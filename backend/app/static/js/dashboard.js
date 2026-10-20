"use strict";

(() => {
    const nodes = new Map();
    const cards = new Map();
    const groupsBox = document.getElementById("node-groups");
    let zoneFilter = App.storage.get("zoneFilter") || "";
    let stateFilter = "";
    let search = "";
    let userCount = null;
    let renderQueued = false;
    const seeded = new Set();

    const zoneOf = (n) => n.zone || "Sin zona asignada";

    /** Coloca los hijos en orden moviendo solo los que cambiaron de sitio
     *  (mover un nodo del DOM reinicia sus animaciones). */
    function syncChildren(parent, wanted) {
        wanted.forEach((child, i) => {
            if (parent.children[i] !== child) parent.insertBefore(child, parent.children[i] || null);
        });
        while (parent.children.length > wanted.length) parent.lastElementChild.remove();
    }

    // ---------- filtros ----------
    function matches(node) {
        if (zoneFilter && zoneOf(node) !== zoneFilter) return false;
        if (stateFilter === "alarm" && !node.alarms.length) return false;
        if (stateFilter === "offline" && node.connection === "online") return false;
        if (search) {
            const hay = `${node.name} ${node.zone || ""} ${node.mac} ${node.mac_display}`.toLowerCase();
            if (!hay.includes(search)) return false;
        }
        return true;
    }

    function renderZoneChips() {
        const counts = new Map();
        for (const n of nodes.values()) counts.set(zoneOf(n), (counts.get(zoneOf(n)) || 0) + 1);
        const zones = [...counts.keys()].sort((a, b) => a.localeCompare(b, "es"));
        if (zoneFilter && !counts.has(zoneFilter)) zoneFilter = "";
        const chip = (value, label, count) => App.el("button",
            { class: `chip ${zoneFilter === value ? "active" : ""}`, type: "button", "data-zone": value },
            value ? App.icon("pin") : null, label, App.el("span", { class: "count", text: String(count) }));
        document.getElementById("zone-chips").replaceChildren(
            chip("", "Todas las zonas", nodes.size), ...zones.map(z => chip(z, z, counts.get(z))));
    }

    // ---------- tarjetas por zona ----------
    function render() {
        renderQueued = false;
        const visible = [...nodes.values()].filter(matches)
            .sort((a, b) => zoneOf(a).localeCompare(zoneOf(b), "es") || a.name.localeCompare(b.name, "es"));
        const byZone = new Map();
        for (const n of visible) {
            if (!byZone.has(zoneOf(n))) byZone.set(zoneOf(n), []);
            byZone.get(zoneOf(n)).push(n);
        }
        const existingGroups = new Map([...groupsBox.children].map(g => [g.dataset.zone, g]));
        const order = [];
        let index = 0;
        for (const [zone, list] of byZone) {
            let group = existingGroups.get(zone);
            if (!group) {
                group = App.el("section", { class: "zone-group", "data-zone": zone },
                    App.el("div", { class: "zone-title" }, App.icon("pin"), App.el("span", { class: "zone-name", text: zone }),
                        App.el("span", { class: "zone-count" }), App.el("span", { class: "line" })),
                    App.el("div", { class: "node-grid" }));
            }
            group.querySelector(".zone-count").textContent = `· ${list.length}`;
            const grid = group.querySelector(".node-grid");
            const wanted = list.map(node => {
                let card = cards.get(node.mac);
                if (!card) {
                    card = NodeCard.create(node);
                    card.style.setProperty("--i", index++);
                    card.classList.add("reveal");
                    card.addEventListener("animationend", (ev) => {
                        if (ev.animationName === "fade-up") card.classList.remove("reveal");
                    });
                    cards.set(node.mac, card);
                }
                return card;
            });
            syncChildren(grid, wanted);
            order.push(group);
        }
        syncChildren(groupsBox, order);
        for (const [mac, card] of cards) {
            if (!nodes.has(mac)) { card.remove(); cards.delete(mac); }
        }
        document.getElementById("empty-state").classList.toggle("hidden", nodes.size > 0);
        document.getElementById("no-match").classList.toggle("hidden", nodes.size === 0 || visible.length > 0);
        renderZoneChips();
        renderSummary();
    }

    function scheduleRender() {
        if (!renderQueued) {
            renderQueued = true;
            requestAnimationFrame(render);
        }
    }

    // ---------- KPI, alarmas y guía ----------
    function average(metric) {
        const values = [...nodes.values()]
            .filter(n => n.enabled && n.connection === "online")
            .map(n => n.telemetry?.[metric]).filter(Number.isFinite);
        return values.length ? values.reduce((a, b) => a + b, 0) / values.length : NaN;
    }

    function renderSummary() {
        const list = [...nodes.values()];
        const online = list.filter(n => n.connection === "online").length;
        const alarmed = list.filter(n => n.alarms.length);
        document.getElementById("kpi-online").textContent = `${online} / ${list.length}`;
        App.countTo(document.getElementById("kpi-alarms"), alarmed.length);
        document.getElementById("kpi-alarm-card").classList.toggle("active", alarmed.length > 0);
        App.countTo(document.getElementById("kpi-temp"), average("temp_c"), 1, " °C");
        App.countTo(document.getElementById("kpi-ch4"), average("ch4_ppm"), 0, " ppm");
        const last = list.map(n => n.last_seen).filter(Boolean).sort().pop();
        document.getElementById("kpi-last").textContent = last ? App.timeAgo(last) : "—";

        const banner = document.getElementById("alarm-banner");
        document.getElementById("alarm-text").textContent = alarmed.map(n => `${n.name}: ${App.alarmText(n)}`).join("   |   ");
        banner.classList.toggle("hidden", alarmed.length === 0);
        updateGuide();
    }

    function updateGuide() {
        const list = [...nodes.values()];
        const done = {
            nodes: list.length > 0,
            online: list.some(n => n.last_seen),
            zones: list.length > 0 && list.every(n => n.zone),
            calibrated: list.length > 0 && list.every(n => !n.telemetry || n.telemetry.mq_cal),
            users: userCount !== null ? userCount > 1 : App.role() !== "admin",
        };
        let count = 0;
        for (const step of document.querySelectorAll("#guide-steps .step")) {
            const ok = Boolean(done[step.dataset.step]);
            step.classList.toggle("done", ok);
            count += ok;
        }
        const total = Object.keys(done).length;
        document.getElementById("guide-bar").style.width = `${(count / total) * 100}%`;
        document.getElementById("guide-summary").textContent = count === total
            ? "¡Todo listo! Puedes ocultar esta guía."
            : `${count} de ${total} pasos completados.`;
        const guide = document.getElementById("guide");
        const dismissed = App.storage.get("guideHidden") === "1";
        if (!guide.dataset.init) {
            guide.dataset.init = "1";
            guide.classList.toggle("hidden", dismissed || count === total);
            if (!guide.classList.contains("hidden")) App.stagger([guide]);
        }
    }

    // ---------- minigráficos iniciales ----------
    async function seedSparklines() {
        const pending = [...nodes.values()].filter(n => !seeded.has(n.mac) && n.registered);
        for (const node of pending) seeded.add(node.mac);
        const worker = async () => {
            while (pending.length) {
                const node = pending.shift();
                try {
                    const rows = await App.api(`/api/devices/${node.mac}/history?hours=2&points=40`);
                    NodeCard.seed(node.mac, rows.map(r => r.ch4_ppm));
                    const card = cards.get(node.mac);
                    if (card) NodeCard.update(card, nodes.get(node.mac), false);
                } catch (_) { /* sin histórico todavía */ }
            }
        };
        await Promise.all([worker(), worker(), worker()]);
    }

    // ---------- eventos ----------
    document.getElementById("zone-chips").addEventListener("click", (ev) => {
        const chip = ev.target.closest(".chip");
        if (!chip) return;
        zoneFilter = chip.dataset.zone;
        App.storage.set("zoneFilter", zoneFilter);
        render();
    });
    document.getElementById("state-chips").addEventListener("click", (ev) => {
        const chip = ev.target.closest(".chip");
        if (!chip) return;
        stateFilter = chip.dataset.state;
        for (const c of document.querySelectorAll("#state-chips .chip")) c.classList.toggle("active", c === chip);
        render();
    });
    document.getElementById("search").addEventListener("input", (ev) => {
        search = ev.target.value.trim().toLowerCase();
        render();
    });
    document.getElementById("toggle-guide").addEventListener("click", () => {
        const guide = document.getElementById("guide");
        guide.classList.toggle("hidden");
        App.storage.set("guideHidden", guide.classList.contains("hidden") ? "1" : "0");
        if (!guide.classList.contains("hidden")) guide.scrollIntoView({ behavior: "smooth", block: "nearest" });
    });
    document.getElementById("close-guide").addEventListener("click", () => {
        document.getElementById("guide").classList.add("hidden");
        App.storage.set("guideHidden", "1");
        App.toast("Guía oculta. Vuelve a abrirla con el botón «Guía».");
    });

    if (App.role() === "admin") {
        App.api("/api/users").then(users => { userCount = users.length; updateGuide(); }).catch(() => {});
    }

    App.connectLive((event) => {
        if (event.type === "hello") {
            nodes.clear();
            for (const n of event.nodes) nodes.set(n.mac, n);
            document.getElementById("broker-warning").classList.toggle("hidden", event.broker);
            render();
            seedSparklines();
        } else if (event.type === "node") {
            const isNew = !nodes.has(event.node.mac);
            nodes.set(event.node.mac, event.node);
            const card = cards.get(event.node.mac);
            if (card && !isNew) NodeCard.update(card, event.node);
            AddNode.onNode(event.node);
            scheduleRender();
            if (isNew) seedSparklines();
        } else if (event.type === "removed") {
            nodes.delete(event.mac);
            scheduleRender();
        } else if (event.type === "broker") {
            document.getElementById("broker-warning").classList.toggle("hidden", event.connected);
        }
    });

    setInterval(() => {
        for (const [mac, card] of cards) {
            const node = nodes.get(mac);
            if (node) NodeCard.refreshTimes(card, node);
        }
        const last = [...nodes.values()].map(n => n.last_seen).filter(Boolean).sort().pop();
        document.getElementById("kpi-last").textContent = last ? App.timeAgo(last) : "—";
    }, 5000);
})();
