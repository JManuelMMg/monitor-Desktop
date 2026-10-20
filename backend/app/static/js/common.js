/* Utilidades compartidas de la interfaz. Sin dependencias externas. */
"use strict";

const App = (() => {
    const CONN_LABEL = { online: "En línea", stale: "Sin datos", offline: "Desconectado" };
    const METRIC = {
        temp_c: { label: "Temperatura", unit: "°C", decimals: 1, icon: "temp" },
        hum_pct: { label: "Humedad", unit: "%", decimals: 1, icon: "drop" },
        ch4_ppm: { label: "Metano CH₄", unit: "ppm", decimals: 0, icon: "flame" },
        co2_ppm: { label: "CO₂", unit: "ppm", decimals: 0, icon: "cloud" },
        level_pct: { label: "Nivel", unit: "%", decimals: 1, icon: "level" },
        dist_cm: { label: "Distancia", unit: "cm", decimals: 1, icon: "level" },
        rssi: { label: "Señal", unit: "dBm", decimals: 0, icon: "wifi" },
    };
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    // ---------- API ----------
    function formatDetail(detail) {
        if (Array.isArray(detail)) {
            return detail.map(d => `${(d.loc || []).slice(1).join(".") || "dato"}: ${d.msg}`).join("; ");
        }
        return detail || "Error";
    }

    async function api(path, { method = "GET", body } = {}) {
        const opts = { method, headers: {}, credentials: "same-origin" };
        if (method !== "GET") opts.headers["X-CSRF"] = "1";
        if (body !== undefined) {
            opts.headers["Content-Type"] = "application/json";
            opts.body = JSON.stringify(body);
        }
        let res;
        try {
            res = await fetch(path, opts);
        } catch (_) {
            throw new Error("No hay conexión con el servidor");
        }
        if (res.status === 401 && path !== "/api/auth/login") {
            location.href = "/login";
            throw new Error("Sesión expirada");
        }
        if (!res.ok) {
            let detail = res.statusText;
            try { detail = formatDetail((await res.json()).detail); } catch (_) { /* sin cuerpo JSON */ }
            throw new Error(detail);
        }
        return res.status === 204 ? null : res.json();
    }

    // ---------- elementos ----------
    function icon(name, cls = "") {
        const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
        svg.setAttribute("class", `ic ${cls}`.trim());
        svg.setAttribute("aria-hidden", "true");
        const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
        use.setAttribute("href", `#i-${name}`);
        svg.appendChild(use);
        return svg;
    }

    function el(tag, attrs = {}, ...children) {
        const node = document.createElement(tag);
        for (const [key, value] of Object.entries(attrs)) {
            if (value === undefined || value === null || value === false) continue;
            if (key === "class") node.className = value;
            else if (key === "text") node.textContent = value;
            else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
            else node.setAttribute(key, value === true ? "" : value);
        }
        for (const child of children.flat()) {
            if (child === null || child === undefined || child === false) continue;
            node.appendChild(typeof child === "string" ? document.createTextNode(child) : child);
        }
        return node;
    }

    // ---------- avisos ----------
    function toast(message, isError = false) {
        const box = document.getElementById("toasts");
        if (!box) return;
        const item = el("div", { class: `toast ${isError ? "error" : ""}` }, icon(isError ? "alert" : "check"), el("span", { text: message }));
        box.appendChild(item);
        setTimeout(() => {
            item.classList.add("leaving");
            item.addEventListener("animationend", () => item.remove(), { once: true });
        }, isError ? 7000 : 4000);
    }

    // ---------- formato ----------
    function fmt(value, decimals = 1) {
        if (value === null || value === undefined || value === "" || !Number.isFinite(Number(value))) return "—";
        return Number(value).toLocaleString("es", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
    }

    function fmtMetric(metric, value) {
        return fmt(value, METRIC[metric]?.decimals ?? 1);
    }

    function timeAgo(iso) {
        if (!iso) return "nunca";
        const seconds = Math.max(0, Math.round((Date.now() - Date.parse(iso)) / 1000));
        if (seconds < 5) return "ahora";
        if (seconds < 60) return `hace ${seconds} s`;
        if (seconds < 3600) return `hace ${Math.round(seconds / 60)} min`;
        if (seconds < 86400) return `hace ${Math.round(seconds / 3600)} h`;
        return `hace ${Math.round(seconds / 86400)} d`;
    }

    function dateTime(iso) {
        return iso ? new Date(iso).toLocaleString("es") : "—";
    }

    function alarmText(node) {
        return node.alarms.map(a => {
            const m = METRIC[a.metric] || { label: a.metric, unit: "" };
            return `${m.label} ${fmtMetric(a.metric, a.value)} ${m.unit} (límite ${fmtMetric(a.metric, a.limit)})`;
        }).join(" · ");
    }

    function setStatus(node, connection) {
        node.classList.remove("online", "stale", "offline", "pending", "alarm");
        node.classList.add(connection);
        node.textContent = CONN_LABEL[connection] || connection;
    }

    /** Cambia el texto y, si cambió, lo resalta brevemente. */
    function setText(node, text) {
        if (!node || node.textContent === text) return;
        const first = node.textContent === "" || node.textContent === "–";
        node.textContent = text;
        if (!first && !reducedMotion) {
            node.classList.remove("bump");
            void node.offsetWidth;
            node.classList.add("bump");
        }
    }

    /** Animación de conteo para números de KPI. */
    function countTo(node, target, decimals = 0, suffix = "") {
        if (!Number.isFinite(target)) { node.textContent = "—"; return; }
        const from = Number(node.dataset.value ?? 0);
        node.dataset.value = target;
        if (reducedMotion || from === target) {
            node.textContent = fmt(target, decimals) + suffix;
            return;
        }
        const start = performance.now();
        const dur = 700;
        const step = (now) => {
            const t = Math.min(1, (now - start) / dur);
            const eased = 1 - Math.pow(1 - t, 3);
            node.textContent = fmt(from + (target - from) * eased, decimals) + suffix;
            if (t < 1) requestAnimationFrame(step);
        };
        requestAnimationFrame(step);
    }

    /** Entrada escalonada: cada elemento recibe --i y la clase reveal. */
    function stagger(nodes) {
        [...nodes].forEach((node, i) => {
            node.style.setProperty("--i", node.dataset.i ?? i);
            node.classList.add("reveal");
        });
    }

    function formToObject(form) {
        const out = {};
        for (const field of form.elements) {
            if (!field.name) continue;
            if (field.type === "checkbox") out[field.name] = field.checked;
            else if (field.type === "number") out[field.name] = field.value === "" ? null : Number(field.value);
            else out[field.name] = field.value;
        }
        return out;
    }

    // ---------- gráficos SVG pequeños ----------
    function ring(sizeClass = "") {
        const r = 40, c = 2 * Math.PI * r;
        const wrap = el("div", { class: `ring ${sizeClass}` });
        wrap.innerHTML = `<svg viewBox="0 0 100 100"><circle class="ring-bg" cx="50" cy="50" r="${r}"/>` +
            `<circle class="ring-fg" cx="50" cy="50" r="${r}" stroke-dasharray="${c}" stroke-dashoffset="${c}"/></svg>` +
            `<div class="ring-label"><b>—</b><span>nivel</span></div>`;
        wrap.update = (pct, over = false) => {
            const valid = Number.isFinite(pct);
            const value = valid ? Math.max(0, Math.min(100, pct)) : 0;
            wrap.querySelector(".ring-fg").style.strokeDashoffset = String(c * (1 - value / 100));
            setText(wrap.querySelector("b"), valid ? `${fmt(value, 0)}%` : "—");
            wrap.classList.toggle("over", over);
        };
        return wrap;
    }

    function sparkline(values, color) {
        const pts = values.map((v, i) => [i, v]).filter(([, v]) => Number.isFinite(v));
        if (pts.length < 2) return '<svg viewBox="0 0 100 30" preserveAspectRatio="none"></svg>';
        const min = Math.min(...pts.map(p => p[1])), max = Math.max(...pts.map(p => p[1]));
        const span = max - min || 1;
        const n = values.length - 1 || 1;
        const xy = pts.map(([i, v]) => [(i / n) * 100, 27 - ((v - min) / span) * 24]);
        const line = xy.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(2)},${y.toFixed(2)}`).join(" ");
        const area = `${line} L${xy[xy.length - 1][0].toFixed(2)},30 L${xy[0][0].toFixed(2)},30 Z`;
        const id = `g${Math.random().toString(36).slice(2, 8)}`;
        return `<svg viewBox="0 0 100 30" preserveAspectRatio="none"><defs><linearGradient id="${id}" x1="0" x2="0" y1="0" y2="1">` +
            `<stop offset="0" stop-color="${color}" stop-opacity=".35"/><stop offset="1" stop-color="${color}" stop-opacity="0"/></linearGradient></defs>` +
            `<path d="${area}" fill="url(#${id})"/><path d="${line}" fill="none" stroke="${color}" stroke-width="1.6" vector-effect="non-scaling-stroke"/></svg>`;
    }

    // ---------- pestañas ----------
    function tabs(container, onChange) {
        const buttons = [...container.querySelectorAll(".tab")];
        const ink = el("span", { class: "tab-ink" });
        container.appendChild(ink);
        const select = (name, push = true) => {
            const button = buttons.find(b => b.dataset.tab === name) || buttons[0];
            for (const b of buttons) b.classList.toggle("active", b === button);
            for (const panel of document.querySelectorAll("[data-panel]")) {
                panel.classList.toggle("hidden", panel.dataset.panel !== button.dataset.tab);
            }
            ink.style.left = `${button.offsetLeft}px`;
            ink.style.width = `${button.offsetWidth}px`;
            if (push) history.replaceState(null, "", `#${button.dataset.tab}`);
            onChange?.(button.dataset.tab);
        };
        buttons.forEach(b => b.addEventListener("click", () => select(b.dataset.tab)));
        window.addEventListener("resize", () => {
            const active = buttons.find(b => b.classList.contains("active"));
            if (active) { ink.style.left = `${active.offsetLeft}px`; ink.style.width = `${active.offsetWidth}px`; }
        });
        window.addEventListener("hashchange", () => select(location.hash.slice(1), false));
        select(location.hash.slice(1) || buttons[0].dataset.tab, false);
        return select;
    }

    // ---------- tiempo real ----------
    function connectLive(onEvent) {
        const label = document.getElementById("link-state");
        const dot = document.getElementById("live-dot");
        let delay = 1000;
        let pingTimer = null;

        const setState = (on) => {
            if (label) label.textContent = on ? "En vivo" : "Reconectando…";
            if (dot) dot.classList.toggle("on", on);
            // netlink.js escucha este evento para la conmutación LAN ↔ VPN.
            document.dispatchEvent(new CustomEvent("live-state", { detail: on }));
        };

        const open = () => {
            const proto = location.protocol === "https:" ? "wss" : "ws";
            const ws = new WebSocket(`${proto}://${location.host}/ws`);
            ws.onopen = () => {
                delay = 1000;
                setState(true);
                pingTimer = setInterval(() => ws.readyState === 1 && ws.send("ping"), 25000);
            };
            ws.onmessage = (ev) => {
                try { onEvent(JSON.parse(ev.data)); } catch (err) { console.error(err); }
            };
            ws.onclose = (ev) => {
                clearInterval(pingTimer);
                setState(false);
                if (ev.code === 4401) { location.href = "/login"; return; }
                setTimeout(open, delay);
                delay = Math.min(delay * 2, 30000);
            };
        };
        open();
    }

    async function copyText(text) {
        try {
            await navigator.clipboard.writeText(text);
        } catch (_) {
            const area = el("textarea", {}, text);
            document.body.appendChild(area);
            area.select();
            document.execCommand("copy");
            area.remove();
        }
    }

    document.addEventListener("click", async (ev) => {
        const button = ev.target.closest("[data-copy]");
        if (!button) return;
        const source = document.getElementById(button.dataset.copy);
        if (!source || !source.textContent) return;
        await copyText(source.textContent);
        button.classList.add("copied");
        toast("Copiado al portapapeles");
        setTimeout(() => button.classList.remove("copied"), 1500);
    });

    document.addEventListener("DOMContentLoaded", () => {
        document.getElementById("logout-btn")?.addEventListener("click", async () => {
            try { await api("/api/auth/logout", { method: "POST" }); } finally { location.href = "/login"; }
        });
        const sidebar = document.getElementById("sidebar");
        document.getElementById("menu-btn")?.addEventListener("click", (ev) => {
            ev.stopPropagation();
            sidebar.classList.toggle("open");
        });
        document.addEventListener("click", (ev) => {
            if (sidebar?.classList.contains("open") && !sidebar.contains(ev.target)) sidebar.classList.remove("open");
        });
        stagger(document.querySelectorAll(".kpi, .page-head, [data-reveal]"));
    });

    return {
        api, toast, fmt, fmtMetric, timeAgo, dateTime, alarmText, setStatus, setText, countTo, stagger,
        formToObject, ring, sparkline, tabs, connectLive, copyText, icon, el, CONN_LABEL, METRIC, reducedMotion,
        role: () => document.body.dataset.role,
        storage: {
            get(key) { try { return localStorage.getItem(key); } catch (_) { return null; } },
            set(key, value) { try { localStorage.setItem(key, value); } catch (_) { /* sin storage */ } },
        },
    };
})();
