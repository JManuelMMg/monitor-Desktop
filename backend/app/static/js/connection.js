"use strict";

(() => {
    const list = document.getElementById("server-list");
    const auto = document.getElementById("auto-switch");
    let live = false;

    function row(url) {
        const current = url === location.origin;
        const open = App.el("a", { class: "btn btn-sm btn-ghost", href: `${url}/`, text: current ? "Actual" : "Abrir" });
        if (current) open.setAttribute("aria-disabled", "true");
        return App.el("div", { class: `server ${current ? "current" : ""}`, "data-url": url },
            App.el("span", { class: "dot" }),
            App.el("span", { class: "server-url" }, url, App.el("small", { class: "muted", text: current ? "estás conectado por aquí" : "—" })),
            App.el("span", { class: "latency", text: "—" }),
            open);
    }

    async function testRow(item) {
        const url = item.dataset.url;
        item.className = `server ${url === location.origin ? "current" : ""} testing`;
        item.querySelector(".latency").textContent = "…";
        const r = await Net.probe(url);
        item.classList.remove("testing");
        item.classList.add(r.ok ? "ok" : "bad");
        item.querySelector(".latency").textContent = r.ok ? `${r.ms} ms` : "—";
        const note = item.querySelector("small");
        if (url === location.origin) note.textContent = r.ok ? "estás conectado por aquí" : "no responde";
        else note.textContent = r.ok ? "responde · disponible para cambiar" : r.error;
        return r;
    }

    async function testAll() {
        const button = document.getElementById("test-all");
        button.classList.add("loading");
        const items = [...list.children];
        const results = await Promise.all(items.map(testRow));
        button.classList.remove("loading");
        const current = results[items.findIndex(i => i.dataset.url === location.origin)];
        renderCurrent(current);
    }

    function renderCurrent(result) {
        const data = result?.data || {};
        const item = (label, state, sub) => App.el("div", { class: `health-item ${state}` }, App.el("span", { class: "dot" }), label, App.el("span", { class: "sub", text: sub }));
        document.getElementById("current-health").replaceChildren(
            item("Servidor", result?.ok ? "ok" : "bad", result?.ok ? "responde" : "sin respuesta"),
            item("Tiempo real", live ? "ok" : "warn", live ? "WebSocket activo" : "reconectando"),
            item("Broker MQTT", data.mqtt ? "ok" : "bad", data.mqtt ? "conectado" : "sin conexión"),
            item("Base de datos", data.db ? "ok" : "warn", data.db ? "Neon OK" : "guardando en local"),
        );
        document.getElementById("cur-url").textContent = location.origin;
        document.getElementById("cur-latency").textContent = result?.ok ? `${result.ms} ms` : "—";
        document.getElementById("cur-secure").textContent = location.protocol === "https:" ? "Sí (HTTPS)" : "No (solo desarrollo)";
        const badge = document.getElementById("mode-badge");
        badge.className = `status ${Net.installed() ? "online" : "pending"}`;
        badge.textContent = Net.installed() ? "App instalada" : "En el navegador";
    }

    document.addEventListener("live-state", (ev) => { live = ev.detail; });
    auto.checked = Net.autoSwitch();
    auto.addEventListener("change", () => {
        Net.setAutoSwitch(auto.checked);
        App.toast(auto.checked ? "Cambio automático activado" : "Cambio automático desactivado: se te preguntará antes");
    });
    document.getElementById("test-all").addEventListener("click", testAll);

    (async () => {
        const urls = await Net.refreshFromServer();
        list.replaceChildren(...urls.map(row));
        App.stagger(list.children);
        testAll();
    })();

    App.connectLive(() => {});
    setInterval(() => { if (!document.hidden) testAll(); }, 30000);
})();
