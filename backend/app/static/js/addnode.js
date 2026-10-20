/* Asistente «Agregar nodo» (solo administradores). */
"use strict";

const AddNode = (() => {
    const modal = document.getElementById("add-node-modal");
    if (!modal) return { onNode() {} };

    const form = document.getElementById("an-form");
    const macInput = document.getElementById("an-mac");
    const nextBtn = document.getElementById("an-next");
    const backBtn = document.getElementById("an-back");
    const errorBox = document.getElementById("an-error");
    let step = 1;
    let created = null;      // {node, credentials}
    let connected = false;

    const NEXT_LABEL = { 1: "Registrar y generar clave", 2: "Ya lo pegué, continuar", 3: "Ir al nodo" };

    function normalizeMac(value) {
        const hex = value.replace(/[^0-9a-fA-F]/g, "").toLowerCase();
        return hex.length === 12 ? hex : null;
    }

    function setStep(n) {
        step = n;
        modal.querySelector(".modal-body").scrollTop = 0;
        for (const s of modal.querySelectorAll(".wizard-step")) s.classList.toggle("active", Number(s.dataset.step) === n);
        for (const s of modal.querySelectorAll(".st")) {
            const i = Number(s.dataset.st);
            s.classList.toggle("active", i === n);
            s.classList.toggle("done", i < n);
        }
        for (const b of modal.querySelectorAll(".bar")) b.classList.toggle("done", Number(b.dataset.bar) < n);
        backBtn.classList.toggle("hidden", n !== 3);
        nextBtn.replaceChildren(NEXT_LABEL[n] + " ", App.icon("chevron"));
        nextBtn.disabled = n === 3 && !connected;
    }

    function reset() {
        form.reset();
        created = null;
        connected = false;
        macInput.classList.remove("valid", "invalid");
        errorBox.classList.add("hidden");
        document.getElementById("an-waiting").classList.remove("hidden");
        document.getElementById("an-success").classList.add("hidden");
        document.getElementById("an-ssid").value = "";
        document.getElementById("an-wifipass").value = "";
        setStep(1);
    }

    async function open() {
        reset();
        modal.showModal();
        macInput.focus();
        try {
            const [zones, info] = await Promise.all([App.api("/api/zones"), App.api("/api/provisioning")]);
            document.getElementById("an-zones").replaceChildren(...zones.map(z => new Option(z, z)));
            if (info.mqtt_host) document.getElementById("an-host").value = info.mqtt_host;
            if (info.mqtt_port) document.getElementById("an-port").value = info.mqtt_port;
        } catch (_) { /* opcional */ }
    }

    function provisionLine() {
        if (!created) return "";
        return JSON.stringify({
            cmd: "provision",
            wifi_ssid: document.getElementById("an-ssid").value,
            wifi_pass: document.getElementById("an-wifipass").value,
            mqtt_host: document.getElementById("an-host").value.trim(),
            mqtt_port: Number(document.getElementById("an-port").value) || 8883,
            mqtt_tls: true,
            mqtt_pass: created.credentials.password,
        });
    }

    function refreshLine() {
        document.getElementById("an-line").textContent = provisionLine();
    }

    async function submit() {
        const data = App.formToObject(form);
        const mac = normalizeMac(data.mac);
        if (!mac) {
            macInput.classList.add("invalid");
            macInput.focus();
            return;
        }
        if (!data.name.trim()) {
            form.name.focus();
            form.name.classList.add("invalid");
            return;
        }
        nextBtn.classList.add("loading");
        errorBox.classList.add("hidden");
        try {
            created = await App.api("/api/devices", { method: "POST", body: { ...data, mac } });
            document.getElementById("an-user").textContent = created.credentials.username;
            document.getElementById("an-pass").textContent = created.credentials.password;
            const warn = document.getElementById("an-sync-warning");
            const c = created.credentials;
            const problems = [];
            if (!c.passwd_file_managed) problems.push("Este servidor no administra el archivo de claves de Mosquitto (MQTT_PASSWD_FILE vacío): la clave queda registrada pero el broker no la conocerá hasta que lo configures.");
            if (c.passwd_sync_error) problems.push(`No se pudo actualizar Mosquitto: ${c.passwd_sync_error}`);
            warn.textContent = problems.join(" ");
            warn.classList.toggle("hidden", problems.length === 0);
            refreshLine();
            setStep(2);
            document.getElementById("an-ssid").focus();
            App.toast(`Nodo «${created.node.name}» registrado`);
        } catch (err) {
            errorBox.textContent = err.message;
            errorBox.classList.remove("hidden");
        } finally {
            nextBtn.classList.remove("loading");
        }
    }

    function markConnected() {
        if (!created || connected) return;
        connected = true;
        document.getElementById("an-ok-name").textContent = created.node.name;
        document.getElementById("an-waiting").classList.add("hidden");
        document.getElementById("an-success").classList.remove("hidden");
        nextBtn.disabled = false;
    }

    macInput.addEventListener("input", () => {
        const ok = normalizeMac(macInput.value) !== null;
        macInput.classList.toggle("valid", ok);
        macInput.classList.toggle("invalid", !ok && macInput.value.length >= 12);
        document.getElementById("an-mac-help").textContent = ok
            ? `Se registrará como ${normalizeMac(macInput.value)}`
            : "12 dígitos hexadecimales (0-9, A-F).";
    });
    form.name.addEventListener("input", () => form.name.classList.remove("invalid"));
    form.addEventListener("submit", (ev) => { ev.preventDefault(); submit(); });
    for (const id of ["an-ssid", "an-wifipass", "an-host", "an-port"]) {
        document.getElementById(id).addEventListener("input", refreshLine);
    }

    nextBtn.addEventListener("click", () => {
        if (step === 1) submit();
        else if (step === 2) {
            if (!document.getElementById("an-ssid").value || !document.getElementById("an-host").value.trim()) {
                App.toast("Completa el WiFi y la IP de la Pi para que la línea sirva", true);
                return;
            }
            document.getElementById("an-wait-name").textContent = created.node.name;
            setStep(3);
        } else if (step === 3 && created) {
            location.href = `/nodes/${created.node.mac}`;
        }
    });
    backBtn.addEventListener("click", () => setStep(step - 1 || 1));
    for (const b of modal.querySelectorAll("[data-close]")) b.addEventListener("click", () => modal.close());
    modal.addEventListener("close", () => {
        // La clave WiFi no se queda en el DOM.
        document.getElementById("an-wifipass").value = "";
        document.getElementById("an-line").textContent = "";
    });
    document.addEventListener("click", (ev) => {
        if (ev.target.closest("[data-open-add-node]")) open();
    });

    return {
        /** Avisa al asistente de cada actualización de nodo (WebSocket). */
        onNode(node) {
            if (created && node.mac === created.node.mac && node.connection === "online") markConnected();
        },
    };
})();
