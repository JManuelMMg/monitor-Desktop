/* Tarjeta de nodo del panel general: anillo de nivel, métricas y minigráfico. */
"use strict";

const NodeCard = (() => {
    const SPARK_POINTS = 40;
    const SPARK_COLOR = getComputedStyle(document.documentElement).getPropertyValue("--c-ch4").trim() || "#2dd4bf";
    const buffers = new Map();   // mac -> últimos valores de CH4

    function pushSample(mac, value) {
        const buf = buffers.get(mac) || [];
        buf.push(Number.isFinite(value) ? value : null);
        while (buf.length > SPARK_POINTS) buf.shift();
        buffers.set(mac, buf);
    }

    function seed(mac, values) {
        if (!buffers.has(mac) || buffers.get(mac).length < 3) buffers.set(mac, values.slice(-SPARK_POINTS));
    }

    function metric(name) {
        const m = App.METRIC[name];
        return App.el("div", { class: "m", "data-metric": name, "data-tip": m.label },
            App.icon(m.icon), App.el("span", { class: "m-val" }, App.el("span", { class: "v", text: "—" }), App.el("small", { text: m.unit })));
    }

    function create(node) {
        const ring = App.ring();
        const card = App.el("a", { class: "card node-card", href: `/nodes/${node.mac}` },
            App.el("div", { class: "node-top" },
                App.el("div", {},
                    App.el("h2", { class: "node-name" }),
                    App.el("div", { class: "node-zone" }, App.icon("pin"), App.el("span", { class: "zone-text" }))),
                App.el("span", { class: "status node-conn" })),
            App.el("div", { class: "node-body" }, ring,
                App.el("div", { class: "node-metrics" }, ["temp_c", "hum_pct", "ch4_ppm", "co2_ppm"].map(metric))),
            App.el("div", { class: "node-spark", "data-tip": "CH₄ reciente" }),
            App.el("div", { class: "node-foot" },
                App.el("span", { class: "mac" }),
                App.el("span", { class: "signal" }, App.icon("wifi"), App.el("span", { class: "rssi" })),
                App.el("span", { class: "seen" })));
        card.ring = ring;
        update(card, node, false);
        return card;
    }

    function update(card, node, sample = true) {
        const t = node.telemetry || {};
        if (sample && node.telemetry) pushSample(node.mac, t.ch4_ppm);
        card.dataset.conn = node.first_connection_pending ? "pending" : node.connection;
        card.classList.toggle("alarm", node.alarms.length > 0);
        card.classList.toggle("disabled", !node.enabled);
        card.querySelector(".node-name").textContent = node.name;
        card.querySelector(".zone-text").textContent = node.zone || "Sin zona asignada";
        const status = card.querySelector(".node-conn");
        if (node.first_connection_pending) {
            status.className = "status pending node-conn";
            status.textContent = "Esperando conexión";
        } else {
            status.className = "status node-conn";
            App.setStatus(status, node.connection);
        }
        const over = new Set(node.alarms.map(a => a.metric));
        for (const box of card.querySelectorAll(".m")) {
            const name = box.dataset.metric;
            App.setText(box.querySelector(".v"), App.fmtMetric(name, t[name]));
            box.classList.toggle("over", over.has(name));
        }
        card.ring.update(t.level_pct, over.has("level_pct"));
        card.querySelector(".mac").textContent = node.mac_display;
        card.querySelector(".rssi").textContent = Number.isFinite(t.rssi) ? `${t.rssi} dBm` : "—";
        card.querySelector(".seen").textContent = App.timeAgo(node.last_seen);
        card.querySelector(".node-spark").innerHTML = App.sparkline(buffers.get(node.mac) || [], SPARK_COLOR);
    }

    function refreshTimes(card, node) {
        card.querySelector(".seen").textContent = App.timeAgo(node.last_seen);
    }

    return { create, update, seed, refreshTimes };
})();
