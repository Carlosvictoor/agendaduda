# Agenda para Nail Designer

Aplicacao web simples para registrar agendamentos usando Python, HTML e CSS, pronta para rodar localmente ou publicar online.

## Recursos

- Cadastro de cliente, telefone, servico, data, horario e observacoes
- Horarios disponiveis calculados com base nos horarios liberados pela dona e nos agendamentos existentes
- Lista dos proximos atendimentos
- Cancelamento de agendamento direto pela interface
- Painel admin com login com senha hash
- Visao financeira com faturamento previsto
- Link direto para conversa no WhatsApp das clientes
- Cadastro e edicao de servicos e precos pela pagina de Configurações
- Mensagem personalizada no link do WhatsApp com servico, data e horario
- Duracao estimada por servico
- Horarios de funcionamento marcados pela dona na pagina de Configurações, de 06:00 ate 00:00, valendo para todos os dias
- Tela final com confirmacao Agendada com sucesso

## Tecnologias

- Flask
- Flask-SQLAlchemy
- SQLite
- Gunicorn
- HTML e CSS

## Como rodar

1. Ative o ambiente virtual do projeto.
2. Instale as dependencias:

```bash
pip install -r requirements.txt
```

3. Inicie a aplicacao:

```bash
python app.py
```

4. Abra no navegador:

```text
http://127.0.0.1:5000
```

O banco sera criado automaticamente no primeiro start.

## Deploy online

O projeto esta preparado para publicar em Render ou Railway.

Arquivos incluidos para deploy:

- [render.yaml](render.yaml)
- [Procfile](Procfile)
- [wsgi.py](wsgi.py)
- [.env.example](.env.example)

Variaveis importantes:

- `SECRET_KEY`
- `DATABASE_URL`
- `SESSION_COOKIE_SECURE=1`
- `ADMIN_USERNAME=duda`
- `ADMIN_PASSWORD=199612@Vs`

### Render

1. Crie um novo Web Service apontando para este repositorio.
2. Se quiser, use o [render.yaml](render.yaml) para preencher build e start automaticamente.
3. Configure um banco Postgres no Render e copie a `DATABASE_URL`.
4. Defina `SECRET_KEY` e mantenha `SESSION_COOKIE_SECURE=1`.
5. Faça o deploy.

### Railway

1. Crie um novo projeto com este repositorio.
2. Adicione um banco Postgres.
3. Configure `DATABASE_URL`, `SECRET_KEY`, `SESSION_COOKIE_SECURE`, `ADMIN_USERNAME` e `ADMIN_PASSWORD`.
4. O start pode usar o [Procfile](Procfile) ou o comando `gunicorn --bind 0.0.0.0:$PORT wsgi:application`.

## Painel admin

- URL: /admin/login
- Usuario padrao: duda
- Senha padrao: 199612@Vs

Depois do primeiro login, altere usuario e senha na pagina Mudar senha.