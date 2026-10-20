/* Gráfico de líneas en <canvas>, sin bibliotecas externas.
   series: [{ label, color, points: [{ t: msEpoch, v: number|null }] }]
   - Los null y los huecos largos cortan la línea.
   - animate: la línea se traza de izquierda a derecha.
   - Al pasar el ratón muestra hora y valores del punto más cercano. */
"use strict";

const LineChart = (() => {
    const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    function niceRange(min, max) {
        if (min === max) { min -= 1; max += 1; }
        const pad = (max - min) * 0.1;
        return [min - pad, max + pad];
    }

    function timeLabel(ms, spanMs) {
        const d = new Date(ms);
        if (spanMs > 2 * 86400000) return d.toLocaleDateString("es", { day: "2-digit", month: "2-digit" });
        if (spanMs < 15 * 60000) return d.toLocaleTimeString("es", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
        return d.toLocaleTimeString("es", { hour: "2-digit", minute: "2-digit" });
    }

    function alpha(hex, a) {
        const n = parseInt(hex.replace("#", ""), 16);
        return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${a})`;
    }

    function layout(canvas, series) {
        const dpr = window.devicePixelRatio || 1;
        const width = canvas.clientWidth;
        const height = Number(canvas.getAttribute("height")) || 200;
        canvas.style.height = `${height}px`;
        canvas.width = Math.round(width * dpr);
        canvas.height = Math.round(height * dpr);
        const all = series.flatMap(s => s.points.filter(p => p.v !== null && Number.isFinite(p.v)));
        if (!all.length) return { width, height, dpr, empty: true };
        const tMin = Math.min(...all.map(p => p.t));
        const tMax = Math.max(...all.map(p => p.t));
        const [vMin, vMax] = niceRange(Math.min(...all.map(p => p.v)), Math.max(...all.map(p => p.v)));
        const left = 50, right = 12, top = 24, bottom = 24;
        const plotW = Math.max(10, width - left - right);
        const plotH = Math.max(10, height - top - bottom);
        return {
            width, height, dpr, tMin, tMax, vMin, vMax, left, top, plotW, plotH,
            x: t => left + (tMax === tMin ? plotW / 2 : (t - tMin) / (tMax - tMin) * plotW),
            y: v => top + plotH - (v - vMin) / (vMax - vMin) * plotH,
        };
    }

    function paint(canvas, series, L, decimals, progress, hoverIndex) {
        const ctx = canvas.getContext("2d");
        ctx.setTransform(L.dpr, 0, 0, L.dpr, 0, 0);
        ctx.clearRect(0, 0, L.width, L.height);
        const muted = css("--muted") || "#8696aa";
        const grid = css("--border") || "#1f2e40";
        ctx.font = "11px system-ui, sans-serif";

        if (L.empty) {
            ctx.fillStyle = muted;
            ctx.textAlign = "center";
            ctx.fillText("Sin datos en este periodo", L.width / 2, L.height / 2);
            return;
        }

        // rejilla y ejes
        ctx.strokeStyle = grid;
        ctx.fillStyle = muted;
        ctx.lineWidth = 1;
        ctx.setLineDash([3, 4]);
        ctx.textAlign = "right";
        ctx.textBaseline = "middle";
        for (let i = 0; i <= 4; i++) {
            const v = L.vMin + (L.vMax - L.vMin) * i / 4;
            const yy = Math.round(L.y(v)) + 0.5;
            ctx.beginPath(); ctx.moveTo(L.left, yy); ctx.lineTo(L.left + L.plotW, yy); ctx.stroke();
            ctx.fillText(v.toLocaleString("es", { maximumFractionDigits: decimals }), L.left - 8, yy);
        }
        ctx.setLineDash([]);
        ctx.textAlign = "center";
        ctx.textBaseline = "top";
        const ticks = Math.max(2, Math.min(6, Math.floor(L.plotW / 95)));
        for (let i = 0; i <= ticks; i++) {
            const t = L.tMin + (L.tMax - L.tMin) * i / ticks;
            ctx.fillText(timeLabel(t, L.tMax - L.tMin), L.x(t), L.top + L.plotH + 7);
        }

        // series (recortadas según el progreso de la animación)
        ctx.save();
        ctx.beginPath();
        ctx.rect(0, 0, L.left + L.plotW * progress + 2, L.height);
        ctx.clip();
        for (const s of series) {
            const pts = s.points;
            const steps = [];
            for (let i = 1; i < pts.length; i++) steps.push(pts[i].t - pts[i - 1].t);
            steps.sort((a, b) => a - b);
            const gap = (steps[Math.floor(steps.length / 2)] || Infinity) * 3;
            const segments = [];
            let current = [];
            let prevT = null;
            for (const p of pts) {
                const valid = p.v !== null && Number.isFinite(p.v);
                if (!valid || (prevT !== null && p.t - prevT > gap)) {
                    if (current.length) segments.push(current);
                    current = [];
                }
                if (valid) { current.push(p); prevT = p.t; }
            }
            if (current.length) segments.push(current);

            const fill = ctx.createLinearGradient(0, L.top, 0, L.top + L.plotH);
            fill.addColorStop(0, alpha(s.color, series.length > 1 ? 0.12 : 0.28));
            fill.addColorStop(1, alpha(s.color, 0));
            for (const seg of segments) {
                ctx.beginPath();
                seg.forEach((p, i) => (i ? ctx.lineTo(L.x(p.t), L.y(p.v)) : ctx.moveTo(L.x(p.t), L.y(p.v))));
                ctx.strokeStyle = s.color;
                ctx.lineWidth = 2;
                ctx.lineJoin = "round";
                ctx.stroke();
                if (seg.length > 1) {
                    ctx.lineTo(L.x(seg[seg.length - 1].t), L.top + L.plotH);
                    ctx.lineTo(L.x(seg[0].t), L.top + L.plotH);
                    ctx.closePath();
                    ctx.fillStyle = fill;
                    ctx.fill();
                }
            }
        }
        ctx.restore();

        // leyenda
        ctx.textAlign = "left";
        ctx.textBaseline = "top";
        let lx = L.left;
        for (const s of series) {
            ctx.fillStyle = s.color;
            ctx.beginPath(); ctx.arc(lx + 5, 8, 4, 0, Math.PI * 2); ctx.fill();
            ctx.fillStyle = muted;
            ctx.fillText(s.label, lx + 14, 2);
            lx += ctx.measureText(s.label).width + 32;
        }

        // cursor
        if (hoverIndex !== null && progress >= 1) {
            const ref = series[0].points[hoverIndex];
            if (!ref) return;
            const xx = L.x(ref.t);
            ctx.strokeStyle = css("--border-strong") || "#2b3f56";
            ctx.beginPath(); ctx.moveTo(xx, L.top); ctx.lineTo(xx, L.top + L.plotH); ctx.stroke();
            const lines = [new Date(ref.t).toLocaleString("es", { dateStyle: "short", timeStyle: "short" })];
            for (const s of series) {
                const p = s.points[hoverIndex];
                if (p && Number.isFinite(p.v)) {
                    ctx.fillStyle = s.color;
                    ctx.beginPath(); ctx.arc(xx, L.y(p.v), 3.5, 0, Math.PI * 2); ctx.fill();
                    lines.push(`${s.label}: ${p.v.toLocaleString("es", { maximumFractionDigits: decimals })}`);
                }
            }
            ctx.font = "12px system-ui, sans-serif";
            const w = Math.max(...lines.map(l => ctx.measureText(l).width)) + 16;
            const h = lines.length * 16 + 10;
            const bx = Math.min(Math.max(xx + 10, L.left), L.left + L.plotW - w);
            ctx.fillStyle = "rgba(9, 15, 22, .94)";
            ctx.strokeStyle = css("--border-strong") || "#2b3f56";
            ctx.beginPath(); ctx.roundRect(bx, L.top + 4, w, h, 7); ctx.fill(); ctx.stroke();
            ctx.fillStyle = css("--text") || "#e7eef6";
            lines.forEach((l, i) => ctx.fillText(l, bx + 8, L.top + 10 + i * 16));
        }
    }

    function draw(canvas, series, { decimals = 0, animate = false } = {}) {
        const L = layout(canvas, series);
        canvas._chart = { series, L, decimals };
        if (!animate || reduced || L.empty) {
            paint(canvas, series, L, decimals, 1, null);
        } else {
            const start = performance.now();
            const frame = (now) => {
                const t = Math.min(1, (now - start) / 900);
                paint(canvas, series, L, decimals, 1 - Math.pow(1 - t, 3), null);
                if (t < 1 && canvas._chart.L === L) requestAnimationFrame(frame);
            };
            requestAnimationFrame(frame);
        }
        if (!canvas._hoverBound) {
            canvas._hoverBound = true;
            canvas.addEventListener("mousemove", (ev) => {
                const c = canvas._chart;
                if (!c || c.L.empty || !c.series[0].points.length) return;
                const rect = canvas.getBoundingClientRect();
                const mx = ev.clientX - rect.left;
                const pts = c.series[0].points;
                let best = 0, bestD = Infinity;
                pts.forEach((p, i) => { const d = Math.abs(c.L.x(p.t) - mx); if (d < bestD) { bestD = d; best = i; } });
                paint(canvas, c.series, c.L, c.decimals, 1, best);
            });
            canvas.addEventListener("mouseleave", () => {
                const c = canvas._chart;
                if (c) paint(canvas, c.series, c.L, c.decimals, 1, null);
            });
        }
    }

    return { draw };
})();
