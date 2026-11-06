/* Tema claro / oscuro.
   Se carga en <head> antes de la hoja de estilos para aplicar el tema guardado
   sin parpadeo (la CSP no permite scripts en línea). La elección se guarda en
   este navegador (también en la app de escritorio, que usa su propio almacén).
   Sin elección guardada se usa el oscuro, el aspecto original del panel. */
"use strict";

const Theme = (() => {
    const KEY = "theme";
    const META_BG = { dark: "#0f1720", light: "#ffffff" };

    function stored() {
        try {
            const value = localStorage.getItem(KEY);
            return value === "light" || value === "dark" ? value : null;
        } catch (_) {
            return null;
        }
    }

    function setMeta(name, content) {
        let meta = document.querySelector(`meta[name="${name}"]`);
        if (!meta) {
            meta = document.createElement("meta");
            meta.name = name;
            document.head.appendChild(meta);
        }
        meta.content = content;
    }

    function apply(theme) {
        document.documentElement.dataset.theme = theme;
        setMeta("color-scheme", theme);
        setMeta("theme-color", META_BG[theme]);
    }

    function current() {
        return document.documentElement.dataset.theme === "light" ? "light" : "dark";
    }

    function set(theme) {
        const root = document.documentElement;
        root.classList.add("theme-switching");
        apply(theme);
        try { localStorage.setItem(KEY, theme); } catch (_) { /* sin almacenamiento */ }
        // App de escritorio: guarda el tema en su config.json para su pantalla de conexión.
        try { window.pywebview?.api?.set_theme?.(theme); } catch (_) { /* no es la app */ }
        updateButtons();
        document.dispatchEvent(new CustomEvent("themechange", { detail: theme }));
        setTimeout(() => root.classList.remove("theme-switching"), 300);
    }

    function updateButtons() {
        const light = current() === "light";
        for (const btn of document.querySelectorAll("[data-theme-toggle]")) {
            btn.setAttribute("aria-pressed", String(light));
            btn.setAttribute("aria-label", light ? "Cambiar a tema oscuro" : "Cambiar a tema claro");
        }
    }

    apply(stored() || "dark");

    document.addEventListener("click", (ev) => {
        if (ev.target.closest("[data-theme-toggle]")) set(current() === "light" ? "dark" : "light");
    });
    document.addEventListener("DOMContentLoaded", updateButtons);
    // Otra pestaña o ventana cambió el tema.
    window.addEventListener("storage", (ev) => {
        if (ev.key === KEY && (ev.newValue === "light" || ev.newValue === "dark") && ev.newValue !== current()) {
            apply(ev.newValue);
            updateButtons();
            document.dispatchEvent(new CustomEvent("themechange", { detail: ev.newValue }));
        }
    });

    return { current, set };
})();
