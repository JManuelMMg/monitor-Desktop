"use strict";

(() => {
    const form = document.getElementById("login-form");
    const error = document.getElementById("login-error");

    App.stagger(document.querySelectorAll(".feature-list li"));

    document.getElementById("toggle-pw").addEventListener("click", () => {
        form.password.type = form.password.type === "password" ? "text" : "password";
        form.password.focus();
    });

    form.addEventListener("submit", async (ev) => {
        ev.preventDefault();
        const button = form.querySelector("button[type=submit]");
        error.classList.add("hidden");
        if (!form.username.value.trim() || !form.password.value) {
            error.textContent = "Escribe usuario y contraseña.";
            error.classList.remove("hidden");
            return;
        }
        button.classList.add("loading");
        try {
            await App.api("/api/auth/login", {
                method: "POST",
                body: { username: form.username.value.trim(), password: form.password.value },
            });
            document.querySelector(".auth-card").classList.add("leaving");
            location.href = "/";
        } catch (err) {
            error.textContent = err.message;
            error.classList.remove("hidden");
            form.password.value = "";
            const card = document.querySelector(".auth-card");
            card.classList.remove("shake");
            void card.offsetWidth;  // reinicia la animación
            card.classList.add("shake");
        } finally {
            button.classList.remove("loading");
        }
    });
})();
