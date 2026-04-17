document.addEventListener("DOMContentLoaded", () => {
  const mobileNavToggle = document.querySelector("[data-mobile-nav-toggle]");
  const mobileNav = document.querySelector("[data-mobile-nav]");

  if (mobileNavToggle && mobileNav) {
    const closeMobileNav = () => {
      mobileNav.classList.remove("is-open");
      mobileNavToggle.classList.remove("is-active");
      mobileNavToggle.setAttribute("aria-expanded", "false");
      document.body.classList.remove("has-mobile-nav-open");
    };

    mobileNavToggle.addEventListener("click", () => {
      const willOpen = !mobileNav.classList.contains("is-open");
      mobileNav.classList.toggle("is-open", willOpen);
      mobileNavToggle.classList.toggle("is-active", willOpen);
      mobileNavToggle.setAttribute("aria-expanded", String(willOpen));
      document.body.classList.toggle("has-mobile-nav-open", willOpen);
    });

    mobileNav.querySelectorAll("a").forEach((link) => {
      link.addEventListener("click", closeMobileNav);
    });

    window.addEventListener("resize", () => {
      if (window.innerWidth > 980) {
        closeMobileNav();
      }
    });
  }

  const bookingForm = document.querySelector("[data-booking-form]");
  if (!bookingForm) {
    return;
  }

  const serviceSelect = bookingForm.querySelector("[data-service-select]");
  const dateInput = bookingForm.querySelector("[data-date-input]");
  const timeInput = bookingForm.querySelector("[data-time-input]");
  const slotGrid = bookingForm.querySelector("[data-slot-grid]");
  const slotMessage = bookingForm.querySelector("[data-slot-message]");
  const phoneInput = bookingForm.querySelector("[data-phone-mask]");
  const serviceCards = document.querySelectorAll("[data-service-name]");
  const serviceButtons = document.querySelectorAll("[data-service-trigger]");

  const setSelectedService = (serviceName) => {
    if (!serviceSelect) {
      return;
    }

    serviceSelect.value = serviceName;

    serviceCards.forEach((card) => {
      card.classList.toggle("is-selected", card.dataset.serviceName === serviceName);
    });

    serviceButtons.forEach((button) => {
      button.classList.toggle("is-selected", button.dataset.serviceTrigger === serviceName);
    });

    if (dateInput && dateInput.value) {
      loadSlots();
    }
  };

  const renderSlots = (slots) => {
    slotGrid.innerHTML = "";

    if (!slots.length) {
      const emptyState = document.createElement("p");
      emptyState.className = "slot-picker__empty";
      emptyState.textContent = "Sem horarios livres nessa data.";
      slotGrid.appendChild(emptyState);
      timeInput.value = "";
      return;
    }

    slots.forEach((slot) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "slot-button";
      button.textContent = slot;
      button.dataset.slotValue = slot;

      button.addEventListener("click", () => {
        timeInput.value = slot;
        slotGrid.querySelectorAll(".slot-button").forEach((item) => {
          item.classList.toggle("is-selected", item.dataset.slotValue === slot);
        });
      });

      slotGrid.appendChild(button);
    });
  };

  const loadSlots = async () => {
    const selectedDate = dateInput.value;
    const selectedService = serviceSelect.value;
    if (!selectedDate) {
      slotMessage.textContent = "Selecione uma data para ver os horarios disponiveis.";
      return;
    }

    if (!selectedService) {
      slotMessage.textContent = "Selecione um servico para ver os horarios disponiveis.";
      return;
    }

    slotMessage.textContent = "Carregando horarios...";
    timeInput.value = "";

    try {
      const response = await fetch(`/available-slots?date=${selectedDate}&service=${encodeURIComponent(selectedService)}`);
      const data = await response.json();

      slotMessage.textContent = data.message || "Escolha um horario disponivel.";
      renderSlots(data.slots || []);
    } catch (error) {
      slotMessage.textContent = "Nao foi possivel carregar os horarios agora.";
      renderSlots([]);
    }
  };

  const formatPhone = (value) => {
    const digits = value.replace(/\D/g, "").slice(0, 11);

    if (digits.length <= 2) {
      return digits ? `(${digits}` : "";
    }

    if (digits.length <= 7) {
      return `(${digits.slice(0, 2)}) ${digits.slice(2)}`;
    }

    if (digits.length <= 10) {
      return `(${digits.slice(0, 2)}) ${digits.slice(2, 6)}-${digits.slice(6)}`;
    }

    return `(${digits.slice(0, 2)}) ${digits.slice(2, 7)}-${digits.slice(7)}`;
  };

  serviceCards.forEach((card) => {
    card.addEventListener("click", () => setSelectedService(card.dataset.serviceName));
  });

  serviceButtons.forEach((button) => {
    button.addEventListener("click", () => setSelectedService(button.dataset.serviceTrigger));
  });

  if (serviceSelect) {
    serviceSelect.addEventListener("change", () => {
      setSelectedService(serviceSelect.value);
      if (dateInput.value) {
        loadSlots();
      }
    });
  }

  if (dateInput) {
    dateInput.addEventListener("change", loadSlots);
  }

  if (phoneInput) {
    phoneInput.addEventListener("input", () => {
      phoneInput.value = formatPhone(phoneInput.value);
    });
  }
});