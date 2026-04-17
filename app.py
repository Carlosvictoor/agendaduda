import os
import re
import secrets
from datetime import date, datetime, timedelta
from functools import wraps
from pathlib import Path
from urllib.parse import quote

from flask import Flask, abort, flash, jsonify, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix


BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
INSTANCE_DIR.mkdir(exist_ok=True)


def database_uri_from_env():
    database_url = os.getenv("DATABASE_URL", "").strip()
    if database_url:
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        return database_url

    sqlite_path = INSTANCE_DIR / "agenda.db"
    return f"sqlite:///{sqlite_path.as_posix()}"


app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY") or "dev-secret-change-in-production"
app.config["SQLALCHEMY_DATABASE_URI"] = database_uri_from_env()
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Strict"
app.config["SESSION_COOKIE_SECURE"] = os.getenv("SESSION_COOKIE_SECURE", "0") == "1"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)
app.config["PREFERRED_URL_SCHEME"] = "https"

db = SQLAlchemy(app)


BRAND_NAME = "Duda Leumann Nails"
DEFAULT_ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "duda")
DEFAULT_ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "199612@Vs")
MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCKOUT_MINUTES = 15

DEFAULT_SERVICE_PRICES = {
    "Manicure simples": 55.0,
    "Manicure em gel": 85.0,
    "Spa das maos": 70.0,
    "Alongamento": 160.0,
    "Manutencao": 110.0,
    "Decoracao especial": 95.0,
}

DEFAULT_SERVICE_DURATIONS = {
    "Manicure simples": 60,
    "Manicure em gel": 90,
    "Spa das maos": 60,
    "Alongamento": 180,
    "Manutencao": 120,
    "Decoracao especial": 90,
}

SLOT_INTERVAL_MINUTES = 60

WORKING_HOUR_OPTIONS = [
    "06:00",
    "07:00",
    "08:00",
    "09:00",
    "10:00",
    "11:00",
    "12:00",
    "13:00",
    "14:00",
    "15:00",
    "16:00",
    "17:00",
    "18:00",
    "19:00",
    "20:00",
    "21:00",
    "22:00",
    "23:00",
    "00:00",
]

DEFAULT_ACTIVE_HOURS = {
    "09:00",
    "10:00",
    "11:00",
    "12:00",
    "13:00",
    "14:00",
    "15:00",
    "16:00",
    "17:00",
    "18:00",
}

LOGIN_ATTEMPTS = {}


class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    price = db.Column(db.Float, nullable=False)
    duration_minutes = db.Column(db.Integer, nullable=False, default=60)
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class AdminSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    service = db.Column(db.String(120), nullable=False)
    appointment_date = db.Column(db.Date, nullable=False)
    appointment_time = db.Column(db.String(5), nullable=False)
    price = db.Column(db.Float, nullable=False, default=0.0)
    duration_minutes = db.Column(db.Integer, nullable=False, default=60)
    confirmed = db.Column(db.Boolean, nullable=False, default=False)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint(
            "appointment_date",
            "appointment_time",
            name="unique_appointment_slot",
        ),
    )


class AvailableHour(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hour_label = db.Column(db.String(5), nullable=False, unique=True)
    active = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class BusinessHour(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    weekday = db.Column(db.Integer, nullable=False, unique=True)
    is_open = db.Column(db.Boolean, nullable=False, default=True)
    start_time = db.Column(db.String(5), nullable=False, default="09:00")
    end_time = db.Column(db.String(5), nullable=False, default="18:00")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class BlockedPeriod(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    block_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.String(5), nullable=False)
    end_time = db.Column(db.String(5), nullable=False)
    label = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


def seed_default_services():
    existing_services = {service.name: service for service in Service.query.all()}

    for service_name, service_price in DEFAULT_SERVICE_PRICES.items():
        if service_name not in existing_services:
            db.session.add(
                Service(
                    name=service_name,
                    price=service_price,
                    duration_minutes=DEFAULT_SERVICE_DURATIONS.get(service_name, 60),
                    active=True,
                )
            )

    for service in Service.query.all():
        if not service.duration_minutes:
            service.duration_minutes = DEFAULT_SERVICE_DURATIONS.get(service.name, 60)

    db.session.commit()


def seed_available_hours():
    existing_hours = {item.hour_label: item for item in AvailableHour.query.all()}

    for hour_label in WORKING_HOUR_OPTIONS:
        item = existing_hours.get(hour_label)
        if item is None:
            db.session.add(
                AvailableHour(
                    hour_label=hour_label,
                    active=hour_label in DEFAULT_ACTIVE_HOURS,
                )
            )

    db.session.commit()


def ensure_admin_account():
    admin = AdminSetting.query.first()
    if admin:
        return admin

    admin = AdminSetting(
        username=DEFAULT_ADMIN_USERNAME,
        password_hash=generate_password_hash(DEFAULT_ADMIN_PASSWORD),
    )
    db.session.add(admin)
    db.session.commit()
    return admin


def sync_appointment_prices():
    service_map = {
        service.name: {
            "price": service.price,
            "duration_minutes": service.duration_minutes,
        }
        for service in Service.query.all()
    }

    for service_name, service_data in service_map.items():
        db.session.execute(
            text(
                "UPDATE appointment "
                "SET price = :service_price "
                "WHERE service = :service_name AND (price IS NULL OR price = 0)"
            ),
            {"service_price": service_data["price"], "service_name": service_name},
        )
        db.session.execute(
            text(
                "UPDATE appointment "
                "SET duration_minutes = :duration_minutes "
                "WHERE service = :service_name AND (duration_minutes IS NULL OR duration_minutes = 0)"
            ),
            {"duration_minutes": service_data["duration_minutes"], "service_name": service_name},
        )

    db.session.commit()


def currency_br(value):
    formatted = f"{value:,.2f}"
    formatted = formatted.replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R$ {formatted}"


def format_duration(duration_minutes):
    hours = duration_minutes // 60
    minutes = duration_minutes % 60

    if hours and minutes:
        return f"{hours}h {minutes}min"
    if hours:
        return f"{hours}h"
    return f"{minutes}min"


def time_to_minutes(time_value):
    hours, minutes = map(int, time_value.split(":"))
    return hours * 60 + minutes


def minutes_to_time(total_minutes):
    hours = total_minutes // 60
    minutes = total_minutes % 60
    return f"{hours:02d}:{minutes:02d}"


def periods_overlap(start_a, end_a, start_b, end_b):
    return start_a < end_b and end_a > start_b


def blocked_period_conflicts_with_appointments(block_date, start_time, end_time):
    block_start = time_to_minutes(start_time)
    block_end = time_to_minutes(end_time)

    appointments = Appointment.query.filter_by(appointment_date=block_date).all()
    for appointment in appointments:
        appointment_start = time_to_minutes(appointment.appointment_time)
        appointment_end = appointment_start + appointment.duration_minutes
        if periods_overlap(block_start, block_end, appointment_start, appointment_end):
            return True
    return False


def normalize_phone(phone):
    digits = re.sub(r"\D", "", phone)
    if digits and len(digits) in {10, 11}:
        return f"55{digits}"
    return digits


def whatsapp_link(phone, client_name, service=None, appointment_date=None, appointment_time=None):
    digits = normalize_phone(phone)
    if not digits:
        return None

    if appointment_date and appointment_time:
        tomorrow = date.today() + timedelta(days=1)
        if appointment_date == tomorrow:
            schedule_text = f"amanha as {appointment_time}"
        elif appointment_date == date.today():
            schedule_text = f"hoje as {appointment_time}"
        else:
            formatted_date = appointment_date.strftime("%d/%m/%Y")
            schedule_text = f"no dia {formatted_date} as {appointment_time}"
    elif appointment_date:
        formatted_date = appointment_date.strftime("%d/%m/%Y")
        schedule_text = f"no dia {formatted_date}"
    elif appointment_time:
        schedule_text = f"as {appointment_time}"
    else:
        schedule_text = "conforme combinado"

    message = quote(
        "\n".join(
            [
                f"Ola, {client_name}, tudo bem?",
                f"Passando para lembra-la que seu compromisso esta agendado para {schedule_text}.",
                "",
                "Estou ansiosa para te atender!",
                "",
                "Endereco: Rua 1o de Janeiro, 660, sala 02 - Nova Mirim, Praia Grande - SP, 11704-800",
                "(Em cima do Bar Lider do Litoral, porta ao lado. Em frente ao Mc Donalds)",
                "",
                "*Aviso Importante:*",
                "",
                "- A tolerancia para atrasos e de 10 minutos. Apos esse periodo, o atendimento sera automaticamente cancelado para nao atrasar a proxima cliente.",
                "- Nao e permitido levar acompanhantes.",
                "- Nao realizar cuticulagem 5 dias antes do procedimento.",
                "",
                "Agradecemos a compreensao!",
            ]
        )
    )
    return f"https://wa.me/{digits}?text={message}"


def client_ip_address():
    forwarded_for = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    return forwarded_for or request.remote_addr or "unknown"


def login_lock_state(ip_address):
    attempt_data = LOGIN_ATTEMPTS.get(ip_address)
    if not attempt_data:
        return False

    locked_until = attempt_data.get("locked_until")
    if locked_until and locked_until > datetime.utcnow():
        return True

    if locked_until and locked_until <= datetime.utcnow():
        LOGIN_ATTEMPTS.pop(ip_address, None)

    return False


def register_failed_login(ip_address):
    now = datetime.utcnow()
    attempt_data = LOGIN_ATTEMPTS.get(ip_address)

    if not attempt_data or attempt_data["window_expires_at"] <= now:
        attempt_data = {
            "count": 0,
            "window_expires_at": now + timedelta(minutes=LOGIN_LOCKOUT_MINUTES),
            "locked_until": None,
        }

    attempt_data["count"] += 1
    if attempt_data["count"] >= MAX_LOGIN_ATTEMPTS:
        attempt_data["locked_until"] = now + timedelta(minutes=LOGIN_LOCKOUT_MINUTES)

    LOGIN_ATTEMPTS[ip_address] = attempt_data


def clear_failed_logins(ip_address):
    LOGIN_ATTEMPTS.pop(ip_address, None)


def generate_csrf_token():
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


def admin_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if not session.get("is_admin"):
            flash("Entre no painel admin para continuar.", "error")
            return redirect(url_for("admin_login"))
        return view_func(*args, **kwargs)

    return wrapped_view


def service_catalog():
    return [
        {
            "id": service.id,
            "name": service.name,
            "price": service.price,
            "duration_minutes": service.duration_minutes,
            "duration_label": format_duration(service.duration_minutes),
            "active": service.active,
        }
        for service in Service.query.filter_by(active=True).order_by(Service.name.asc()).all()
    ]


def all_services_catalog():
    return Service.query.order_by(Service.active.desc(), Service.name.asc()).all()


def get_service_by_name(service_name):
    return Service.query.filter_by(name=service_name, active=True).first()


def get_admin_account():
    return AdminSetting.query.first()


def hour_sort_key(hour_label):
    if hour_label == "00:00":
        return 24 * 60
    return time_to_minutes(hour_label)


def all_available_hours():
    return sorted(AvailableHour.query.all(), key=lambda item: hour_sort_key(item.hour_label))


def available_hours_catalog():
    return [
        {
            "hour_label": item.hour_label,
            "active": item.active,
        }
        for item in all_available_hours()
    ]


def selected_working_hours():
    return [item.hour_label for item in all_available_hours() if item.active]


def build_dashboard_data():
    appointments = upcoming_appointments()
    today = date.today()
    month_key = today.strftime("%Y-%m")

    today_appointments = [item for item in appointments if item.appointment_date == today]
    month_appointments = [
        item for item in appointments if item.appointment_date.strftime("%Y-%m") == month_key
    ]
    unique_clients = len({item.phone for item in appointments})
    services = all_services_catalog()
    available_hours = all_available_hours()

    return {
        "appointments": appointments,
        "services": services,
        "available_hours": available_hours,
        "stats": {
            "today_revenue": sum(item.price for item in today_appointments),
            "month_revenue": sum(item.price for item in month_appointments),
            "scheduled_revenue": sum(item.price for item in appointments),
            "today_count": len(today_appointments),
            "scheduled_count": len(appointments),
            "client_count": unique_clients,
            "service_count": len(services),
            "active_hours_count": sum(1 for item in available_hours if item.active),
        },
    }


@app.context_processor
def inject_global_template_data():
    return {
        "brand_name": BRAND_NAME,
        "is_admin": session.get("is_admin", False),
        "whatsapp_link": whatsapp_link,
        "csrf_token": generate_csrf_token,
    }


@app.before_request
def protect_post_requests():
    if request.method != "POST":
        return None

    session_token = session.get("_csrf_token")
    form_token = request.form.get("csrf_token", "")
    if not session_token or not form_token or not secrets.compare_digest(session_token, form_token):
        abort(400)

    return None


@app.after_request
def apply_security_headers(response):
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com data:; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "object-src 'none'"
    )

    if request.path.startswith("/admin") or request.endpoint == "booking_success":
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

    return response


@app.template_filter("currency_br")
def currency_br_filter(value):
    return currency_br(value or 0)


@app.template_filter("duration_label")
def duration_label_filter(value):
    return format_duration(value or 0)


def upcoming_appointments():
    today = date.today()
    now_time = datetime.now().strftime("%H:%M")

    return (
        Appointment.query.filter(
            db.or_(
                Appointment.appointment_date > today,
                db.and_(
                    Appointment.appointment_date == today,
                    Appointment.appointment_time >= now_time,
                ),
            )
        )
        .order_by(Appointment.appointment_date.asc(), Appointment.appointment_time.asc())
        .all()
    )


def available_slots_for_date(selected_date, service_name=None):
    if selected_date < date.today():
        return []

    selected_service = get_service_by_name(service_name) if service_name else None
    duration_minutes = selected_service.duration_minutes if selected_service else 60
    appointments = Appointment.query.filter_by(appointment_date=selected_date).all()
    active_hours = selected_working_hours()
    if not active_hours:
        return []

    current_time = datetime.now().strftime("%H:%M")
    slots = []
    for slot in active_hours:
        start_minutes = time_to_minutes(slot)
        end_minutes = start_minutes + duration_minutes

        if end_minutes > 24 * 60:
            continue
        if selected_date == date.today() and slot <= current_time:
            continue

        conflicting_appointment = any(
            periods_overlap(
                start_minutes,
                end_minutes,
                time_to_minutes(appointment.appointment_time),
                time_to_minutes(appointment.appointment_time) + appointment.duration_minutes,
            )
            for appointment in appointments
        )
        if conflicting_appointment:
            continue

        slots.append(slot)

    return slots


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        client_name = request.form.get("client_name", "").strip()
        phone = request.form.get("phone", "").strip()
        service = request.form.get("service", "").strip()
        appointment_date_raw = request.form.get("appointment_date", "").strip()
        appointment_time = request.form.get("appointment_time", "").strip()
        notes = request.form.get("notes", "").strip()

        if not all([client_name, phone, service, appointment_date_raw, appointment_time]):
            flash("Preencha todos os campos obrigatorios.", "error")
            return redirect(url_for("index"))

        selected_service = get_service_by_name(service)
        if selected_service is None:
            flash("Selecione um servico valido.", "error")
            return redirect(url_for("index"))

        try:
            appointment_date = datetime.strptime(appointment_date_raw, "%Y-%m-%d").date()
        except ValueError:
            flash("A data informada e invalida.", "error")
            return redirect(url_for("index"))

        if appointment_date < date.today():
            flash("Nao e possivel agendar em uma data passada.", "error")
            return redirect(url_for("index"))

        if appointment_date == date.today() and appointment_time < datetime.now().strftime("%H:%M"):
            flash("Escolha um horario futuro para hoje.", "error")
            return redirect(url_for("index"))

        if appointment_time not in available_slots_for_date(appointment_date, service):
            flash("Esse horario nao esta mais disponivel. Escolha outro horario.", "error")
            return redirect(url_for("index"))

        slot_taken = Appointment.query.filter_by(
            appointment_date=appointment_date,
            appointment_time=appointment_time,
        ).first()

        if slot_taken:
            flash("Esse horario ja esta reservado. Escolha outro horario.", "error")
            return redirect(url_for("index"))

        appointment = Appointment(
            client_name=client_name,
            phone=phone,
            service=service,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            price=selected_service.price,
            duration_minutes=selected_service.duration_minutes,
            confirmed=False,
            notes=notes or None,
        )
        db.session.add(appointment)
        db.session.commit()
        return redirect(url_for("booking_success", appointment_id=appointment.id))

    appointments = upcoming_appointments()
    return render_template(
        "index.html",
        appointments=appointments,
        services=service_catalog(),
        min_date=date.today().isoformat(),
        featured_revenue=sum(item.price for item in appointments),
        featured_clients=len({item.phone for item in appointments}),
        featured_today=sum(1 for item in appointments if item.appointment_date == date.today()),
        working_hours=selected_working_hours(),
    )


@app.get("/agendada/<int:appointment_id>")
def booking_success(appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)
    return render_template("booking_success.html", appointment=appointment)


@app.get("/available-slots")
def available_slots():
    selected_date_raw = request.args.get("date", "").strip()
    service_name = request.args.get("service", "").strip()

    if not selected_date_raw:
        return jsonify({"slots": [], "message": "Selecione uma data."})

    try:
        selected_date = datetime.strptime(selected_date_raw, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"slots": [], "message": "Data invalida."}), 400

    slots = available_slots_for_date(selected_date, service_name)
    if not selected_working_hours():
        message = "Nenhum horario de funcionamento foi liberado no momento."
    elif not slots:
        message = "Nenhum horario disponivel nessa data."
    else:
        message = "Escolha um horario disponivel."

    return jsonify({"slots": slots, "message": message})


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("is_admin"):
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        ip_address = client_ip_address()
        if login_lock_state(ip_address):
            flash("Muitas tentativas de login. Tente novamente em alguns minutos.", "error")
            return render_template("admin_login.html"), 429

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        admin = get_admin_account()

        if admin and username == admin.username and check_password_hash(admin.password_hash, password):
            session.clear()
            session["is_admin"] = True
            session.permanent = True
            session["_csrf_token"] = secrets.token_urlsafe(32)
            clear_failed_logins(ip_address)
            flash("Painel liberado com sucesso.", "success")
            return redirect(url_for("admin_dashboard"))

        register_failed_login(ip_address)
        flash("Usuario ou senha invalidos.", "error")

    return render_template("admin_login.html")


@app.get("/admin/logout")
def admin_logout():
    session.clear()
    flash("Sessao admin encerrada.", "success")
    return redirect(url_for("index"))


@app.get("/admin")
@admin_required
def admin_dashboard():
    dashboard = build_dashboard_data()
    return render_template(
        "admin.html",
        stats=dashboard["stats"],
    )


@app.get("/admin/settings")
@admin_required
def admin_settings():
    dashboard = build_dashboard_data()
    return render_template(
        "settings.html",
        services=dashboard["services"],
        available_hours=available_hours_catalog(),
        stats=dashboard["stats"],
    )


@app.post("/admin/business-hours")
@admin_required
def update_business_hours():
    selected_hours = set(request.form.getlist("selected_hours"))

    for item in AvailableHour.query.all():
        item.active = item.hour_label in selected_hours

    db.session.commit()
    flash("Horarios de funcionamento atualizados com sucesso.", "success")
    return redirect(url_for("admin_settings"))


@app.get("/admin/agenda")
@admin_required
def admin_agenda():
    dashboard = build_dashboard_data()
    return render_template(
        "agenda.html",
        appointments=dashboard["appointments"],
        stats=dashboard["stats"],
    )


@app.post("/admin/services")
@admin_required
def create_service():
    service_name = request.form.get("name", "").strip()
    price_raw = request.form.get("price", "").strip().replace(",", ".")
    duration_raw = request.form.get("duration_minutes", "").strip()

    if not service_name or not price_raw or not duration_raw:
        flash("Informe nome, preco e duracao do servico.", "error")
        return redirect(url_for("admin_settings"))

    try:
        price = float(price_raw)
    except ValueError:
        flash("Preco invalido.", "error")
        return redirect(url_for("admin_settings"))

    try:
        duration_minutes = int(duration_raw)
    except ValueError:
        flash("Duracao invalida.", "error")
        return redirect(url_for("admin_settings"))

    if price <= 0 or duration_minutes <= 0:
        flash("Preco e duracao devem ser maiores que zero.", "error")
        return redirect(url_for("admin_settings"))

    existing_service = Service.query.filter(db.func.lower(Service.name) == service_name.lower()).first()
    if existing_service:
        flash("Ja existe um servico com esse nome.", "error")
        return redirect(url_for("admin_settings"))

    db.session.add(
        Service(
            name=service_name,
            price=price,
            duration_minutes=duration_minutes,
            active=True,
        )
    )
    db.session.commit()
    flash("Servico criado com sucesso.", "success")
    return redirect(url_for("admin_settings"))


@app.post("/admin/services/<int:service_id>")
@admin_required
def update_service(service_id):
    service = Service.query.get_or_404(service_id)
    new_name = request.form.get("name", "").strip()
    price_raw = request.form.get("price", "").strip().replace(",", ".")
    duration_raw = request.form.get("duration_minutes", "").strip()
    is_active = request.form.get("active") == "on"

    if not new_name or not price_raw or not duration_raw:
        flash("Nome, preco e duracao sao obrigatorios.", "error")
        return redirect(url_for("admin_settings"))

    try:
        new_price = float(price_raw)
    except ValueError:
        flash("Preco invalido.", "error")
        return redirect(url_for("admin_settings"))

    try:
        new_duration_minutes = int(duration_raw)
    except ValueError:
        flash("Duracao invalida.", "error")
        return redirect(url_for("admin_settings"))

    if new_price <= 0 or new_duration_minutes <= 0:
        flash("Preco e duracao devem ser maiores que zero.", "error")
        return redirect(url_for("admin_settings"))

    name_in_use = (
        Service.query.filter(db.func.lower(Service.name) == new_name.lower(), Service.id != service.id).first()
    )
    if name_in_use:
        flash("Outro servico ja usa esse nome.", "error")
        return redirect(url_for("admin_settings"))

    old_name = service.name
    service.name = new_name
    service.price = new_price
    service.duration_minutes = new_duration_minutes
    service.active = is_active

    future_appointments = Appointment.query.filter(
        Appointment.service == old_name,
        Appointment.appointment_date >= date.today(),
    ).all()

    for appointment in future_appointments:
        appointment.service = new_name
        appointment.price = new_price
        appointment.duration_minutes = new_duration_minutes

    db.session.commit()
    flash("Servico atualizado com sucesso.", "success")
    return redirect(url_for("admin_settings"))


@app.post("/admin/blocks")
@admin_required
def create_blocked_period():
    block_date_raw = request.form.get("block_date", "").strip()
    start_time = request.form.get("start_time", "").strip()
    end_time = request.form.get("end_time", "").strip()
    label = request.form.get("label", "").strip()

    if not block_date_raw or not start_time or not end_time:
        flash("Preencha data, inicio e fim do bloqueio.", "error")
        return redirect(url_for("admin_settings"))

    try:
        block_date = datetime.strptime(block_date_raw, "%Y-%m-%d").date()
    except ValueError:
        flash("Data do bloqueio invalida.", "error")
        return redirect(url_for("admin_settings"))

    if time_to_minutes(end_time) <= time_to_minutes(start_time):
        flash("O horario final precisa ser maior que o inicial.", "error")
        return redirect(url_for("admin_settings"))

    if blocked_period_conflicts_with_appointments(block_date, start_time, end_time):
        flash("Esse bloqueio conflita com um agendamento existente.", "error")
        return redirect(url_for("admin_settings"))

    blocked_period = BlockedPeriod(
        block_date=block_date,
        start_time=start_time,
        end_time=end_time,
        label=label or None,
    )
    db.session.add(blocked_period)
    db.session.commit()
    flash("Bloqueio adicionado com sucesso.", "success")
    return redirect(url_for("admin_settings"))


@app.post("/admin/blocks/<int:block_id>/delete")
@admin_required
def delete_blocked_period(block_id):
    blocked_period = BlockedPeriod.query.get_or_404(block_id)
    db.session.delete(blocked_period)
    db.session.commit()
    flash("Bloqueio removido.", "success")
    return redirect(url_for("admin_settings"))


@app.post("/admin/security")
@admin_required
def update_admin_security():
    admin = get_admin_account()
    current_password = request.form.get("current_password", "")
    new_username = request.form.get("username", "").strip()
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not admin or not check_password_hash(admin.password_hash, current_password):
        flash("Senha atual invalida.", "error")
        return redirect(url_for("admin_login"))

    if not new_username:
        flash("Informe um usuario valido.", "error")
        return redirect(url_for("admin_login"))

    if new_password:
        if len(new_password) < 6:
            flash("A nova senha precisa ter pelo menos 6 caracteres.", "error")
            return redirect(url_for("admin_login"))
        if new_password != confirm_password:
            flash("A confirmacao da nova senha nao confere.", "error")
            return redirect(url_for("admin_login"))
        admin.password_hash = generate_password_hash(new_password)

    admin.username = new_username
    db.session.commit()
    session.clear()
    flash("Credenciais atualizadas. Entre novamente com os novos dados.", "success")
    return redirect(url_for("admin_login"))


@app.post("/cancel/<int:appointment_id>")
def cancel_appointment(appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)
    db.session.delete(appointment)
    db.session.commit()
    flash("Agendamento cancelado.", "success")

    next_view = request.form.get("next_view", "index")
    if next_view == "admin_dashboard" and session.get("is_admin"):
        return redirect(url_for("admin_dashboard"))
    if next_view == "admin_agenda" and session.get("is_admin"):
        return redirect(url_for("admin_agenda"))
    return redirect(url_for("index"))


@app.post("/admin/appointments/<int:appointment_id>/confirm")
@admin_required
def confirm_appointment(appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)
    if not appointment.confirmed:
        appointment.confirmed = True
        db.session.commit()
        flash("Agendamento confirmado.", "success")
    else:
        flash("Esse agendamento ja estava confirmado.", "success")
    return redirect(url_for("admin_agenda"))


with app.app_context():
    db.create_all()
    seed_default_services()
    seed_available_hours()
    ensure_admin_account()
    sync_appointment_prices()


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "0") == "1")