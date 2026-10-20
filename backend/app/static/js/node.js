"use strict";

(() => {
    const root = document.getElementById("node-root");
    const mac = root.dataset.mac;
    const canOperate = root.dataset.canOperate === "1";
    const isAdmin = root.dataset.isAdmin === "1";
    const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    const COLORS = { temp: css("--c-temp"), hum: css("--c-hum"), ch4: css("--c-ch4"), co2: css("--c-co2"), level: css("--c-level") };
    const CMD_LABEL = {
        ping: "Ping", reboot: "Reinicio", identify: "Identificar", calibrate_mq4: "Calibrar MQ-4",
        clear_mq4: "Borrar R0", calibrate_co2_zero: "Cero CO₂",
    };

    let node = null;
    let history = [];
    let hours = 24;
    let chartsDrawn = false;
    const ring = App.ring("ring-lg");
    document.getElementById("level-ring").appendChild(ring);
    const metaForm = document.getElementById("meta-form");
    const thresholdForm = document.getElementById("threshold-form");
    const configForm = document.getElementById("config-form");

    if (!canOperate) {
        for (const form of [metaForm, thresholdForm, configForm]) {
            for (const field of form.elements) field.disabled = true;
        }
    }

    function fillForm(form, values) {
        for (const field of form.elements) {
            if (!field.name || !(field.name in values)) continue;
            if (field.type === "checkbox") field.checked = Boolean(values[field.name]);
            else field.value = values[field.name] ?? "";
        }
    }

    // ---------- cabecera y resumen ----------
    function healthItem(label, state, sub) {
        return App.el("div", { class: `health-item ${state}` }, App.el("span", { class: "dot" }), label,
            App.el("span", { class: "sub", text: sub }));
    }

    function render() {
        document.title = `${node.name} · Monitor multi-nodo`;
        const title = document.getElementById("node-title");
        title.classList.remove("skeleton");
        title.textContent = node.name;
        document.getElementById("node-zone").textContent = node.zone || "Sin zona asignada";
        document.getElementById("node-mac").textContent = node.mac_display;
        document.getElementById("node-fw").textContent = node.fw_version || "—";
        document.getElementById("node-ip").textContent = node.ip || "—";
        const status = document.getElementById("node-conn");
        if (node.first_connection_pending) {
            status.className = "status pending";
            status.textContent = "Esperando primera conexión";
        } else {
            status.className = "status";
            App.setStatus(status, node.connection);
        }
        document.getElementById("node-pending").classList.toggle("hidden", !node.first_connection_pending);
        document.getElementById("node-disabled").classList.toggle("hidden", node.enabled);
        document.getElementById("node-alarms").classList.toggle("hidden", !node.alarms.length);
        document.getElementById("node-alarm-text").textContent = node.alarms.length ? `Alarma: ${App.alarmText(node)}` : "";

        const t = node.telemetry || {};
        const over = new Set(node.alarms.map(a => a.metric));
        for (const tile of document.querySelectorAll("#live-metrics .tile")) {
            const metric = tile.dataset.metric;
            App.setText(tile.querySelector(".v"), App.fmtMetric(metric, t[metric]));
            tile.classList.toggle("over", over.has(metric));
        }
        ring.update(t.level_pct, over.has("level_pct"));
        let mq = "";
        if (t.mq_calibrating) mq = "Calibrando… (20 s)";
        else if (node.telemetry && !t.mq_warm) mq = "Calentando (3 min tras encender)";
        else if (node.telemetry && !t.mq_cal) mq = "Sin calibrar: ve a Acciones";
        document.getElementById("mq-note").textContent = mq;
        document.getElementById("last-update").textContent = node.telemetry_ts ? `Última lectura ${App.timeAgo(node.telemetry_ts)}` : "Sin lecturas aún";

        const has = Boolean(node.telemetry);
        document.getElementById("health").replaceChildren(
            healthItem("DHT11", !has ? "" : t.dht_ok ? "ok" : "bad", "temp./humedad"),
            healthItem("MQ-4", !has ? "" : t.mq_ok ? "ok" : (t.mq_warm === false || !t.mq_cal) ? "warn" : "bad", "metano"),
            healthItem("MH-Z19C", !has ? "" : t.co2_ok ? "ok" : "bad", "CO₂"),
            healthItem("AJ-SR04M", !has ? "" : t.us_ok ? "ok" : "bad", "nivel"),
            healthItem("WiFi", !has ? "" : (t.rssi ?? -100) > -75 ? "ok" : "warn", Number.isFinite(t.rssi) ? `${t.rssi} dBm` : "—"),
        );

        const sync = document.getElementById("config-sync");
        sync.className = "status";
        if (node.config_state?.error) { sync.classList.add("bad"); sync.textContent = "Rechazada por el nodo"; }
        else if (!node.config_state) { sync.classList.add("pending"); sync.textContent = "Sin respuesta del nodo"; }
        else if (node.config_pending) { sync.classList.add("pending"); sync.textContent = `Pendiente · rev ${node.config.rev}`; }
        else { sync.classList.add("online"); sync.textContent = `Aplicada · rev ${node.config.rev}`; }
        const configError = document.getElementById("config-error");
        configError.textContent = node.config_state?.error ? `El nodo rechazó la configuración: ${node.config_state.error}` : "";
        configError.classList.toggle("hidden", !node.config_state?.error);

        document.getElementById("toggle-enabled").replaceChildren(App.icon("power"), node.enabled ? " Deshabilitar" : " Habilitar");
        const credStatus = document.getElementById("cred-status");
        credStatus.className = `status ${node.has_credentials ? "online" : "bad"}`;
        credStatus.textContent = node.has_credentials ? "Activas" : "Sin credencial";
        document.getElementById("cred-user").textContent = node.mac;
        document.getElementById("cred-date").textContent = App.dateTime(node.credentials_issued_at);
        document.getElementById("revoke-cred").disabled = !node.has_credentials;

        for (const btn of document.querySelectorAll("[data-cmd], #quick-identify")) {
            btn.disabled = !canOperate || node.connection === "offline";
        }
    }

    function fillForms() {
        fillForm(metaForm, { name: node.name, zone: node.zone || "", description: node.description || "" });
        fillForm(thresholdForm, node.thresholds);
        fillForm(configForm, node.config);
    }

    // ---------- histórico ----------
    const series = (key) => history.map(r => ({ t: Date.parse(r.ts), v: r[key] }));

    function drawCharts(animate) {
        const opts = (decimals) => ({ decimals, animate });
        LineChart.draw(document.getElementById("chart-env"), [
            { label: "Temp. °C", color: COLORS.temp, points: series("temp_c") },
            { label: "Humedad %", color: COLORS.hum, points: series("hum_pct") },
        ], opts(1));
        LineChart.draw(document.getElementById("chart-ch4"), [{ label: "CH₄", color: COLORS.ch4, points: series("ch4_ppm") }], opts(0));
        LineChart.draw(document.getElementById("chart-co2"), [{ label: "CO₂", color: COLORS.co2, points: series("co2_ppm") }], opts(0));
        LineChart.draw(document.getElementById("chart-level"), [{ label: "Nivel", color: COLORS.level, points: series("level_pct") }], opts(1));
        chartsDrawn = true;
    }

    async function loadHistory(animate = true) {
        document.getElementById("export-link").href = `/api/devices/${mac}/export.csv?hours=${hours}`;
        try {
            history = await App.api(`/api/devices/${mac}/history?hours=${hours}&points=400`);
            if (!document.querySelector('[data-panel="historico"]').classList.contains("hidden")) drawCharts(animate);
            else chartsDrawn = false;
        } catch (err) {
            App.toast(`Histórico: ${err.message}`, true);
        }
    }

    async function loadCommands() {
        const rows = await App.api(`/api/devices/${mac}/commands?limit=15`);
        const tbody = document.querySelector("#command-log tbody");
        if (!rows.length) {
            tbody.replaceChildren(App.el("tr", {}, App.el("td", { colspan: "4", class: "muted", text: "Todavía no se han enviado comandos a este nodo." })));
            return;
        }
        tbody.replaceChildren(...rows.map(r => {
            const result = r.ok === null
                ? App.el("span", { class: "status pending", text: "esperando" })
                : App.el("span", {}, App.el("span", { class: `status ${r.ok ? "online" : "bad"}`, text: r.ok ? "OK" : "Error" }), ` ${r.response || ""}`);
            return App.el("tr", {},
                App.el("td", { text: App.dateTime(r.sent_at) }), App.el("td", { text: r.username || "—" }),
                App.el("td", { text: CMD_LABEL[r.cmd] || r.cmd }), App.el("td", {}, result));
        }));
    }

    // ---------- acciones ----------
    async function patch(body, okMessage, button) {
        button?.classList.add("loading");
        try {
            node = await App.api(`/api/devices/${mac}`, { method: "PATCH", body });
            render();
            fillForms();
            App.toast(okMessage);
        } catch (err) {
            App.toast(err.message, true);
        } finally {
            button?.classList.remove("loading");
        }
    }

    metaForm.addEventListener("submit", (ev) => {
        ev.preventDefault();
        const v = App.formToObject(metaForm);
        patch({ name: v.name, zone: v.zone, description: v.description }, "Nombre y ubicación guardados", ev.submitter);
    });
    thresholdForm.addEventListener("submit", (ev) => {
        ev.preventDefault();
        patch({ thresholds: App.formToObject(thresholdForm) }, "Umbrales guardados", ev.submitter);
    });
    configForm.addEventListener("submit", async (ev) => {
        ev.preventDefault();
        ev.submitter?.classList.add("loading");
        try {
            const res = await App.api(`/api/devices/${mac}/config`, { method: "PUT", body: App.formToObject(configForm) });
            node = res.node;
            render();
            App.toast(res.published ? "Configuración enviada; esperando confirmación del nodo" : "Guardada; se enviará cuando el broker esté disponible");
        } catch (err) {
            App.toast(err.message, true);
        } finally {
            ev.submitter?.classList.remove("loading");
        }
    });

    async function sendCommand(cmd, button) {
        const body = { cmd };
        if (cmd === "identify") body.seconds = 15;
        button?.classList.add("loading");
        try {
            await App.api(`/api/devices/${mac}/commands`, { method: "POST", body });
            App.toast(`${CMD_LABEL[cmd]}: enviado, esperando respuesta…`);
            loadCommands().catch(() => {});
        } catch (err) {
            App.toast(err.message, true);
        } finally {
            button?.classList.remove("loading");
        }
    }

    for (const btn of document.querySelectorAll("[data-cmd]")) {
        btn.addEventListener("click", () => {
            if (btn.dataset.confirm && !confirm(btn.dataset.confirm)) return;
            sendCommand(btn.dataset.cmd, btn);
        });
    }
    document.getElementById("quick-identify").addEventListener("click", (ev) => sendCommand("identify", ev.currentTarget));

    document.getElementById("toggle-enabled").addEventListener("click", (ev) => {
        if (isAdmin) patch({ enabled: !node.enabled }, node.enabled ? "Nodo deshabilitado" : "Nodo habilitado", ev.currentTarget);
    });
    document.getElementById("delete-node").addEventListener("click", async () => {
        if (!isAdmin) return;
        if (prompt(`Esto borra el nodo, su histórico y su credencial.\nEscribe el nombre del nodo (${node.name}) para confirmar:`) !== node.name) return;
        try {
            await App.api(`/api/devices/${mac}`, { method: "DELETE" });
            location.href = "/";
        } catch (err) {
            App.toast(err.message, true);
        }
    });
    document.getElementById("rotate-cred").addEventListener("click", async (ev) => {
        const button = ev.currentTarget;
        if (!confirm("La clave actual dejará de funcionar y el nodo se desconectará hasta que le cargues la nueva. ¿Continuar?")) return;
        button.classList.add("loading");
        try {
            const res = await App.api(`/api/devices/${mac}/credentials`, { method: "POST" });
            node = res.node;
            render();
            document.getElementById("cred-pass").textContent = res.credentials.password;
            document.getElementById("cred-new").classList.remove("hidden");
            App.toast("Clave nueva generada");
        } catch (err) {
            App.toast(err.message, true);
        } finally {
            button.classList.remove("loading");
        }
    });
    document.getElementById("revoke-cred").addEventListener("click", async () => {
        if (!confirm("El nodo no podrá volver a conectarse hasta que generes una clave nueva. ¿Revocar?")) return;
        try {
            await App.api(`/api/devices/${mac}/credentials`, { method: "DELETE" });
            node = await App.api(`/api/devices/${mac}`);
            render();
            document.getElementById("cred-new").classList.add("hidden");
            App.toast("Credencial revocada");
        } catch (err) {
            App.toast(err.message, true);
        }
    });

    document.getElementById("range-picker").addEventListener("click", (ev) => {
        const b = ev.target.closest("button");
        if (!b) return;
        hours = Number(b.dataset.hours);
        for (const x of document.querySelectorAll("#range-picker button")) x.classList.toggle("active", x === b);
        loadHistory();
    });
    let resizeTimer = null;
    window.addEventListener("resize", () => {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(() => chartsDrawn && drawCharts(false), 150);
    });

    // ---------- arranque ----------
    (async () => {
        try {
            node = await App.api(`/api/devices/${mac}`);
        } catch (err) {
            document.getElementById("node-title").textContent = "Nodo no encontrado";
            document.getElementById("node-title").classList.remove("skeleton");
            App.toast(err.message, true);
            return;
        }
        App.tabs(document.getElementById("node-tabs"), (tab) => {
            if (tab === "historico" && !chartsDrawn) requestAnimationFrame(() => drawCharts(true));
        });
        render();
        fillForms();
        App.api("/api/zones").then(zones => {
            document.getElementById("zone-list").replaceChildren(...zones.map(z => new Option(z, z)));
        }).catch(() => {});
        loadHistory();
        loadCommands().catch(() => {});
        setInterval(() => { if (hours <= 24) loadHistory(false); }, 60000);

        App.connectLive((event) => {
            if (event.type === "node" && event.node.mac === mac) {
                node = event.node;
                render();
            } else if (event.type === "removed" && event.mac === mac) {
                location.href = "/";
            } else if (event.type === "ack" && event.mac === mac) {
                App.toast(`${CMD_LABEL[event.cmd] || event.cmd}: ${event.ok ? "OK" : "falló"} — ${event.msg}`, !event.ok);
                setTimeout(() => loadCommands().catch(() => {}), 1500);
            } else if (event.type === "event" && event.mac === mac && event.event.type === "mq4_calibration") {
                const e = event.event;
                App.toast(e.ok ? `MQ-4 calibrado: R0 = ${App.fmt(e.r0_kohm, 3)} kΩ` : `Calibración MQ-4 fallida: ${e.msg}`, !e.ok);
                setTimeout(() => loadCommands().catch(() => {}), 1500);
            }
        });
    })();
})();
