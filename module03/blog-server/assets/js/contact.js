/* ============================================================
   Contact page: inline validation + async POST to the Python
   server (which logs the body and answers with a 302).
   ============================================================ */
(function () {
  "use strict";

  const { toast, autoGrow } = window.App;
  const form = document.getElementById("contact-form");
  const message = form.querySelector('[name="message"]');
  const counter = document.getElementById("char-count");
  const button = form.querySelector("button[type=submit]");
  const MAX = 500;

  const RULES = {
    name: (v) => (v.trim().length >= 2 ? "" : "Please enter at least 2 characters."),
    email: (v) => (/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v.trim()) ? "" : "That doesn't look like an email address."),
    message: (v) =>
      v.trim().length < 10
        ? "Tell us a bit more — at least 10 characters."
        : v.length > MAX
        ? `Keep it under ${MAX} characters.`
        : "",
  };

  function validateField(input) {
    const rule = RULES[input.name];
    if (!rule) return true;
    const error = rule(input.value);
    const field = input.closest(".field");
    field.classList.toggle("invalid", Boolean(error));
    field.querySelector(".error").textContent = error;
    return !error;
  }

  form.querySelectorAll("input, textarea").forEach((input) => {
    input.addEventListener("blur", () => validateField(input));
    input.addEventListener("input", () => {
      if (input.closest(".field").classList.contains("invalid")) validateField(input);
    });
  });

  message.addEventListener("input", () => {
    autoGrow(message);
    counter.textContent = `${message.value.length} / ${MAX}`;
    counter.style.color = message.value.length > MAX ? "var(--red)" : "";
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const fields = [...form.querySelectorAll("input, textarea")];
    const ok = fields.map(validateField).every(Boolean);
    if (!ok) {
      toast("Please fix the highlighted fields", "err");
      form.querySelector(".field.invalid input, .field.invalid textarea").focus();
      return;
    }

    button.disabled = true;
    button.textContent = "Sending…";

    try {
      const res = await fetch("/contact", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams(new FormData(form)).toString(),
      });
      if (!res.ok) throw new Error("HTTP " + res.status);

      form.reset();
      counter.textContent = `0 / ${MAX}`;
      message.style.height = "auto";
      document.getElementById("sent").hidden = false;
      toast("Message sent — check the server console");
    } catch (err) {
      console.error(err);
      toast("Could not reach the server: " + err.message, "err");
    } finally {
      button.disabled = false;
      button.textContent = "Send message";
    }
  });
})();
