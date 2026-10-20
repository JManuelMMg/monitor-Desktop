"use strict";

(() => {
    const form = document.getElementById("password-form");
    const meter = document.getElementById("pw-meter");
    const help = document.getElementById("pw-help");

    function strength(pw) {
        let score = Math.min(pw.length / 20, 1) * 60;
        if (/[a-z]/.test(pw) && /[A-Z]/.test(pw)) score += 12;
        if (/\d/.test(pw)) score += 12;
        if (/[^A-Za-z0-9]/.test(pw)) score += 16;
        return Math.min(100, score);
    }

    document.getElementById("new-pw").addEventListener("input", (ev) => {
        const pw = ev.target.value;
        const s = strength(pw);
        meter.style.width = `${s}%`;
        help.textContent = pw.length < 10 ? `Faltan ${10 - pw.length} caracteres.`
            : s < 60 ? "Válida, pero podría ser más larga." : "Contraseña robusta.";
    });

    form.addEventListener("submit", async (ev) => {
        ev.preventDefault();
        const v = App.formToObject(form);
        if (v.new_password !== v.repeat) {
            App.toast("Las contraseñas nuevas no coinciden", true);
            return;
        }
        ev.submitter?.classList.add("loading");
        try {
            await App.api("/api/auth/password", {
                method: "POST",
                body: { current_password: v.current_password, new_password: v.new_password },
            });
            form.reset();
            meter.style.width = "0";
            App.toast("Contraseña cambiada");
        } catch (err) {
            App.toast(err.message, true);
        } finally {
            ev.submitter?.classList.remove("loading");
        }
    });
    App.connectLive(() => {});
})();
