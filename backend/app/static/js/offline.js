/* Pantalla sin conexión (la sirve el service worker cuando la Pi no responde). */
"use strict";

(() => {
    const status = document.getElementById("off-status");
    const list = document.getElementById("off-list");
    document.getElementById("off-origin").textContent = location.origin;
    let countdown = null;
    let checking = false;

    function row(url, result) {
        const state = result ? (result.ok ? "ok" : "bad") : "testing";
        const note = !result ? "comprobando…" : result.ok ? `responde · ${result.ms} ms` : result.error;
        return App.el("div", { class: `server ${state} ${url === location.origin ? "current" : ""}` },
            App.el("span", { class: "dot" }),
            App.el("span", { class: "server-url" }, url, App.el("small", { class: "muted", text: url === location.origin ? `esta dirección · ${note}` : note })),
            App.el("span", { class: "latency" }),
            result?.ok && url !== location.origin
                ? App.el("button", { class: "btn btn-sm btn-primary", type: "button", onclick: () => Net.go(url) }, "Abrir")
                : App.el("span"));
    }

    async function check() {
        if (checking || countdown) return;
        checking = true;
        const urls = Net.urls();
        list.replaceChildren(...urls.map(u => row(u, null)));
        const results = await Promise.all(urls.map(u => Net.probe(u)));
        list.replaceChildren(...urls.map((u, i) => row(u, results[i])));
        checking = false;

        if (results[urls.indexOf(location.origin)]?.ok) {
            status.textContent = "¡La conexión volvió! Cargando…";
            location.reload();
            return;
        }
        const alt = urls.find((u, i) => u !== location.origin && results[i].ok);
        if (alt && Net.autoSwitch()) {
            let seconds = 5;
            const tick = () => {
                status.textContent = `${alt} responde. Cambiando en ${seconds} s…`;
                if (seconds-- <= 0) { clearInterval(countdown); Net.go(alt); }
            };
            tick();
            countdown = setInterval(tick, 1000);
        } else {
            status.textContent = alt
                ? `Esta dirección no responde, pero ${alt} sí. Pulsa «Abrir».`
                : `Ninguna dirección responde. Nuevo intento en unos segundos…`;
        }
    }

    document.getElementById("off-retry").addEventListener("click", check);
    check();
    setInterval(check, 6000);
})();
