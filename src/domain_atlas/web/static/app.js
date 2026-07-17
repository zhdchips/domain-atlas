(() => {
  const setPending = (form) => {
    if (form.dataset.pending === "true") return;
    form.dataset.pending = "true";
    form.setAttribute("aria-busy", "true");
    const message = form.dataset.pendingText || "正在处理…";
    let status = form.querySelector("[data-pending-status]");
    if (!status) {
      status = document.createElement("p");
      status.dataset.pendingStatus = "";
      status.className = "pending-status";
      status.setAttribute("role", "status");
      form.append(status);
    }
    status.textContent = message;
    form.querySelectorAll("button[type='submit'], input[type='submit']").forEach((button) => {
      button.disabled = true;
      button.setAttribute("aria-disabled", "true");
      button.classList.add("is-pending");
    });
  };

  document.querySelectorAll("form[data-pending-form]").forEach((form) => {
    form.addEventListener("submit", () => setPending(form));
  });

  document.querySelectorAll("[data-workflow-poll]").forEach((container) => {
    const url = container.dataset.workflowPoll;
    const refresh = async () => {
      try {
        const response = await fetch(url, { headers: { "X-Requested-With": "DomainAtlas" } });
        if (response.ok) container.innerHTML = await response.text();
      } catch (_) {
        // The persisted page remains usable while a local server is restarting.
      }
    };
    window.setInterval(refresh, 2000);
  });
})();
