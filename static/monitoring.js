/* ════════════════════════════════════════════════════════════════
   SST Dashboard v5 — AI Agent Monitoring "Mission Control"
   Vanilla JS module  |  Dark theme  |  Real-time feed
   ════════════════════════════════════════════════════════════════ */
"use strict";

(function () {

  // ── Constants ──────────────────────────────────────────────
  const CLR = {
    bg:        "#0d1117",
    card:      "#161b22",
    border:    "#30363d",
    text:      "#e6edf3",
    textDim:   "#8b949e",
    info:      "#58a6ff",
    warning:   "#d29922",
    critical:  "#f85149",
    success:   "#3fb950",
    accent:    "#1f6feb",
    surface:   "#21262d",
  };

  const REFRESH_MS   = 30_000;
  const FEED_LIMIT   = 50;
  const API_BASE     = "";

  let _refreshTimer  = null;
  let _anomalyChart  = null;
  let _sstLineChart  = null;
  let _root          = null;
  let _feedContainer = null;
  let _feedData      = [];
  let _filterSeverity = "all";
  let _filterAgent    = "all";

  // ── Auth header ────────────────────────────────────────────
  function authHeaders() {
    const tok = localStorage.getItem("access_token");
    const h = { "Content-Type": "application/json" };
    if (tok) h["Authorization"] = "Bearer " + tok;
    return h;
  }

  function apiFetch(url, opts = {}) {
    opts.headers = { ...authHeaders(), ...(opts.headers || {}) };
    return fetch(API_BASE + url, opts);
  }

  // ── CSS Injection ──────────────────────────────────────────
  function injectStyles() {
    if (document.getElementById("mon-styles")) return;
    const style = document.createElement("style");
    style.id = "mon-styles";
    style.textContent = `
      #monitoring-root {
        position: fixed; inset: 0; z-index: 9000;
        background: ${CLR.bg};
        color: ${CLR.text};
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        display: flex; flex-direction: column;
        overflow: hidden;
        animation: monFadeIn .35s ease;
      }
      @keyframes monFadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }

      /* ── Top bar ── */
      .mon-topbar {
        display: flex; align-items: center; justify-content: space-between;
        padding: 12px 24px; background: ${CLR.card};
        border-bottom: 1px solid ${CLR.border};
        flex-shrink: 0;
      }
      .mon-topbar-title {
        font-size: 16px; font-weight: 700; letter-spacing: .02em;
        display: flex; align-items: center; gap: 10px;
      }
      .mon-topbar-title .mon-pulse {
        width: 8px; height: 8px; border-radius: 50%;
        background: ${CLR.success};
        box-shadow: 0 0 6px ${CLR.success};
        animation: monPulse 2s infinite;
      }
      @keyframes monPulse {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: .5; transform: scale(1.4); }
      }
      .mon-topbar-right { display: flex; align-items: center; gap: 12px; }
      .mon-topbar-time { font-size: 12px; color: ${CLR.textDim}; font-variant-numeric: tabular-nums; }
      .mon-btn-close {
        background: ${CLR.surface}; border: 1px solid ${CLR.border}; color: ${CLR.text};
        padding: 6px 16px; border-radius: 6px; cursor: pointer; font-size: 13px;
        font-family: inherit; transition: background .15s;
      }
      .mon-btn-close:hover { background: ${CLR.border}; }

      /* ── Columns ── */
      .mon-columns {
        display: flex; flex: 1; overflow: hidden;
      }
      .mon-col-left   { width: 25%; min-width: 260px; border-right: 1px solid ${CLR.border}; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 16px; }
      .mon-col-center { width: 50%; display: flex; flex-direction: column; overflow: hidden; }
      .mon-col-right  { width: 25%; min-width: 260px; border-left: 1px solid ${CLR.border}; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 16px; }

      /* ── Section cards ── */
      .mon-section {
        background: ${CLR.card}; border: 1px solid ${CLR.border};
        border-radius: 8px; padding: 14px; display: flex; flex-direction: column; gap: 10px;
      }
      .mon-section-title {
        font-size: 11px; font-weight: 600; text-transform: uppercase;
        letter-spacing: .06em; color: ${CLR.textDim}; margin: 0;
      }

      /* ── Mini map ── */
      .mon-minimap {
        width: 100%; aspect-ratio: 16/10; border-radius: 6px; overflow: hidden;
        background: #0b1222; position: relative;
      }
      .mon-minimap svg { width: 100%; height: 100%; }
      .mon-station-dot {
        transition: r .2s, fill .2s;
      }
      .mon-station-dot:hover { r: 5; }

      /* ── Status row ── */
      .mon-status-row {
        display: flex; align-items: center; gap: 6px;
        font-size: 13px; padding: 4px 0;
      }
      .mon-status-dot {
        width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0;
      }
      .mon-status-count { font-weight: 600; margin-right: 2px; }

      /* ── Feed header ── */
      .mon-feed-header {
        display: flex; align-items: center; justify-content: space-between;
        padding: 14px 18px; border-bottom: 1px solid ${CLR.border};
        flex-shrink: 0; gap: 10px; flex-wrap: wrap;
      }
      .mon-feed-title { font-size: 14px; font-weight: 700; white-space: nowrap; }
      .mon-feed-filters { display: flex; gap: 8px; align-items: center; }
      .mon-feed-select {
        background: ${CLR.surface}; border: 1px solid ${CLR.border}; color: ${CLR.text};
        padding: 4px 10px; border-radius: 5px; font-size: 12px; font-family: inherit;
        cursor: pointer; outline: none;
      }
      .mon-feed-select:focus { border-color: ${CLR.info}; }

      /* ── Feed list ── */
      .mon-feed-list {
        flex: 1; overflow-y: auto; padding: 10px 14px;
        display: flex; flex-direction: column; gap: 8px;
      }
      .mon-feed-list::-webkit-scrollbar { width: 6px; }
      .mon-feed-list::-webkit-scrollbar-track { background: transparent; }
      .mon-feed-list::-webkit-scrollbar-thumb { background: ${CLR.border}; border-radius: 3px; }

      /* ── Activity card ── */
      .mon-card {
        background: ${CLR.surface}; border: 1px solid ${CLR.border};
        border-radius: 8px; padding: 12px 14px; cursor: pointer;
        transition: border-color .2s, box-shadow .2s, transform .15s;
      }
      .mon-card:hover { border-color: ${CLR.textDim}; transform: translateY(-1px); }
      .mon-card:focus-visible { outline: 2px solid ${CLR.info}; outline-offset: 2px; }
      .mon-card.sev-critical {
        border-left: 3px solid ${CLR.critical};
        box-shadow: 0 0 12px rgba(248,81,73,.15);
      }
      .mon-card.sev-critical:hover {
        box-shadow: 0 0 20px rgba(248,81,73,.3);
      }
      .mon-card.sev-warning  { border-left: 3px solid ${CLR.warning}; }
      .mon-card.sev-info     { border-left: 3px solid ${CLR.info}; }

      .mon-card-top {
        display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
        font-size: 12px; margin-bottom: 6px;
      }
      .mon-card-time { color: ${CLR.textDim}; font-variant-numeric: tabular-nums; }
      .mon-card-agent {
        padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600;
        background: rgba(88,166,255,.15); color: ${CLR.info};
      }
      .mon-card-sev {
        font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .04em;
        margin-left: auto;
      }
      .mon-card-sev.sev-info     { color: ${CLR.info}; }
      .mon-card-sev.sev-warning  { color: ${CLR.warning}; }
      .mon-card-sev.sev-critical { color: ${CLR.critical}; }

      .mon-card-title { font-size: 13px; font-weight: 600; line-height: 1.4; }
      .mon-card-expand-hint {
        font-size: 11px; color: ${CLR.textDim}; margin-top: 4px;
        display: flex; align-items: center; gap: 4px;
        transition: color .15s;
      }
      .mon-card.expanded .mon-card-expand-hint { color: ${CLR.info}; }
      .mon-card-body {
        max-height: 0; overflow: hidden; transition: max-height .3s ease, padding .3s;
        font-size: 13px; line-height: 1.6; color: ${CLR.textDim};
      }
      .mon-card.expanded .mon-card-body {
        max-height: 600px; padding-top: 10px;
      }
      .mon-card-body p { margin: 0 0 8px; }

      /* ── Metric card ── */
      .mon-metric-value {
        font-size: 28px; font-weight: 700; letter-spacing: -.02em;
        line-height: 1;
      }
      .mon-metric-label {
        font-size: 12px; color: ${CLR.textDim}; margin-top: 2px;
      }
      .mon-chart-wrap {
        width: 100%; height: 140px; position: relative;
      }
      .mon-chart-wrap canvas { width: 100% !important; height: 100% !important; }

      /* ── Agent list ── */
      .mon-agent-row {
        display: flex; align-items: center; justify-content: space-between;
        padding: 6px 0; border-bottom: 1px solid ${CLR.border};
        font-size: 12px;
      }
      .mon-agent-row:last-child { border-bottom: none; }
      .mon-agent-name {
        display: flex; align-items: center; gap: 6px; font-weight: 500;
      }
      .mon-agent-indicator {
        width: 6px; height: 6px; border-radius: 50%;
        background: ${CLR.success};
      }
      .mon-agent-time { color: ${CLR.textDim}; font-variant-numeric: tabular-nums; }

      /* ── Action buttons ── */
      .mon-action-btn {
        width: 100%; padding: 10px 14px; border-radius: 6px;
        border: 1px solid ${CLR.border}; background: ${CLR.surface};
        color: ${CLR.text}; font-size: 13px; font-weight: 600;
        font-family: inherit; cursor: pointer;
        display: flex; align-items: center; gap: 8px; justify-content: center;
        transition: background .15s, border-color .2s, box-shadow .2s;
      }
      .mon-action-btn:hover {
        background: ${CLR.card}; border-color: ${CLR.info};
        box-shadow: 0 0 8px rgba(88,166,255,.15);
      }
      .mon-action-btn:active { transform: scale(.98); }
      .mon-action-btn.primary {
        background: ${CLR.accent}; border-color: ${CLR.accent};
      }
      .mon-action-btn.primary:hover {
        background: #388bfd; box-shadow: 0 0 12px rgba(56,139,253,.3);
      }

      /* ── Feed empty ── */
      .mon-feed-empty {
        flex: 1; display: flex; align-items: center; justify-content: center;
        color: ${CLR.textDim}; font-size: 13px; font-style: italic;
      }

      /* ── Responsive ── */
      @media (max-width: 1100px) {
        .mon-col-left  { display: none; }
        .mon-col-center { width: 60%; }
        .mon-col-right  { width: 40%; }
      }
      @media (max-width: 700px) {
        .mon-columns { flex-direction: column; }
        .mon-col-center, .mon-col-right { width: 100%; border: none; }
        .mon-col-right { border-top: 1px solid ${CLR.border}; max-height: 40vh; }
      }

      /* ── Loading shimmer ── */
      .mon-shimmer {
        background: linear-gradient(90deg, ${CLR.surface} 25%, ${CLR.border} 50%, ${CLR.surface} 75%);
        background-size: 200% 100%;
        animation: monShimmer 1.5s infinite;
        border-radius: 4px;
      }
      @keyframes monShimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }
    `;
    document.head.appendChild(style);
  }

  // ── Utility ────────────────────────────────────────────────
  function el(tag, cls, html) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html !== undefined) e.innerHTML = html;
    return e;
  }

  function fmtTime(iso) {
    if (!iso) return "--:--";
    const d = new Date(iso);
    return d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
  }

  function fmtDate(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    return d.toLocaleDateString("ru-RU", { day: "numeric", month: "short" });
  }

  function fmtRelative(iso) {
    if (!iso) return "";
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1)  return "только что";
    if (mins < 60) return mins + " мин. назад";
    const hrs = Math.floor(mins / 60);
    if (hrs < 24)  return hrs + " ч. назад";
    return Math.floor(hrs / 24) + " дн. назад";
  }

  function sevLabel(sev) {
    const m = { info: "INFO", warning: "WARNING", critical: "CRITICAL" };
    return m[sev] || sev.toUpperCase();
  }

  function sevIcon(sev) {
    if (sev === "critical") return '<svg width="12" height="12" viewBox="0 0 16 16" fill="' + CLR.critical + '"><circle cx="8" cy="8" r="7"/></svg>';
    if (sev === "warning")  return '<svg width="12" height="12" viewBox="0 0 16 16" fill="' + CLR.warning + '"><polygon points="8,1 15,15 1,15"/></svg>';
    return '<svg width="12" height="12" viewBox="0 0 16 16" fill="' + CLR.info + '"><circle cx="8" cy="8" r="7"/></svg>';
  }

  function mdToHtml(text) {
    if (!text) return "";
    return text
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(.+?)\*/g, "<em>$1</em>")
      .replace(/`(.+?)`/g, '<code style="background:' + CLR.border + ';padding:1px 5px;border-radius:3px;font-size:12px">$1</code>')
      .split(/\n\n+/).map(p => "<p>" + p.replace(/\n/g, "<br>") + "</p>").join("");
  }

  function nowStr() {
    return new Date().toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  }

  // ── Station map (SVG) ──────────────────────────────────────
  const STATIONS = [
    { id: 1,  name: "Владивосток",        lat: 43.12, lon: 131.87 },
    { id: 2,  name: "Находка",            lat: 42.81, lon: 132.87 },
    { id: 3,  name: "Посьет",             lat: 42.63, lon: 130.80 },
    { id: 4,  name: "Ольга",              lat: 43.73, lon: 135.28 },
    { id: 5,  name: "Рудная Пристань",    lat: 44.35, lon: 135.83 },
    { id: 6,  name: "Пластун",            lat: 44.75, lon: 136.29 },
    { id: 7,  name: "Терней",             lat: 45.05, lon: 136.59 },
    { id: 8,  name: "Совгавань",          lat: 48.97, lon: 140.28 },
    { id: 9,  name: "Де-Кастри",          lat: 51.47, lon: 140.79 },
    { id: 10, name: "Николаевск-на-Амуре", lat: 53.14, lon: 140.72 },
    { id: 11, name: "Охотск",             lat: 59.35, lon: 143.20 },
    { id: 12, name: "Магадан",            lat: 59.56, lon: 150.78 },
    { id: 13, name: "Петропавловск-Камч.", lat: 52.97, lon: 158.65 },
    { id: 14, name: "Усть-Камчатск",      lat: 56.23, lon: 162.47 },
    { id: 15, name: "Корсаков",           lat: 46.63, lon: 142.78 },
    { id: 16, name: "Холмск",             lat: 47.04, lon: 142.04 },
    { id: 17, name: "Невельск",           lat: 46.68, lon: 141.86 },
    { id: 18, name: "Александровск-Сах.",  lat: 50.90, lon: 142.16 },
    { id: 19, name: "Южно-Курильск",      lat: 44.03, lon: 145.86 },
    { id: 20, name: "Северо-Курильск",    lat: 50.68, lon: 156.13 },
  ];

  function buildMiniMap(stationStatuses) {
    const lonMin = 128, lonMax = 165, latMin = 40, latMax = 62;
    const W = 400, H = 250;
    function proj(lat, lon) {
      const x = ((lon - lonMin) / (lonMax - lonMin)) * W;
      const y = ((latMax - lat) / (latMax - latMin)) * H;
      return [x, y];
    }
    // Build connection lines between nearby stations
    let links = "";
    const coords = STATIONS.map(s => ({ ...s, pos: proj(s.lat, s.lon) }));
    const MAX_DIST = 120; // px distance threshold for connections
    for (let i = 0; i < coords.length; i++) {
      for (let j = i + 1; j < coords.length; j++) {
        const dx = coords[i].pos[0] - coords[j].pos[0];
        const dy = coords[i].pos[1] - coords[j].pos[1];
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < MAX_DIST) {
          const opacity = (0.12 + 0.08 * (1 - dist / MAX_DIST)).toFixed(2);
          links += `<line x1="${coords[i].pos[0].toFixed(1)}" y1="${coords[i].pos[1].toFixed(1)}" x2="${coords[j].pos[0].toFixed(1)}" y2="${coords[j].pos[1].toFixed(1)}" stroke="${CLR.info}" stroke-width="0.8" opacity="${opacity}"/>`;
        }
      }
    }

    let dots = "";
    STATIONS.forEach(s => {
      const [x, y] = proj(s.lat, s.lon);
      const status = (stationStatuses && stationStatuses[s.id]) || "online";
      const color = status === "critical" ? CLR.critical : status === "warning" ? CLR.warning : CLR.success;
      const glow = status === "critical" ? ` style="filter: drop-shadow(0 0 4px ${CLR.critical})"` : "";
      dots += `<circle class="mon-station-dot" data-station-id="${s.id}" cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="4.5" fill="${color}"${glow} style="cursor:pointer">
        <title>${s.name}</title>
      </circle>`;
    });
    // Simplified coastline path (rough outline of Russian Far East coast)
    const coastPath = `M${proj(42.5, 130).join(",")} L${proj(43, 132).join(",")} L${proj(44, 135).join(",")}
      L${proj(45, 136.5).join(",")} L${proj(47, 139).join(",")} L${proj(49, 140.3).join(",")}
      L${proj(51.5, 140.8).join(",")} L${proj(53, 141).join(",")} L${proj(55, 141.5).join(",")}
      L${proj(57, 142).join(",")} L${proj(59, 143).join(",")} L${proj(60, 150).join(",")}
      L${proj(59.5, 151).join(",")} L${proj(58, 153).join(",")} L${proj(56, 157).join(",")}
      L${proj(53, 159).join(",")} L${proj(51, 157).join(",")} L${proj(50.5, 156).join(",")}`;
    // Sakhalin outline
    const sakhalin = `M${proj(46, 142).join(",")} L${proj(47, 142.5).join(",")} L${proj(49, 142.3).join(",")}
      L${proj(51, 142.2).join(",")} L${proj(52, 142.8).join(",")} L${proj(51, 143.5).join(",")}
      L${proj(49, 143.8).join(",")} L${proj(47, 143.3).join(",")} L${proj(46, 142).join(",")}`;

    return `<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <radialGradient id="mapBg" cx="50%" cy="50%" r="70%">
          <stop offset="0%" stop-color="#0f1923"/>
          <stop offset="100%" stop-color="#060a10"/>
        </radialGradient>
      </defs>
      <rect width="${W}" height="${H}" fill="url(#mapBg)"/>
      <g opacity=".18">
        ${Array.from({length: 8}, (_, i) => {
          const x = (i + 1) * (W / 9);
          return `<line x1="${x}" y1="0" x2="${x}" y2="${H}" stroke="${CLR.border}" stroke-width=".5"/>`;
        }).join("")}
        ${Array.from({length: 5}, (_, i) => {
          const y = (i + 1) * (H / 6);
          return `<line x1="0" y1="${y}" x2="${W}" y2="${y}" stroke="${CLR.border}" stroke-width=".5"/>`;
        }).join("")}
      </g>
      <path d="${coastPath}" fill="none" stroke="${CLR.textDim}" stroke-width="1" opacity=".35"/>
      <path d="${sakhalin}" fill="none" stroke="${CLR.textDim}" stroke-width=".8" opacity=".3"/>
      <g class="mon-links">${links}</g>
      ${dots}
    </svg>`;
  }

  // ── Build DOM ──────────────────────────────────────────────
  function buildDashboard() {
    if (_root) _root.remove();
    _root = el("div");
    _root.id = "monitoring-root";

    // Top bar
    const topbar = el("div", "mon-topbar");
    topbar.innerHTML = `
      <div class="mon-topbar-title">
        <div class="mon-pulse"></div>
        ✨ ИИ Мониторинг
      </div>
      <div class="mon-topbar-right">
        <span class="mon-topbar-time" id="mon-clock">${nowStr()}</span>
        <button class="mon-btn-close" id="mon-btn-back">✕ Закрыть</button>
      </div>
    `;
    _root.appendChild(topbar);

    // Columns wrapper
    const cols = el("div", "mon-columns");

    // ── LEFT COLUMN ──
    const left = el("div", "mon-col-left");

    // Mini map section
    const mapSection = el("div", "mon-section");
    mapSection.innerHTML = `<h3 class="mon-section-title">Сеть станций</h3>`;
    const mapWrap = el("div", "mon-minimap");
    mapWrap.id = "mon-minimap";
    mapWrap.innerHTML = buildMiniMap(null);
    mapSection.appendChild(mapWrap);

    // Status counts
    const statusWrap = el("div");
    statusWrap.id = "mon-station-status";
    statusWrap.innerHTML = buildStatusCounts(18, 1, 1);
    mapSection.appendChild(statusWrap);
    left.appendChild(mapSection);

    // Stations list
    const stListSection = el("div", "mon-section");
    stListSection.innerHTML = `<h3 class="mon-section-title">Последние события станций</h3>`;
    const stList = el("div");
    stList.id = "mon-station-events";
    stList.innerHTML = '<div class="mon-shimmer" style="height:80px"></div>';
    stListSection.appendChild(stList);
    left.appendChild(stListSection);

    cols.appendChild(left);

    // ── CENTER COLUMN ──
    const center = el("div", "mon-col-center");

    // Feed header
    const feedHdr = el("div", "mon-feed-header");
    feedHdr.innerHTML = `
      <span class="mon-feed-title">Лента активности AI-агентов</span>
      <div class="mon-feed-filters">
        <select class="mon-feed-select" id="mon-filter-sev">
          <option value="all">Все уровни</option>
          <option value="info">INFO</option>
          <option value="warning">WARNING</option>
          <option value="critical">CRITICAL</option>
        </select>
        <select class="mon-feed-select" id="mon-filter-agent">
          <option value="all">Все агенты</option>
        </select>
      </div>
    `;
    center.appendChild(feedHdr);

    // Feed list
    _feedContainer = el("div", "mon-feed-list");
    _feedContainer.id = "mon-feed-list";
    _feedContainer.innerHTML = buildShimmerCards(5);
    center.appendChild(_feedContainer);

    cols.appendChild(center);

    // ── RIGHT COLUMN ──
    const right = el("div", "mon-col-right");

    // Anomaly chart
    const anomSec = el("div", "mon-section");
    anomSec.innerHTML = `
      <h3 class="mon-section-title">Аномалий за 30 дней</h3>
      <div class="mon-metric-value" id="mon-anomaly-total">--</div>
      <div class="mon-chart-wrap"><canvas id="mon-chart-anomaly"></canvas></div>
    `;
    right.appendChild(anomSec);

    // SST line chart
    const sstSec = el("div", "mon-section");
    sstSec.innerHTML = `
      <h3 class="mon-section-title">Средняя ТПО сети (7 дней)</h3>
      <div class="mon-metric-value" id="mon-sst-current">--</div>
      <div class="mon-metric-label">последнее значение</div>
      <div class="mon-chart-wrap"><canvas id="mon-chart-sst"></canvas></div>
    `;
    right.appendChild(sstSec);

    // Active agents
    const agentSec = el("div", "mon-section");
    agentSec.innerHTML = `<h3 class="mon-section-title">Активные агенты</h3>`;
    const agentList = el("div");
    agentList.id = "mon-agent-list";
    agentList.innerHTML = '<div class="mon-shimmer" style="height:60px"></div>';
    agentSec.appendChild(agentList);
    right.appendChild(agentSec);

    // Actions
    const actSec = el("div", "mon-section");
    actSec.innerHTML = `<h3 class="mon-section-title">Быстрые действия</h3>`;
    const actBtns = el("div", "", "");
    actBtns.style.cssText = "display:flex;flex-direction:column;gap:8px;";
    actBtns.innerHTML = `
      <button class="mon-action-btn primary" id="mon-act-digest">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M2 3h12M2 7h8M2 11h10"/></svg>
        Запустить дайджест
      </button>
      <button class="mon-action-btn" id="mon-act-anomaly">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M8 2v5M8 10v1M2 14h12L8 2 2 14z"/></svg>
        Проверка аномалий
      </button>
    `;
    actSec.appendChild(actBtns);
    right.appendChild(actSec);

    cols.appendChild(right);
    _root.appendChild(cols);
    document.body.appendChild(_root);

    // ── Bind events ──
    document.getElementById("mon-btn-back").addEventListener("click", () => window.hideMonitoringView());
    document.getElementById("mon-filter-sev").addEventListener("change", e => {
      _filterSeverity = e.target.value;
      renderFeed();
    });
    document.getElementById("mon-filter-agent").addEventListener("change", e => {
      _filterAgent = e.target.value;
      renderFeed();
    });
    document.getElementById("mon-act-digest").addEventListener("click", () => fireAction("digest"));
    document.getElementById("mon-act-anomaly").addEventListener("click", () => fireAction("anomaly_check"));

    // Bind station dot clicks on minimap
    document.querySelectorAll(".mon-station-dot[data-station-id]").forEach(dot => {
      dot.addEventListener("click", function() {
        const sid = parseInt(this.dataset.stationId);
        _monShowStationAlerts(sid);
      });
    });
  }

  let _lastStationData = {};

  function buildStatusCounts(online, warn, crit) {
    return `
      <div class="mon-status-row" style="cursor:pointer" onclick="window._monShowStatusList('online')" title="Показать онлайн-станции">
        <div class="mon-status-dot" style="background:${CLR.success}"></div>
        <span class="mon-status-count">${online}</span> онлайн
        <span style="margin-left:auto;font-size:10px;color:${CLR.textDim}">›</span>
      </div>
      <div class="mon-status-row" style="cursor:pointer" onclick="window._monShowStatusList('warning')" title="Показать станции с предупреждением">
        <div class="mon-status-dot" style="background:${CLR.warning}"></div>
        <span class="mon-status-count">${warn}</span> внимание
        <span style="margin-left:auto;font-size:10px;color:${CLR.textDim}">›</span>
      </div>
      <div class="mon-status-row" style="cursor:pointer" onclick="window._monShowStatusList('critical')" title="Показать критичные станции">
        <div class="mon-status-dot" style="background:${CLR.critical}"></div>
        <span class="mon-status-count">${crit}</span> критично
        <span style="margin-left:auto;font-size:10px;color:${CLR.textDim}">›</span>
      </div>
    `;
  }

  window._monShowStatusList = function(filter) {
    // Show a modal with stations matching the filter
    const old = document.getElementById('mon-status-modal');
    if (old) old.remove();

    const stations = Object.values(_lastStationData);
    const COLOR_MAP = { online: CLR.success, warning: CLR.warning, critical: CLR.critical, offline: CLR.textDim };
    const LABEL_MAP = { online: 'Онлайн', warning: 'Внимание', critical: 'Критично', offline: 'Нет связи' };
    const TITLE_MAP = { online: 'Онлайн станции', warning: 'Станции: Внимание', critical: 'Критичные станции' };

    const modal = el('div');
    modal.id = 'mon-status-modal';
    modal.style.cssText = `position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.6);z-index:99999;display:flex;align-items:center;justify-content:center`;
    modal.addEventListener('click', function(e) { if (e.target === modal) modal.remove(); });

    const box = el('div');
    box.style.cssText = `background:${CLR.card};border:1px solid ${CLR.border};border-radius:12px;width:380px;max-width:96vw;max-height:70vh;display:flex;flex-direction:column;overflow:hidden`;

    const hdr = el('div');
    hdr.style.cssText = `display:flex;align-items:center;justify-content:space-between;padding:16px 20px;border-bottom:1px solid ${CLR.border};flex-shrink:0`;
    hdr.innerHTML = `<span style="font-size:15px;font-weight:700;color:${CLR.text}">${TITLE_MAP[filter] || filter}</span>
      <button aria-label="Закрыть" onclick="document.getElementById('mon-status-modal').remove()" style="background:${CLR.surface};border:1px solid ${CLR.border};color:${CLR.text};width:28px;height:28px;border-radius:6px;cursor:pointer;font-size:16px;display:flex;align-items:center;justify-content:center;font-family:inherit">&times;</button>`;
    box.appendChild(hdr);

    const list = el('div');
    list.style.cssText = `overflow-y:auto;padding:12px 16px;display:flex;flex-direction:column;gap:8px`;

    // Try to use actual station data from last fetch
    const filtered = _lastStationsArray ? _lastStationsArray.filter(s => {
      if (filter === 'online') return s.status === 'normal';
      return s.status === filter;
    }) : [];

    if (filtered.length === 0) {
      list.innerHTML = `<div style="text-align:center;color:${CLR.textDim};padding:24px;font-size:13px">Нет станций с этим статусом</div>`;
    } else {
      filtered.forEach(function(s) {
        const row = el('div');
        row.style.cssText = `display:flex;align-items:center;gap:10px;padding:10px 12px;background:${CLR.surface};border:1px solid ${CLR.border};border-radius:8px;cursor:pointer`;
        row.addEventListener('click', function() { modal.remove(); if (window.showStationDetail) window.showStationDetail(s.id); });
        const sc = COLOR_MAP[s.status] || CLR.textDim;
        const lr = s.latest_reading || {};
        const sst = lr.sst != null ? lr.sst.toFixed(1).replace('.', ',') + '°C' : '—';
        const t = lr.observed_at ? new Date(lr.observed_at).toLocaleTimeString('ru-RU',{hour:'2-digit',minute:'2-digit'}) : '—';
        row.innerHTML = `
          <span style="width:10px;height:10px;border-radius:50%;background:${sc};flex-shrink:0"></span>
          <div style="flex:1;min-width:0">
            <div style="font-size:13px;font-weight:600;color:${CLR.text};white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${escHtml(s.name || s.code)}</div>
            <div style="font-size:11px;color:${CLR.textDim}">${escHtml(s.code)} · ${escHtml(s.region || '')} · ${t}</div>
          </div>
          <div style="text-align:right;flex-shrink:0">
            <div style="font-size:14px;font-weight:700;color:${CLR.info}">${sst}</div>
            <div style="font-size:10px;color:${CLR.textDim}">ТПО</div>
          </div>`;
        list.appendChild(row);
      });
    }

    box.appendChild(list);
    modal.appendChild(box);
    document.body.appendChild(modal);
  };

  function _monShowStationAlerts(stationId) {
    const station = STATIONS.find(s => s.id === stationId);
    if (!station) return;
    const stData = _lastStationsArray ? _lastStationsArray.find(s => s.id === stationId) : null;

    const old = document.getElementById('mon-station-alert-modal');
    if (old) old.remove();

    const modal = el('div');
    modal.id = 'mon-station-alert-modal';
    modal.style.cssText = `position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.6);z-index:99999;display:flex;align-items:center;justify-content:center`;
    modal.addEventListener('click', function(e) { if (e.target === modal) modal.remove(); });

    const box = el('div');
    box.style.cssText = `background:${CLR.card};border:1px solid ${CLR.border};border-radius:12px;width:420px;max-width:96vw;max-height:80vh;display:flex;flex-direction:column;overflow:hidden`;

    const lr = stData && stData.latest_reading ? stData.latest_reading : {};
    const sst = lr.sst != null ? Number(lr.sst).toFixed(1).replace('.', ',') + '°C' : '—';
    const wind = lr.wind_speed != null ? Number(lr.wind_speed).toFixed(1).replace('.', ',') + ' м/с' : '—';
    const waves = lr.wave_height != null ? Number(lr.wave_height).toFixed(2).replace('.', ',') + ' м' : '—';

    box.innerHTML = `
      <div style="display:flex;align-items:center;justify-content:space-between;padding:16px 20px;border-bottom:1px solid ${CLR.border}">
        <div>
          <div style="font-size:15px;font-weight:700;color:${CLR.text}">${escHtml(station.name)}</div>
          <div style="font-size:11px;color:${CLR.textDim}">${stData ? escHtml(stData.code || '') + ' · ' + escHtml(stData.region || '') : ''}</div>
        </div>
        <button aria-label="Закрыть" onclick="document.getElementById('mon-station-alert-modal').remove()" style="background:${CLR.surface};border:1px solid ${CLR.border};color:${CLR.text};width:28px;height:28px;border-radius:6px;cursor:pointer;font-size:16px;display:flex;align-items:center;justify-content:center">&times;</button>
      </div>
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;padding:12px 16px;border-bottom:1px solid ${CLR.border}">
        <div style="text-align:center"><div style="font-size:10px;color:${CLR.textDim}">ТПО</div><div style="font-size:16px;font-weight:700;color:${CLR.info}">${sst}</div></div>
        <div style="text-align:center"><div style="font-size:10px;color:${CLR.textDim}">Ветер</div><div style="font-size:16px;font-weight:700;color:${CLR.text}">${wind}</div></div>
        <div style="text-align:center"><div style="font-size:10px;color:${CLR.textDim}">Волны</div><div style="font-size:16px;font-weight:700;color:${CLR.text}">${waves}</div></div>
      </div>
      <div style="padding:12px 16px 4px;font-size:12px;font-weight:600;color:${CLR.textDim}">Оповещения AI-агентов</div>
      <div id="mon-station-alerts-list" style="overflow-y:auto;padding:4px 16px 16px;display:flex;flex-direction:column;gap:6px">
        <div class="mon-shimmer" style="height:40px;border-radius:6px"></div>
      </div>
    `;
    modal.appendChild(box);
    document.body.appendChild(modal);

    // Load alerts for this station from feed data
    const stName = station.name.toLowerCase();
    const alerts = _feedData.filter(item => {
      const t = (item.title || '').toLowerCase();
      const b = (item.body || '').toLowerCase();
      return t.includes(stName) || b.includes(stName);
    }).slice(0, 10);

    const listEl = document.getElementById('mon-station-alerts-list');
    if (!alerts.length) {
      listEl.innerHTML = `<div style="text-align:center;color:${CLR.textDim};padding:16px;font-size:12px">Нет оповещений для этой станции</div>`;
    } else {
      listEl.innerHTML = alerts.map(a => {
        const sevColor = a.severity === 'critical' ? CLR.critical : a.severity === 'warning' ? CLR.warning : CLR.info;
        const time = a.timestamp ? new Date(a.timestamp).toLocaleString('ru-RU', {day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'}) : '';
        return `<div style="padding:8px 10px;background:${CLR.surface};border-left:3px solid ${sevColor};border-radius:4px;font-size:12px">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:2px">
            <span style="font-weight:600;color:${CLR.text}">${escHtml(a.agent_name || 'system')}</span>
            <span style="font-size:10px;color:${CLR.textDim}">${time}</span>
          </div>
          <div style="color:${CLR.textDim}">${escHtml(a.title || '')}</div>
        </div>`;
      }).join('');
    }
  }

  let _lastStationsArray = null;

  function buildShimmerCards(n) {
    return Array.from({ length: n }, () =>
      `<div class="mon-card" style="pointer-events:none">
        <div class="mon-shimmer" style="height:14px;width:60%;margin-bottom:8px"></div>
        <div class="mon-shimmer" style="height:12px;width:90%"></div>
      </div>`
    ).join("");
  }

  // ── Render feed ────────────────────────────────────────────
  function renderFeed() {
    if (!_feedContainer) return;
    let items = _feedData;
    if (_filterSeverity !== "all") items = items.filter(i => i.severity === _filterSeverity);
    if (_filterAgent !== "all")    items = items.filter(i => i.agent_name === _filterAgent);

    if (!items.length) {
      _feedContainer.innerHTML = '<div class="mon-feed-empty">Нет записей по выбранным фильтрам</div>';
      return;
    }

    _feedContainer.innerHTML = "";
    items.forEach(item => {
      const card = el("div", "mon-card sev-" + (item.severity || "info"));
      const sev = item.severity || "info";
      card.setAttribute("role", "button");
      card.setAttribute("tabindex", "0");
      card.setAttribute("aria-expanded", "false");
      card.setAttribute("aria-label", `${item.agent_name || "system"} - ${item.title || ""}`);
      card.innerHTML = `
        <div class="mon-card-top">
          ${sevIcon(sev)}
          <span class="mon-card-time">${fmtTime(item.timestamp)}${item.timestamp ? ", " + fmtDate(item.timestamp) : ""}</span>
          <span class="mon-card-agent">${escHtml(item.agent_name || "system")}</span>
          <span class="mon-card-sev sev-${sev}">${sevLabel(sev)}</span>
        </div>
        <div class="mon-card-title">${escHtml(item.title || "")}</div>
        <div class="mon-card-expand-hint">
          <span style="font-size:10px">&#9660;</span> Подробнее
        </div>
        <div class="mon-card-body">${mdToHtml(item.body || "")}</div>
      `;
      const toggleExpand = () => {
        const isExpanded = card.classList.toggle("expanded");
        card.setAttribute("aria-expanded", isExpanded ? "true" : "false");
      };
      card.addEventListener("click", toggleExpand);
      card.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          toggleExpand();
        }
      });
      _feedContainer.appendChild(card);
    });
  }

  function escHtml(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  // ── Charts ─────────────────────────────────────────────────
  function initAnomalyChart(labels, data) {
    const ctx = document.getElementById("mon-chart-anomaly");
    if (!ctx) return;
    if (_anomalyChart) _anomalyChart.destroy();
    _anomalyChart = new Chart(ctx, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [{
          data: data,
          backgroundColor: data.map(v => v >= 5 ? CLR.critical + "99" : v >= 2 ? CLR.warning + "99" : CLR.info + "66"),
          borderRadius: 3,
          borderSkipped: false,
        }]
      },
      options: chartOpts("Аномалии", false),
    });
  }

  function initSSTChart(labels, data) {
    const ctx = document.getElementById("mon-chart-sst");
    if (!ctx) return;
    if (_sstLineChart) _sstLineChart.destroy();
    _sstLineChart = new Chart(ctx, {
      type: "line",
      data: {
        labels: labels,
        datasets: [{
          data: data,
          borderColor: CLR.info,
          backgroundColor: CLR.info + "1a",
          fill: true,
          tension: .4,
          pointRadius: 2,
          pointHoverRadius: 5,
          borderWidth: 2,
        }]
      },
      options: chartOpts("°C", true),
    });
  }

  function chartOpts(yTitle, showLine) {
    return {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: CLR.card,
          titleColor: CLR.text,
          bodyColor: CLR.textDim,
          borderColor: CLR.border,
          borderWidth: 1,
          cornerRadius: 6,
          padding: 8,
        },
      },
      scales: {
        x: {
          ticks: { color: CLR.textDim, font: { size: 10 }, maxRotation: 0 },
          grid: { color: CLR.border + "44" },
        },
        y: {
          ticks: { color: CLR.textDim, font: { size: 10 } },
          grid: { color: CLR.border + "44" },
          title: { display: false },
        }
      },
      interaction: { mode: "index", intersect: false },
    };
  }

  // ── Agent list ─────────────────────────────────────────────
  function renderAgentList(agents) {
    const wrap = document.getElementById("mon-agent-list");
    if (!wrap) return;
    if (!agents || !agents.length) {
      wrap.innerHTML = '<div style="font-size:12px;color:' + CLR.textDim + '">Нет данных</div>';
      return;
    }
    wrap.innerHTML = agents.map(a => `
      <div class="mon-agent-row">
        <div class="mon-agent-name">
          <div class="mon-agent-indicator" style="background:${a.active !== false ? CLR.success : CLR.textDim}"></div>
          ${escHtml(a.name || a.agent_name || "agent")}
        </div>
        <div class="mon-agent-time">${fmtRelative(a.last_activity)}</div>
      </div>
    `).join("");
  }

  // ── Station events (left column) ───────────────────────────
  function renderStationEvents(events) {
    const wrap = document.getElementById("mon-station-events");
    if (!wrap) return;
    if (!events || !events.length) {
      wrap.innerHTML = '<div style="font-size:12px;color:' + CLR.textDim + '">Нет недавних событий</div>';
      return;
    }
    wrap.innerHTML = events.slice(0, 8).map(e => `
      <div style="display:flex;align-items:flex-start;gap:8px;padding:6px 0;border-bottom:1px solid ${CLR.border};font-size:12px">
        <div class="mon-status-dot" style="background:${e.severity === "critical" ? CLR.critical : e.severity === "warning" ? CLR.warning : CLR.success};margin-top:3px;flex-shrink:0"></div>
        <div>
          <div style="font-weight:500">${escHtml(e.station_name || "Станция")}</div>
          <div style="color:${CLR.textDim}">${escHtml(e.message || "")}</div>
        </div>
        <div style="margin-left:auto;color:${CLR.textDim};white-space:nowrap">${fmtTime(e.timestamp)}</div>
      </div>
    `).join("");
  }

  // ── Data fetch ─────────────────────────────────────────────
  async function fetchSummary() {
    try {
      const res = await apiFetch("/api/monitoring/dashboard/summary");
      if (!res.ok) throw new Error(res.status);
      const data = await res.json();

      // Station statuses
      const statuses = data.station_statuses || {};
      const online = data.stations_online ?? 18;
      const warn   = data.stations_warning ?? 1;
      const crit   = data.stations_critical ?? 1;
      if (data.stations && Array.isArray(data.stations)) _lastStationsArray = data.stations;

      const statusEl = document.getElementById("mon-station-status");
      if (statusEl) statusEl.innerHTML = buildStatusCounts(online, warn, crit);

      const mapEl = document.getElementById("mon-minimap");
      if (mapEl) mapEl.innerHTML = buildMiniMap(statuses);

      // Anomaly chart
      if (data.anomaly_chart) {
        initAnomalyChart(data.anomaly_chart.labels || [], data.anomaly_chart.data || []);
        const totalEl = document.getElementById("mon-anomaly-total");
        if (totalEl) totalEl.textContent = (data.anomaly_chart.data || []).reduce((s, v) => s + v, 0);
      } else {
        initAnomalyChart(generateLast30DayLabels(), generateDemoAnomalyData());
        const totalEl = document.getElementById("mon-anomaly-total");
        if (totalEl) totalEl.textContent = "--";
      }

      // SST chart
      if (data.sst_chart) {
        initSSTChart(data.sst_chart.labels || [], data.sst_chart.data || []);
        const curEl = document.getElementById("mon-sst-current");
        const d = data.sst_chart.data || [];
        if (curEl && d.length) curEl.textContent = d[d.length - 1].toFixed(1).replace('.', ',') + " °C";
      } else {
        initSSTChart(generateLast7DayLabels(), generateDemoSSTData());
      }

      // Agents
      renderAgentList(data.agents || []);

      // Station events
      renderStationEvents(data.station_events || []);

    } catch (e) {
      console.warn("[monitoring] summary fetch failed, using demo data:", e);
      loadDemoData();
    }
  }

  async function fetchFeed() {
    try {
      const res = await apiFetch("/api/monitoring/feed?limit=" + FEED_LIMIT);
      if (!res.ok) throw new Error(res.status);
      const data = await res.json();
      _feedData = Array.isArray(data) ? data : (data.items || data.feed || []);
    } catch (e) {
      console.warn("[monitoring] feed fetch failed, using demo data:", e);
      _feedData = generateDemoFeed();
    }
    populateAgentFilter();
    renderFeed();
  }

  async function fetchStationsList() {
    try {
      const res = await apiFetch("/api/monitoring/stations");
      if (res.ok) {
        const data = await res.json();
        // Normalize: if no latest_reading nested, create it from top-level fields
        _lastStationsArray = data.map(s => {
          if (!s.latest_reading) {
            s.latest_reading = {
              sst: s.sst, temp_air: s.temp_air, wind_speed: s.wind_speed,
              wave_height: s.wave_height, pressure: s.pressure, humidity: s.humidity,
              observed_at: s.last_reading_at || s.observed_at
            };
          }
          return s;
        });
      }
    } catch(e) {}
  }

  function populateAgentFilter() {
    const sel = document.getElementById("mon-filter-agent");
    if (!sel) return;
    const agents = [...new Set(_feedData.map(i => i.agent_name).filter(Boolean))];
    const current = sel.value;
    sel.innerHTML = '<option value="all">Все агенты</option>' +
      agents.map(a => `<option value="${escHtml(a)}">${escHtml(a)}</option>`).join("");
    sel.value = current;
  }

  // ── Demo / fallback data ───────────────────────────────────
  function generateLast30DayLabels() {
    const labels = [];
    for (let i = 29; i >= 0; i--) {
      const d = new Date(); d.setDate(d.getDate() - i);
      labels.push(d.toLocaleDateString("ru-RU", { day: "numeric", month: "short" }));
    }
    return labels;
  }
  function generateLast7DayLabels() {
    const labels = [];
    for (let i = 6; i >= 0; i--) {
      const d = new Date(); d.setDate(d.getDate() - i);
      labels.push(d.toLocaleDateString("ru-RU", { day: "numeric", month: "short" }));
    }
    return labels;
  }
  function generateDemoAnomalyData() {
    return Array.from({ length: 30 }, () => Math.floor(Math.random() * 6));
  }
  function generateDemoSSTData() {
    let v = 5.2;
    return Array.from({ length: 7 }, () => { v += (Math.random() - .5) * 1.2; return +v.toFixed(1); });
  }

  function generateDemoFeed() {
    const agents = ["anomaly-detector-v1", "digest-agent", "data-quality-checker", "forecast-agent", "alert-dispatcher"];
    const severities = ["info", "info", "info", "warning", "warning", "critical"];
    const titles = [
      "Завершена проверка данных за сутки",
      "Аномальный рост ТПО у Владивостока",
      "Дайджест сформирован и отправлен",
      "Пропущены данные со станции Посьет",
      "Прогноз ТПО обновлен на 7 дней",
      "Критическое отклонение ТПО у Южно-Курильска",
      "Станция Охотск: задержка данных > 6 часов",
      "Обнаружен тренд похолодания в районе Магадана",
      "Автоматическая коррекция смещения сенсора",
      "Плановая проверка качества данных завершена",
    ];
    const bodies = [
      "Все 20 станций передали данные в штатном режиме. Среднее отклонение от климатической нормы составляет **+0.8 °C**.\n\nРекомендуется обратить внимание на станции южного кластера.",
      "Зафиксирован рост ТПО на **+2.3 °C** относительно климатической нормы 1991-2020. Аномалия сохраняется третьи сутки подряд.\n\nВозможная причина: теплое течение Куросио усилилось в данном районе.",
      "Еженедельный дайджест включает анализ 140 наблюдений с 20 станций. Ключевые находки:\n\n- Средняя ТПО сети: **5.8 °C** (+0.4 от нормы)\n- Обнаружено 3 аномалии\n- Все станции функционируют штатно",
      "Станция Посьет не передавала данные более **12 часов**. Последний прием: 07:30 UTC.\n\nРекомендуется проверить канал связи и состояние оборудования.",
      "Обновлен 7-дневный прогноз ТПО на основе ансамбля моделей. Средняя ожидаемая температура: **5.2-6.1 °C**.",
      "ТПО у станции Южно-Курильск отклонилась на **-3.8 °C** от нормы. Это превышает порог в 3 сигма.\n\nТребуется верификация данных и возможная калибровка сенсора.",
    ];

    const feed = [];
    const now = Date.now();
    for (let i = 0; i < 20; i++) {
      const ts = new Date(now - i * 1800000 - Math.random() * 600000);
      feed.push({
        id: i + 1,
        timestamp: ts.toISOString(),
        agent_name: agents[Math.floor(Math.random() * agents.length)],
        severity: severities[Math.floor(Math.random() * severities.length)],
        title: titles[i % titles.length],
        body: bodies[i % bodies.length],
      });
    }
    return feed;
  }

  function loadDemoData() {
    // Anomaly chart
    const anomLabels = generateLast30DayLabels();
    const anomData = generateDemoAnomalyData();
    initAnomalyChart(anomLabels, anomData);
    const totalEl = document.getElementById("mon-anomaly-total");
    if (totalEl) totalEl.textContent = anomData.reduce((s, v) => s + v, 0);

    // SST chart
    const sstLabels = generateLast7DayLabels();
    const sstData = generateDemoSSTData();
    initSSTChart(sstLabels, sstData);
    const curEl = document.getElementById("mon-sst-current");
    if (curEl && sstData.length) curEl.textContent = sstData[sstData.length - 1].toFixed(1).replace('.', ',') + " °C";

    // Agents
    renderAgentList([
      { name: "anomaly-detector-v1",    last_activity: new Date(Date.now() - 120000).toISOString(), active: true },
      { name: "digest-agent",           last_activity: new Date(Date.now() - 3600000).toISOString(), active: true },
      { name: "data-quality-checker",   last_activity: new Date(Date.now() - 900000).toISOString(), active: true },
      { name: "forecast-agent",         last_activity: new Date(Date.now() - 7200000).toISOString(), active: true },
      { name: "alert-dispatcher",       last_activity: new Date(Date.now() - 300000).toISOString(), active: true },
    ]);

    // Station events
    renderStationEvents([
      { station_name: "Посьет",         severity: "warning",  message: "Задержка данных > 3 часов", timestamp: new Date(Date.now() - 600000).toISOString() },
      { station_name: "Южно-Курильск",  severity: "critical", message: "Критическое отклонение ТПО", timestamp: new Date(Date.now() - 1200000).toISOString() },
      { station_name: "Владивосток",    severity: "info",     message: "Данные получены штатно", timestamp: new Date(Date.now() - 1800000).toISOString() },
      { station_name: "Магадан",        severity: "info",     message: "Данные получены штатно", timestamp: new Date(Date.now() - 2400000).toISOString() },
    ]);

    // Update station map with demo statuses
    const statuses = {};
    STATIONS.forEach(s => statuses[s.id] = "online");
    statuses[3]  = "warning";   // Посьет
    statuses[19] = "critical";  // Южно-Курильск
    const mapEl = document.getElementById("mon-minimap");
    if (mapEl) mapEl.innerHTML = buildMiniMap(statuses);

    const statusEl = document.getElementById("mon-station-status");
    if (statusEl) statusEl.innerHTML = buildStatusCounts(18, 1, 1);
  }

  // ── Quick actions ──────────────────────────────────────────
  async function fireAction(action) {
    const btn = action === "digest"
      ? document.getElementById("mon-act-digest")
      : document.getElementById("mon-act-anomaly");
    if (!btn) return;

    const origHTML = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="mon-shimmer" style="display:inline-block;width:16px;height:16px;border-radius:50%"></span> Выполняется...';

    try {
      const res = await apiFetch("/api/monitoring/actions/" + action, { method: "POST" });
      if (!res.ok) throw new Error(res.status);
      btn.innerHTML = '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="' + CLR.success + '" stroke-width="2"><polyline points="3,8 7,12 13,4"/></svg> Готово!';
      btn.style.borderColor = CLR.success;
      setTimeout(() => {
        btn.innerHTML = origHTML;
        btn.disabled = false;
        btn.style.borderColor = "";
      }, 2500);
    } catch (e) {
      console.warn("[monitoring] action failed:", e);
      btn.innerHTML = '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="' + CLR.critical + '" stroke-width="2"><line x1="4" y1="4" x2="12" y2="12"/><line x1="12" y1="4" x2="4" y2="12"/></svg> Ошибка';
      btn.style.borderColor = CLR.critical;
      setTimeout(() => {
        btn.innerHTML = origHTML;
        btn.disabled = false;
        btn.style.borderColor = "";
      }, 2500);
    }
  }

  // ── Clock ──────────────────────────────────────────────────
  let _clockTimer = null;
  function startClock() {
    stopClock();
    _clockTimer = setInterval(() => {
      const el = document.getElementById("mon-clock");
      if (el) el.textContent = nowStr();
    }, 1000);
  }
  function stopClock() {
    if (_clockTimer) { clearInterval(_clockTimer); _clockTimer = null; }
  }

  // ── Auto-refresh ───────────────────────────────────────────
  function startAutoRefresh() {
    stopAutoRefresh();
    _refreshTimer = setInterval(() => {
      window.refreshMonitoringFeed();
    }, REFRESH_MS);
  }
  function stopAutoRefresh() {
    if (_refreshTimer) { clearInterval(_refreshTimer); _refreshTimer = null; }
  }

  // ── Keyboard accessibility listener ────────────────────────
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" || e.keyCode === 27) {
      const m1 = document.getElementById("mon-status-modal");
      if (m1) m1.remove();
      const m2 = document.getElementById("mon-station-alert-modal");
      if (m2) m2.remove();
    }
  });

  // ── Public API ─────────────────────────────────────────────

  window.showMonitoringView = function () {
    injectStyles();
    buildDashboard();
    startClock();

    // Hide SST elements
    const sstEls = ["map", "compare-view", "bottom-bar", "left-panel", "legend",
                    "panel-toggle", "back-btn", "dashboard", "hover-tooltip", "cmp-legend-h"];
    sstEls.forEach(id => {
      const e = document.getElementById(id);
      if (e) e.style.display = "none";
    });
    // Hide user menu in dark monitoring view
    const um = document.getElementById("user-menu");
    if (um) um.style.display = "none";

    // Fetch data
    fetchSummary();
    fetchFeed();
    fetchStationsList();
    startAutoRefresh();
  };

  window.hideMonitoringView = function () {
    stopAutoRefresh();
    stopClock();
    if (_anomalyChart)  { _anomalyChart.destroy();  _anomalyChart = null; }
    if (_sstLineChart)  { _sstLineChart.destroy();  _sstLineChart = null; }
    if (_root) { _root.remove(); _root = null; }
    _feedContainer = null;
    _feedData = [];

    // Restore SST elements
    const show = ["map", "compare-view", "panel-toggle"];
    show.forEach(id => {
      const e = document.getElementById(id);
      if (e) e.style.display = "";
    });
    // Restore user menu
    const um = document.getElementById("user-menu");
    if (um) um.style.display = "";
  };

  window.refreshMonitoringFeed = function () {
    fetchSummary();
    fetchFeed();
  };

})();
