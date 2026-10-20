"use strict";

(() => {
    const ROLES = { viewer: "Solo lectura", operator: "Operador", admin: "Administrador" };
    const devices = new Map();

    const button = (iconName, text, cls, onClick, tip) =>
        App.el("button", { type: "button", class: `btn btn-sm ${cls}`, "data-tip": tip, onclick: onClick }, App.icon(iconName), text ? ` ${text}` : null);

    async function run(action, okMessage, reload) {
        try {
            await action();
            App.toast(okMessage);
        } catch (err) {
            App.toast(err.message, true);
        }
        await reload();
    }

    // ---------- usuarios ----------
    async function loadUsers() {
        const users = await App.api("/api/users");
        document.getElementById("user-count").textContent = `${users.length} en total`;
        const tbody = document.querySelector("#users-table tbody");
        tbody.replaceChildren(...users.map((u, i) => {
            const role = App.el("select", { "aria-label": `Rol de ${u.username}` },
                Object.entries(ROLES).map(([value, label]) => new Option(label, value, false, value === u.role)));
            role.addEventListener("change", () => run(
                () => App.api(`/api/users/${u.id}`, { method: "PATCH", body: { role: role.value } }),
                `${u.username} ahora es ${ROLES[role.value]}`, loadUsers));
            const row = App.el("tr", {},
                App.el("td", {}, App.el("span", { class: "side-user" }, App.el("span", { class: "avatar", text: u.username[0].toUpperCase() }), u.username)),
                App.el("td", {}, role),
                App.el("td", {}, App.el("span", { class: `status ${u.is_active ? "online" : "offline"}`, text: u.is_active ? "Activo" : "Inactivo" })),
                App.el("td", { class: "muted", text: u.last_login ? App.timeAgo(u.last_login) : "nunca" }),
                App.el("td", {}, App.el("div", { class: "actions" },
                    button(u.is_active ? "power" : "check", u.is_active ? "Desactivar" : "Activar", "btn-warn", () => run(
                        () => App.api(`/api/users/${u.id}`, { method: "PATCH", body: { is_active: !u.is_active } }),
                        `${u.username} ${u.is_active ? "desactivado" : "activado"}`, loadUsers)),
                    button("key", "", "", () => {
                        const password = prompt(`Nueva contraseña para ${u.username} (mín. 10 caracteres):`);
                        if (!password) return;
                        run(() => App.api(`/api/users/${u.id}`, { method: "PATCH", body: { password } }),
                            "Contraseña cambiada; sus sesiones se cerraron", loadUsers);
                    }, "Cambiar contraseña"),
                    button("trash", "", "btn-danger", () => {
                        if (!confirm(`¿Eliminar el usuario ${u.username}?`)) return;
                        run(() => App.api(`/api/users/${u.id}`, { method: "DELETE" }), `${u.username} eliminado`, loadUsers);
                    }, "Eliminar"))));
            row.style.setProperty("--i", i);
            row.classList.add("reveal");
            return row;
        }));
    }

    // ---------- nodos ----------
    function renderDevices() {
        const byZone = (n) => (n.zone ? `0${n.zone}` : "1");  // sin zona al final
        const list = [...devices.values()].sort((a, b) => byZone(a).localeCompare(byZone(b), "es") || a.name.localeCompare(b.name, "es"));
        document.getElementById("device-count").textContent = `${list.length} nodos`;
        const tbody = document.querySelector("#devices-table tbody");
        if (!list.length) {
            tbody.replaceChildren(App.el("tr", {}, App.el("td", { colspan: "7", class: "muted", text: "Sin nodos. Usa «Agregar nodo» para registrar el primero." })));
            return;
        }
        tbody.replaceChildren(...list.map(d => {
            const conn = App.el("span", { class: "status" });
            if (d.first_connection_pending) { conn.classList.add("pending"); conn.textContent = "Esperando"; }
            else App.setStatus(conn, d.connection);
            return App.el("tr", {},
                App.el("td", {}, App.el("a", { href: `/nodes/${d.mac}`, text: d.name })),
                App.el("td", { text: d.zone || "—" }),
                App.el("td", { class: "mono", text: d.mac_display }),
                App.el("td", {}, conn),
                App.el("td", { class: "mono", text: d.fw_version || "—" }),
                App.el("td", {}, App.el("span", { class: `status ${d.has_credentials ? "online" : "bad"}`, text: d.has_credentials ? "Activa" : "Revocada" })),
                App.el("td", {}, App.el("div", { class: "actions" },
                    button("power", d.enabled ? "Deshabilitar" : "Habilitar", "btn-warn", async () => {
                        try {
                            const updated = await App.api(`/api/devices/${d.mac}`, { method: "PATCH", body: { enabled: !d.enabled } });
                            devices.set(d.mac, updated);
                            renderDevices();
                        } catch (err) { App.toast(err.message, true); }
                    }),
                    App.el("a", { class: "btn btn-sm btn-ghost", href: `/nodes/${d.mac}#admin`, "data-tip": "Credenciales y más" }, App.icon("chevron")))));
        }));
    }

    // ---------- sistema ----------
    async function loadSystem() {
        const box = document.getElementById("system-health");
        try {
            const [health, info] = await Promise.all([fetch("/healthz").then(r => r.json()), App.api("/api/provisioning")]);
            const item = (label, ok, sub) => App.el("div", { class: `health-item ${ok ? "ok" : "bad"}` }, App.el("span", { class: "dot" }), label, App.el("span", { class: "sub", text: sub }));
            box.replaceChildren(
                item("Backend", true, "respondiendo"),
                item("Broker MQTT", health.mqtt, health.mqtt ? "conectado" : "sin conexión"),
                item("Base de datos", health.db, health.db ? "Neon OK" : "sin conexión (spool)"),
            );
            document.getElementById("prov-host").textContent = info.mqtt_host || "no configurada (MQTT_PUBLIC_HOST)";
            document.getElementById("prov-port").textContent = info.mqtt_port;
            document.getElementById("prov-managed").textContent = info.passwd_file_managed ? "lo mantiene el backend" : "no administrado (MQTT_PASSWD_FILE vacío)";
        } catch (err) {
            App.toast(err.message, true);
        }
    }

    document.getElementById("new-user-form").addEventListener("submit", async (ev) => {
        ev.preventDefault();
        const form = ev.target;
        const body = App.formToObject(form);
        ev.submitter?.classList.add("loading");
        try {
            await App.api("/api/users", { method: "POST", body });
            App.toast(`Usuario ${body.username} creado`);
            form.reset();
        } catch (err) {
            App.toast(err.message, true);
        } finally {
            ev.submitter?.classList.remove("loading");
        }
        loadUsers();
    });
    document.getElementById("refresh-health").addEventListener("click", loadSystem);

    App.tabs(document.getElementById("admin-tabs"), (tab) => { if (tab === "sistema") loadSystem(); });
    loadUsers().catch(err => App.toast(err.message, true));

    App.connectLive((event) => {
        if (event.type === "hello") {
            devices.clear();
            for (const n of event.nodes) devices.set(n.mac, n);
            renderDevices();
        } else if (event.type === "node") {
            // La telemetría llega a menudo: solo se redibuja si cambia algo de la tabla.
            const key = (n) => n && [n.name, n.zone, n.connection, n.fw_version, n.enabled, n.has_credentials, n.first_connection_pending].join("|");
            const changed = key(devices.get(event.node.mac)) !== key(event.node);
            devices.set(event.node.mac, event.node);
            AddNode.onNode(event.node);
            if (changed) renderDevices();
        } else if (event.type === "removed") {
            devices.delete(event.mac);
            renderDevices();
        }
    });
})();
