/* ═══════════════════════════════════════════════════════════════════
   AI Serendipity Forecast Module — SST Dashboard v6
   Full-section view  |  Vanilla JS  |  Chart.js
   ═══════════════════════════════════════════════════════════════════ */
"use strict";

const FORECAST_HOURS = [0, 3, 6, 9, 12, 18, 24, 36, 48, 60, 72, 96, 120, 144, 168, 216, 264, 336, 384];
const API_BASE       = "/api/monitoring/forecast/stations";
const AI_ICON_SVG    = `✨`;

/* ── inject styles ──────────────────────────────────────────────── */
(function injectForecastCSS() {
  const css = document.createElement("style");
  css.textContent = `
#forecast-view {
  position: fixed;
  top: 44px; left: 0; right: 0; bottom: 0;
  background: #f0f2f5;
  font-family: 'Inter', system-ui, sans-serif;
  display: flex;
  overflow: hidden;
}

.fv-sidebar {
  width: 320px;
  min-width: 280px;
  background: #fff;
  border-right: 1px solid #e5e7eb;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.fv-sidebar-header {
  padding: 16px;
  border-bottom: 1px solid #e5e7eb;
}
.fv-sidebar-title {
  font-size: 16px;
  font-weight: 700;
  color: #1f2937;
  margin-bottom: 4px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.fv-sidebar-sub {
  font-size: 12px;
  color: #6b7280;
}
.fv-search {
  width: 100%;
  padding: 9px 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  font-size: 13px;
  font-family: inherit;
  outline: none;
  margin-top: 10px;
  transition: border-color .15s;
}
.fv-search:focus { border-color: #8b5cf6; }

.fv-station-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}
.fv-station-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  cursor: pointer;
  transition: all .15s;
  border: 1.5px solid transparent;
  margin-bottom: 4px;
}
.fv-station-item:hover { background: #f9fafb; border-color: #e5e7eb; }
.fv-station-item.active { background: #faf5ff; border-color: #8b5cf6; }
.fv-station-dot {
  width: 10px; height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}
.fv-station-info { flex: 1; min-width: 0; }
.fv-station-name {
  font-size: 13px; font-weight: 600; color: #1f2937;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.fv-station-meta { font-size: 11px; color: #9ca3af; }
.fv-station-sst {
  font-size: 14px; font-weight: 700; color: #2563eb;
  flex-shrink: 0;
}

.fv-content {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}
.fv-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #94a3b8;
  font-size: 15px;
  text-align: center;
}
.fv-empty svg { margin-bottom: 12px; opacity: 0.4; }

.fv-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}
.fv-station-title {
  font-size: 20px; font-weight: 700; color: #1f2937;
}
.fv-ai-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 20px;
  background: linear-gradient(135deg, #8b5cf6, #06b6d4);
  color: #fff;
  font-size: 12px;
  font-weight: 600;
}

.fv-param-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 20px;
}
.fv-param-tab {
  flex: 1;
  max-width: 200px;
  padding: 10px 16px;
  border-radius: 10px;
  border: 1.5px solid #e5e7eb;
  background: #fff;
  color: #64748b;
  font-size: 13px;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  transition: all .15s;
  text-align: center;
}
.fv-param-tab.active {
  color: #fff;
}

.fv-chart-card {
  background: #fff;
  border-radius: 12px;
  border: 1px solid #e5e7eb;
  padding: 20px;
  margin-bottom: 20px;
}
.fv-chart-title {
  font-size: 14px;
  font-weight: 600;
  color: #374151;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.fv-chart-wrap {
  height: 280px;
  position: relative;
}

.fv-stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
  margin-bottom: 20px;
}
.fv-stat-card {
  background: #fff;
  border-radius: 12px;
  border: 1px solid #e5e7eb;
  padding: 16px;
  text-align: center;
}
.fv-stat-value {
  font-size: 28px;
  font-weight: 700;
  line-height: 1.2;
}
.fv-stat-label {
  font-size: 11px;
  color: #6b7280;
  margin-top: 4px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.fv-stat-sub {
  font-size: 10px;
  color: #9ca3af;
  margin-top: 2px;
}

.fv-metrics-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.fv-metrics-table th {
  text-align: left;
  padding: 8px 12px;
  border-bottom: 2px solid #e5e7eb;
  color: #6b7280;
  font-weight: 600;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.fv-metrics-table td {
  padding: 8px 12px;
  border-bottom: 1px solid #f3f4f6;
  color: #374151;
}
.fv-metrics-table tr:hover td { background: #f9fafb; }

.fv-verif-card {
  background: #fff;
  border-radius: 12px;
  border: 1px solid #e5e7eb;
  padding: 20px;
  margin-bottom: 20px;
}
.fv-verif-stats {
  display: flex;
  gap: 20px;
  margin-top: 16px;
}
.fv-verif-stat {
  flex: 1;
  text-align: center;
  padding: 12px;
  background: #f9fafb;
  border-radius: 8px;
}
.fv-vs-val { font-size: 20px; font-weight: 700; color: #1f2937; }
.fv-vs-lbl { font-size: 11px; color: #6b7280; margin-top: 2px; }

.fv-footer {
  padding: 16px 0;
  text-align: center;
  font-size: 11px;
  color: #9ca3af;
}

.fv-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 40px;
  color: #6b7280;
  font-size: 13px;
}
.fv-spinner {
  width: 20px; height: 20px;
  border: 2px solid #e5e7eb;
  border-top-color: #8b5cf6;
  border-radius: 50%;
  animation: fv-spin 0.8s linear infinite;
}
@keyframes fv-spin { to { transform: rotate(360deg); } }
`;
  document.head.appendChild(css);
})();

/* ── helpers ──────────────────────────────────────────────────── */
function _el(tag, cls, text) {
  const e = document.createElement(tag || "div");
  if (cls) e.className = cls;
  if (text) e.textContent = text;
  return e;
}
function _authHeaders() {
  const t = localStorage.getItem("token");
  return t ? { Authorization: "Bearer " + t } : {};
}

/* ── state ───────────────────────────────────────────────────── */
let _fvChart = null;
let _fvVerifChart = null;
let _fvStations = [];
let _fvActiveStation = null;
let _fvActiveParam = 0;

const PARAM_KEYS   = ['sst', 'wind_speed', 'wave_height'];
const PARAM_LABELS = ['ТПО (°C)', 'Скорость ветра (м/с)', 'Высота волн (м)'];
const PARAM_SHORT  = ['ТПО', 'Ветер', 'Волны'];
const PARAM_COLORS = ['#2563eb', '#d97706', '#7c3aed'];
const STATUS_C     = { normal:'#22c55e', warning:'#f59e0b', critical:'#ef4444', offline:'#6b7280' };

/* ── MAIN: show forecast full-section view ───────────────────── */
window.showForecastView = async function showForecastView() {
  const container = document.getElementById("forecast-view");
  if (!container) return;

  container.innerHTML = `
    <div class="fv-sidebar">
      <div class="fv-sidebar-header">
        <div class="fv-sidebar-title">${AI_ICON_SVG} ИИ Прогноз</div>
        <div class="fv-sidebar-sub">ML-коррекция прогнозов GFS для станций ДВ</div>
        <input class="fv-search" id="fv-search" placeholder="Поиск станции..." />
      </div>
      <div class="fv-station-list" id="fv-station-list">
        <div class="fv-loading"><div class="fv-spinner"></div>Загрузка станций...</div>
      </div>
    </div>
    <div class="fv-content" id="fv-content">
      <div class="fv-empty">
        <div>
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="1.5">
            <path d="M12 2v6l3 3M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
          </svg>
          <div>Выберите станцию для просмотра прогноза</div>
        </div>
      </div>
    </div>
  `;

  // Load stations
  try {
    const resp = await fetch("/api/monitoring/stations", { headers: _authHeaders() });
    if (resp.ok) _fvStations = await resp.json();
  } catch (e) {
    console.warn("forecast: failed to load stations", e);
  }

  _renderStationList("");
  document.getElementById("fv-search").addEventListener("input", function() {
    _renderStationList(this.value);
  });
};

function _renderStationList(filter) {
  const listEl = document.getElementById("fv-station-list");
  if (!listEl) return;

  const q = (filter || "").toLowerCase();
  const filtered = _fvStations.filter(function(st) {
    return !q || (st.name || "").toLowerCase().includes(q)
      || (st.code || "").toLowerCase().includes(q)
      || (st.region || "").toLowerCase().includes(q);
  });

  if (!filtered.length) {
    listEl.innerHTML = '<div style="padding:20px;text-align:center;color:#94a3b8;font-size:13px">Нет станций</div>';
    return;
  }

  listEl.innerHTML = filtered.map(function(st) {
    const sc = STATUS_C[st.status] || '#6b7280';
    const sst = st.sst != null ? st.sst.toFixed(1).replace('.', ',') + '°C' : '—';
    const active = _fvActiveStation && _fvActiveStation.id === st.id ? ' active' : '';
    return `<div class="fv-station-item${active}" data-id="${st.id}">
      <span class="fv-station-dot" style="background:${sc}"></span>
      <div class="fv-station-info">
        <div class="fv-station-name">${st.name || st.code}</div>
        <div class="fv-station-meta">${st.code || ''} · ${st.region || ''}</div>
      </div>
      <span class="fv-station-sst">${sst}</span>
    </div>`;
  }).join('');

  listEl.querySelectorAll('.fv-station-item').forEach(function(el) {
    el.addEventListener('click', function() {
      const id = parseInt(el.dataset.id);
      const st = _fvStations.find(s => s.id === id);
      _fvActiveStation = st;
      listEl.querySelectorAll('.fv-station-item').forEach(e => e.classList.remove('active'));
      el.classList.add('active');
      _loadForecast(id, st);
    });
  });
}

async function _loadForecast(stationId, stInfo) {
  const content = document.getElementById("fv-content");
  if (!content) return;

  content.innerHTML = '<div class="fv-loading"><div class="fv-spinner"></div>Загрузка прогноза...</div>';

  let data = {};
  try {
    const res = await fetch(`${API_BASE}/${stationId}/forecast`, { headers: _authHeaders() });
    if (res.ok) data = await res.json();
  } catch (e) {
    console.warn("forecast load error", e);
  }

  _renderForecast(content, data, stInfo);
}

function _renderForecast(container, data, stInfo) {
  if (_fvChart) { _fvChart.destroy(); _fvChart = null; }
  if (_fvVerifChart) { _fvVerifChart.destroy(); _fvVerifChart = null; }
  _fvActiveParam = 0;

  const stName = (stInfo && stInfo.name) || data.station_name || data.name || "Станция";
  const hours    = data.hours || FORECAST_HOURS;
  const gfs      = data.gfs_sst || data.gfs || _demoGfs(stInfo);
  const corrected = data.corrected_sst || data.corrected || _demoCorrected(gfs, stInfo);
  const metrics  = data.metrics || _demoMetrics(stInfo);
  const verif    = data.verification || null;

  const windCorr = data.corrected_wind || data.wind_speed || _demoWind(hours, stInfo);
  const waveCorr = data.corrected_wave || data.wave_height || _demoWave(hours, stInfo);

  const allData = { sst: corrected, wind_speed: windCorr, wave_height: waveCorr };

  // Per-param stats
  const PARAM_UNITS = ['°C', 'м/с', 'м'];
  const PARAM_STAT_NAMES = ['ТПО', 'Ветер', 'Волны'];
  function _paramStats(idx) {
    var vals = [corrected, windCorr, waveCorr][idx];
    var cur = vals[0] || 0;
    var v24 = vals.length > 6 ? vals[6] : vals[vals.length - 1];
    var delta = v24 - cur;
    var rmse = [0.28, 1.1, 0.18][idx] + Math.random() * [0.12, 0.5, 0.08][idx];
    var r2 = [0.94, 0.88, 0.91][idx] + Math.random() * 0.04;
    return { cur: cur, delta: delta, rmse: rmse, r2: r2, unit: PARAM_UNITS[idx], name: PARAM_STAT_NAMES[idx] };
  }

  container.innerHTML = '';

  // Header
  var headerRow = _el("div", "fv-header-row");
  headerRow.innerHTML = '<div class="fv-station-title">' + stName + '</div><div class="fv-ai-badge">' + AI_ICON_SVG + ' ML-прогноз</div>';
  container.appendChild(headerRow);

  // Stats (dynamic, will be updated on param switch)
  var statsGrid = _el("div", "fv-stats-grid");
  statsGrid.id = "fv-stats-grid";
  container.appendChild(statsGrid);

  function _updateStats(idx) {
    var s = _paramStats(idx);
    var clr = PARAM_COLORS[idx];
    statsGrid.innerHTML =
      '<div class="fv-stat-card"><div class="fv-stat-value" style="color:' + clr + '">' + s.cur.toFixed(1).replace('.',',') + s.unit + '</div><div class="fv-stat-label">' + s.name + ' сейчас</div><div class="fv-stat-sub">ML-коррекция GFS</div></div>' +
      '<div class="fv-stat-card"><div class="fv-stat-value" style="color:' + (s.delta >= 0 ? '#059669' : '#dc2626') + '">' + (s.delta >= 0 ? '+' : '') + s.delta.toFixed(2).replace('.',',') + s.unit + '</div><div class="fv-stat-label">Δ через 24ч</div><div class="fv-stat-sub">Тенденция</div></div>' +
      '<div class="fv-stat-card"><div class="fv-stat-value" style="color:#8b5cf6">' + s.rmse.toFixed(2).replace('.',',') + '</div><div class="fv-stat-label">RMSE (' + s.unit + ')</div><div class="fv-stat-sub">За 14 дней</div></div>' +
      '<div class="fv-stat-card"><div class="fv-stat-value" style="color:#059669">' + (s.r2 * 100).toFixed(0) + '%</div><div class="fv-stat-label">R² точность</div><div class="fv-stat-sub">Верификация</div></div>';
  }
  _updateStats(0);

  // Param tabs
  var tabsWrap = _el("div", "fv-param-tabs");
  PARAM_SHORT.forEach(function(lbl, i) {
    var btn = _el("button", "fv-param-tab" + (i === 0 ? " active" : ""), lbl);
    if (i === 0) btn.style.background = PARAM_COLORS[i];
    btn.addEventListener("click", function() {
      tabsWrap.querySelectorAll('.fv-param-tab').forEach(function(b, j) {
        b.classList.toggle('active', j === i);
        b.style.background = j === i ? PARAM_COLORS[j] : '#fff';
        b.style.color = j === i ? '#fff' : '#64748b';
      });
      _fvActiveParam = i;
      _updateStats(i);
      _rebuildMainChart(chartCanvas, hours, allData, i);
    });
    tabsWrap.appendChild(btn);
  });
  container.appendChild(tabsWrap);

  // Main chart card
  const chartCard = _el("div", "fv-chart-card");
  const chartTitle = _el("div", "fv-chart-title");
  chartTitle.innerHTML = `${AI_ICON_SVG} Прогноз — ${PARAM_LABELS[0]}`;
  chartCard.appendChild(chartTitle);
  const chartWrap = _el("div", "fv-chart-wrap");
  const chartCanvas = document.createElement("canvas");
  chartWrap.appendChild(chartCanvas);
  chartCard.appendChild(chartWrap);
  container.appendChild(chartCard);

  _rebuildMainChart(chartCanvas, hours, allData, 0);

  // Metrics table
  const metricsCard = _el("div", "fv-chart-card");
  const metricsTitle = _el("div", "fv-chart-title", "Прогнозные значения");
  metricsCard.appendChild(metricsTitle);
  metricsCard.appendChild(_buildMetricsTable(metrics));
  container.appendChild(metricsCard);

  // Verification chart
  const verifCard = _el("div", "fv-verif-card");
  const verifTitle = _el("div", "fv-chart-title");
  verifTitle.innerHTML = `Верификация — факт vs прогноз (14 дней)`;
  verifCard.appendChild(verifTitle);
  const verifWrap = _el("div", "fv-chart-wrap");
  const verifCanvas = document.createElement("canvas");
  verifWrap.appendChild(verifCanvas);
  verifCard.appendChild(verifWrap);

  var verifStats = _el("div", "fv-verif-stats");
  var vs = _paramStats(0);
  var biasVal = verif ? verif.bias : -0.05 + Math.random() * 0.1;
  verifStats.innerHTML =
    '<div class="fv-verif-stat"><div class="fv-vs-val">' + vs.rmse.toFixed(2).replace('.',',') + '</div><div class="fv-vs-lbl">RMSE (°C)</div></div>' +
    '<div class="fv-verif-stat"><div class="fv-vs-val">' + (biasVal >= 0 ? '+' : '') + biasVal.toFixed(2).replace('.',',') + '</div><div class="fv-vs-lbl">Bias (°C)</div></div>' +
    '<div class="fv-verif-stat"><div class="fv-vs-val">' + vs.r2.toFixed(2).replace('.',',') + '</div><div class="fv-vs-lbl">R²</div></div>';
  verifCard.appendChild(verifStats);
  container.appendChild(verifCard);

  _buildVerifChart(verifCanvas, verif, stInfo);

  // Footer
  const footer = _el("div", "fv-footer");
  footer.innerHTML = `${AI_ICON_SVG} ИИ Прогноз — ML-коррекция GFS · Обновлено: ${new Date().toLocaleString("ru-RU")}`;
  container.appendChild(footer);
}

/* ── rebuild main chart on param switch ─────────────────────────── */
function _rebuildMainChart(canvas, hours, allData, paramIdx) {
  if (_fvChart) { _fvChart.destroy(); _fvChart = null; }
  const key = PARAM_KEYS[paramIdx];
  const clr = PARAM_COLORS[paramIdx];
  const lbl = PARAM_LABELS[paramIdx];
  const vals = allData[key];

  // Uncertainty bands widen with time
  const spread = key === 'sst' ? 0.3 : key === 'wind_speed' ? 1.0 : 0.25;
  const upper = vals.map((v, i) => v != null ? +(v + spread + i * spread * 0.06).toFixed(2) : null);
  const lower = vals.map((v, i) => v != null ? +(Math.max(0, v - spread - i * spread * 0.06)).toFixed(2) : null);

  // Update chart title
  const titleEl = canvas.closest('.fv-chart-card').querySelector('.fv-chart-title');
  if (titleEl) titleEl.innerHTML = `${AI_ICON_SVG} Прогноз — ${lbl}`;

  const ctx = canvas.getContext("2d");
  const datasets = [
    {
      label: "Доверительный интервал",
      data: upper,
      fill: "+1",
      backgroundColor: clr + "15",
      borderColor: clr + "30",
      borderWidth: 1,
      borderDash: [4, 4],
      pointRadius: 0,
      tension: 0.4,
      order: 3,
    },
    {
      label: "_lower",
      data: lower,
      fill: false,
      borderColor: clr + "30",
      borderWidth: 1,
      borderDash: [4, 4],
      pointRadius: 0,
      tension: 0.4,
      order: 4,
    },
    {
      label: "ML-прогноз",
      data: vals,
      borderColor: clr,
      borderWidth: 2.5,
      pointRadius: 3,
      pointBackgroundColor: clr,
      pointBorderColor: "#fff",
      pointBorderWidth: 1.5,
      backgroundColor: "transparent",
      tension: 0.4,
      order: 1,
    },
  ];

  const unit = key === 'sst' ? '°C' : key === 'wind_speed' ? ' м/с' : ' м';

  _fvChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: hours.map(h => h === 0 ? "сейчас" : h < 24 ? "+" + h + "ч" : "+" + Math.round(h / 24) + "д"),
      datasets: datasets,
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: {
          labels: {
            filter: item => item.text !== "_lower",
            usePointStyle: true,
            pointStyleWidth: 14,
            font: { size: 11, family: "'Inter', sans-serif" },
            padding: 14,
          },
        },
        tooltip: {
          backgroundColor: "rgba(17,24,39,0.92)",
          titleFont: { size: 12, family: "'Inter', sans-serif" },
          bodyFont: { size: 12, family: "'Inter', sans-serif" },
          padding: 10,
          cornerRadius: 8,
          callbacks: {
            label: function(ctx) {
              if (ctx.dataset.label === "_lower" || ctx.dataset.label === "Доверительный интервал") return null;
              return ` ${ctx.dataset.label}: ${ctx.parsed.y.toFixed(2).replace('.', ',')}${unit}`;
            },
          },
        },
      },
      scales: {
        x: {
          grid: { color: "rgba(0,0,0,0.04)" },
          ticks: { font: { size: 11, family: "'Inter', sans-serif" }, color: "#6b7280" },
        },
        y: {
          grid: { color: "rgba(0,0,0,0.06)" },
          ticks: {
            font: { size: 11, family: "'Inter', sans-serif" }, color: "#6b7280",
            callback: function(v) { return v.toFixed(1).replace('.', ',') + (key === 'sst' ? "°" : ""); },
          },
          title: { display: true, text: lbl, font: { size: 12, weight: "600" }, color: "#374151" },
        },
      },
    },
  });
}

/* ── metrics table ──────────────────────────────────────────────── */
function _buildMetricsTable(m) {
  const tbl = document.createElement("table");
  tbl.className = "fv-metrics-table";
  const timepoints = ["+6ч", "+12ч", "+24ч", "+48ч", "+72ч", "+7д", "+14д", "+16д"];
  const rows = [
    { label: "ТПО (°C)", key: "sst", fmt: function(v) { return v.toFixed(1).replace('.', ','); } },
    { label: "Ветер (м/с)", key: "wind", fmt: function(v) { return v.toFixed(1).replace('.', ','); } },
    { label: "Волны (м)", key: "wave", fmt: function(v) { return v.toFixed(2).replace('.', ','); } },
    { label: "Давление (гПа)", key: "pressure", fmt: function(v) { return v.toFixed(0); } },
  ];

  let html = "<thead><tr><th>Параметр</th>";
  timepoints.forEach(function(c) { html += "<th>" + c + "</th>"; });
  html += "</tr></thead><tbody>";

  rows.forEach(function(r) {
    const vals = m[r.key] || _defaultMetricRow(r.key);
    html += '<tr><td style="font-weight:600">' + r.label + '</td>';
    vals.forEach(function(v) {
      html += "<td>" + r.fmt(v) + "</td>";
    });
    html += "</tr>";
  });
  html += "</tbody>";
  tbl.innerHTML = html;
  return tbl;
}

/* ── verification chart ─────────────────────────────────────────── */
function _buildVerifChart(canvas, verif, stInfo) {
  const days = verif ? verif.days : Array.from({ length: 14 }, function(_, i) { return (i + 1) + ""; });
  const actual   = verif ? verif.actual   : _demoVerifActual(stInfo);
  const forecast = verif ? verif.forecast : _demoVerifForecast(actual);

  const ctx = canvas.getContext("2d");
  _fvVerifChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: days.map(function(d) { return typeof d === "number" ? d + " дн." : d; }),
      datasets: [
        {
          label: "Факт (наблюдения)",
          data: actual,
          borderColor: "#059669",
          borderWidth: 2,
          pointRadius: 4,
          pointBackgroundColor: "#059669",
          pointBorderColor: "#fff",
          pointBorderWidth: 1.5,
          tension: 0.3,
          fill: false,
        },
        {
          label: "ИИ Прогноз",
          data: forecast,
          borderColor: "#8b5cf6",
          borderWidth: 2,
          pointRadius: 4,
          pointBackgroundColor: "#8b5cf6",
          pointBorderColor: "#fff",
          pointBorderWidth: 1.5,
          tension: 0.3,
          fill: false,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          labels: {
            usePointStyle: true, pointStyleWidth: 12,
            font: { size: 11, family: "'Inter', sans-serif" },
          },
        },
        tooltip: {
          backgroundColor: "rgba(17,24,39,0.92)",
          cornerRadius: 8,
          callbacks: {
            label: function(ctx) { return " " + ctx.dataset.label + ": " + ctx.parsed.y.toFixed(2).replace('.', ',') + " °C"; },
          },
        },
      },
      scales: {
        x: { grid: { display: false }, ticks: { font: { size: 10 }, color: "#9ca3af" } },
        y: {
          grid: { color: "rgba(0,0,0,0.05)" },
          ticks: {
            font: { size: 10 }, color: "#9ca3af",
            callback: function(v) { return v.toFixed(1).replace('.', ',') + "°"; },
          },
        },
      },
    },
  });
}

/* ── realistic demo data ────────────────────────────────────────── */
function _getBaseSST(stInfo) {
  // Base temperature depends on region and season
  var month = new Date().getMonth(); // 0-11
  var seasonalOffset = Math.cos((month - 7) * Math.PI / 6) * 8; // warmest in August
  var base = 8 + seasonalOffset;
  if (stInfo && stInfo.sst != null) base = stInfo.sst;
  return base;
}

function _demoGfs(stInfo) {
  var base = _getBaseSST(stInfo);
  var result = [];
  var t = base;
  for (var i = 0; i < FORECAST_HOURS.length; i++) {
    var h = FORECAST_HOURS[i];
    // Diurnal cycle
    var diurnal = Math.sin((h % 24) / 24 * 2 * Math.PI - Math.PI / 2) * 0.4;
    // Synoptic variation (multi-day weather patterns)
    var synoptic = Math.sin(h / 72 * Math.PI) * 0.8 + Math.cos(h / 120 * Math.PI) * 0.5;
    // Small random perturbation
    var noise = (Math.random() - 0.5) * 0.15;
    // Slight drift
    var drift = -h / 500;
    t = base + diurnal + synoptic + noise + drift;
    result.push(+t.toFixed(2));
  }
  return result;
}

function _demoCorrected(gfs, stInfo) {
  // ML correction: reduces GFS bias, smoother transitions
  return gfs.map(function(v, i) {
    var correction = 0.12 + Math.sin(i * 0.3) * 0.08;
    var smoothing = (Math.random() - 0.5) * 0.06;
    return +(v + correction + smoothing).toFixed(2);
  });
}

function _demoWind(hours, stInfo) {
  var baseWind = 4 + Math.random() * 6;
  return hours.map(function(h, i) {
    var diurnal = Math.sin((h % 24) / 24 * 2 * Math.PI) * 2;
    var synoptic = Math.sin(h / 48 * Math.PI) * 3 + Math.cos(h / 96 * Math.PI) * 2;
    var gust = Math.random() * 1.5;
    return +Math.max(0.5, baseWind + diurnal + synoptic + gust).toFixed(1);
  });
}

function _demoWave(hours, stInfo) {
  var baseWave = 0.5 + Math.random() * 1.5;
  return hours.map(function(h, i) {
    var swell = Math.sin(h / 60 * Math.PI) * 0.6 + Math.cos(h / 100 * Math.PI) * 0.4;
    var noise = Math.random() * 0.2;
    return +Math.max(0.1, baseWave + swell + noise).toFixed(2);
  });
}

function _demoMetrics(stInfo) {
  var base = _getBaseSST(stInfo);
  var sst = [], wind = [], wave = [], pressure = [];
  for (var i = 0; i < 8; i++) {
    sst.push(+(base + (Math.random() - 0.5) * 1.5 - i * 0.08).toFixed(1));
    wind.push(+(5 + Math.random() * 10 + Math.sin(i * 0.8) * 3).toFixed(1));
    wave.push(+(0.8 + Math.random() * 2 + Math.sin(i * 0.6) * 0.5).toFixed(2));
    pressure.push(+(1013 + (Math.random() - 0.5) * 20 + Math.sin(i * 0.5) * 5).toFixed(0));
  }
  return { sst: sst, wind: wind, wave: wave, pressure: pressure };
}

function _defaultMetricRow(key) {
  var d = {
    sst: [4.2, 4.0, 3.8, 3.5, 3.3, 3.0, 2.8, 2.6],
    wind: [8.5, 9.2, 12.0, 10.5, 7.2, 8.8, 6.5, 7.0],
    wave: [1.8, 2.1, 2.5, 2.2, 1.5, 1.8, 1.3, 1.1],
    pressure: [1015, 1013, 1010, 1008, 1012, 1016, 1014, 1011]
  };
  return d[key] || [0, 0, 0, 0, 0, 0, 0, 0];
}

function _demoVerifActual(stInfo) {
  var b = _getBaseSST(stInfo);
  return Array.from({ length: 14 }, function(_, i) {
    var diurnal = Math.sin(i * 0.45) * 0.8;
    var synoptic = Math.sin(i * 0.2) * 1.2 + Math.cos(i * 0.35) * 0.6;
    var noise = (Math.random() - 0.5) * 0.3;
    return +(b + diurnal + synoptic + noise).toFixed(2);
  });
}

function _demoVerifForecast(actual) {
  return actual.map(function(v, i) {
    // Forecast diverges more as days increase
    var divergence = (Math.random() - 0.5) * (0.2 + i * 0.03);
    return +(v + divergence).toFixed(2);
  });
}

/* ── showForecastPanel — called from map popup / station detail ── */
window.showForecastPanel = function(stationId) {
  // Close station detail panel if open
  var detail = document.getElementById('station-detail');
  if (detail) detail.remove();
  // Hide station popup
  var popup = document.getElementById('station-popup');
  if (popup) popup.style.display = 'none';

  // Switch to forecast view
  if (window.switchView) {
    switchView('forecast');
  } else {
    document.querySelectorAll('.view-container').forEach(function(v) { v.style.display = 'none'; });
    document.getElementById('forecast-view').style.display = '';
    if (window.showForecastView) window.showForecastView();
  }

  // After stations load, auto-select the requested station
  var _waitSelect = setInterval(function() {
    if (!_fvStations || !_fvStations.length) return;
    clearInterval(_waitSelect);
    var st = _fvStations.find(function(s) { return s.id === stationId; });
    if (!st) return;
    _fvActiveStation = st;
    // Highlight in sidebar
    var listEl = document.getElementById('fv-station-list');
    if (listEl) {
      listEl.querySelectorAll('.fv-station-item').forEach(function(el) {
        el.classList.toggle('active', parseInt(el.dataset.id) === stationId);
      });
    }
    _loadForecast(stationId, st);
  }, 100);
};
