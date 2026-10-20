/* Funciones de "app de escritorio" en la web:
   - Instalación como aplicación (PWA) y registro del service worker.
   - Lista de direcciones del servidor (LAN, VPN…) y comprobación de cuál responde.
   - Conmutación automática si la dirección actual deja de responder. */
"use strict";

const Net = (() => {
    const KEY_URLS = "serverUrls";
    const KEY_AUTO = "autoSwitch";
    const SERVICE = "monitor-multinodo";
    let deferredInstall = null;
    let downSince = null;
    let failoverTimer = null;
    let switching = false;

    // ---------- direcciones conocidas ----------
    function urls() {
        let list = [];
        try { list = JSON.parse(App.storage.get(KEY_URLS) || "[]"); } catch (_) { list = []; }
        if (!list.includes(location.origin)) list.unshift(location.origin);
        return list;
    }

    function rememberUrls(list) {
        const clean = [...new Set([location.origin, ...list])];
        App.storage.set(KEY_URLS, JSON.stringify(clean));
        return clean;
    }

    async function refreshFromServer() {
        try {
            const info = await App.api("/api/connection");
            return rememberUrls(info.urls);
        } catch (_) {
            return urls();
        }
    }

    const autoSwitch = () => App.storage.get(KEY_AUTO) !== "0";
    const setAutoSwitch = (on) => App.storage.set(KEY_AUTO, on ? "1" : "0");

    /** Prueba /healthz de una dirección. Devuelve {ok, ms, data, error}. */
    async function probe(url, timeout = 3500) {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), timeout);
        const start = performance.now();
        try {
            const res = await fetch(`${url}/healthz`, { cache: "no-store", credentials: "omit", signal: controller.signal });
            const data = await res.json();
            const ok = res.ok && data.ok === true && data.service === SERVICE;
            return { ok, ms: Math.round(performance.now() - start), data, error: ok ? null : "respuesta inesperada" };
        } catch (err) {
            return { ok: false, ms: null, data: null, error: err.name === "AbortError" ? "sin respuesta" : "inaccesible" };
        } finally {
            clearTimeout(timer);
        }
    }

    async function findAlternative() {
        for (const url of urls()) {
            if (url === location.origin) continue;
            const result = await probe(url);
            if (result.ok) return url;
        }
        return null;
    }

    function go(url) {
        switching = true;
        location.href = url + location.pathname + location.search + location.hash;
    }

    // ---------- aviso de conmutación ----------
    function banner(text, actions = []) {
        let bar = document.getElementById("net-banner");
        if (!bar) {
            bar = App.el("div", { id: "net-banner", class: "net-banner", role: "alert" });
            document.body.appendChild(bar);
        }
        bar.replaceChildren(App.icon("wifi"), App.el("span", { text }), ...actions);
        bar.classList.remove("hidden");
        return bar;
    }

    function hideBanner() {
        document.getElementById("net-banner")?.classList.add("hidden");
    }

    async function checkFailover() {
        if (switching || !downSince) return;
        const retry = () => { if (downSince && !switching) failoverTimer = setTimeout(checkFailover, 15000); };
        const self = await probe(location.origin, 3000);
        if (self.ok) return retry();  // el servidor responde: solo se cortó el WebSocket
        const alt = await findAlternative();
        if (!downSince) return;
        if (!alt) {
            banner("Sin conexión con el servidor en esta dirección. Reintentando…");
            return retry();
        }
        if (!autoSwitch()) {
            banner(`Esta dirección no responde, pero ${alt} sí.`, [
                App.el("button", { class: "btn btn-sm btn-primary", type: "button", onclick: () => go(alt) }, "Cambiar"),
            ]);
            return;
        }
        let seconds = 5;
        const cancel = App.el("button", { class: "btn btn-sm", type: "button", onclick: () => { clearInterval(tick); hideBanner(); } }, "Cancelar");
        const now = App.el("button", { class: "btn btn-sm btn-primary", type: "button", onclick: () => go(alt) }, "Cambiar ya");
        const render = () => banner(`Esta dirección no responde. Cambiando a ${alt} en ${seconds} s (allí tendrás que iniciar sesión si es la primera vez)…`, [now, cancel]);
        render();
        const tick = setInterval(() => {
            seconds -= 1;
            if (!downSince) { clearInterval(tick); hideBanner(); return; }
            if (seconds <= 0) { clearInterval(tick); go(alt); return; }
            render();
        }, 1000);
    }

    document.addEventListener("live-state", (ev) => {
        if (ev.detail) {
            downSince = null;
            clearTimeout(failoverTimer);
            hideBanner();
        } else if (!downSince) {
            downSince = Date.now();
            // Se espera un poco: un reinicio del backend no debe provocar el cambio.
            failoverTimer = setTimeout(checkFailover, 12000);
        }
    });

    // ---------- instalación como app ----------
    const installed = () => window.matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;

    function updateInstallButtons() {
        for (const b of document.querySelectorAll("[data-install]")) b.classList.toggle("hidden", !deferredInstall);
        for (const n of document.querySelectorAll("[data-installed]")) n.classList.toggle("hidden", !installed());
    }

    async function install() {
        if (!deferredInstall) return false;
        deferredInstall.prompt();
        const choice = await deferredInstall.userChoice;
        deferredInstall = null;
        updateInstallButtons();
        return choice.outcome === "accepted";
    }

    window.addEventListener("beforeinstallprompt", (ev) => {
        ev.preventDefault();
        deferredInstall = ev;
        updateInstallButtons();
    });
    window.addEventListener("appinstalled", () => {
        deferredInstall = null;
        updateInstallButtons();
        App.toast("App instalada: búscala en el menú Inicio o en la pantalla de inicio");
    });
    document.addEventListener("click", (ev) => {
        if (ev.target.closest("[data-install]")) install();
    });

    if ("serviceWorker" in navigator && window.isSecureContext) {
        navigator.serviceWorker.register("/sw.js").catch(err => console.warn("Service worker:", err));
    }
    document.addEventListener("DOMContentLoaded", () => {
        updateInstallButtons();
        if (document.body.dataset.role) refreshFromServer();
    });

    return { urls, rememberUrls, refreshFromServer, probe, findAlternative, go, autoSwitch, setAutoSwitch,
             install, installed, canInstall: () => Boolean(deferredInstall) };
})();
