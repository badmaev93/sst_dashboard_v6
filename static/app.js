/* GFS Dashboard v6 — карты прогноза GFS по Северной Пацифике */
"use strict";

// GFS forecast hours available in compare view
const GFS_FHOURS = [0, 24, 48, 72, 96, 120];
const GFS_LABELS = [
  "Анализ (+0ч)", "+24ч (+1 сут)", "+48ч (+2 сут)",
  "+72ч (+3 сут)", "+96ч (+4 сут)", "+120ч (+5 сут)"
];
const GFS_SHORT = ["+0ч", "+24ч", "+48ч", "+72ч", "+96ч", "+120ч"];

const GFS_PARAMS = {
  "gfs_t":     "Темп. поверхности",
  "gfs_2t":    "Темп. воздуха 2м",
  "gfs_prmsl": "Давление (MSL)",
  "gfs_wind":  "Скорость ветра 10м",
  "gfs_tcc":   "Облачность",
  "gfs_pwat":  "Запас воды (PWAT)",
};

// Russian month names for date formatting
const RU_MONTHS_SHORT = ["янв","фев","мар","апр","май","июн","июл","авг","сен","окт","ноя","дек"];

function _formatValidTime(runLabel, fhour) {
  // runLabel like "2026-04-13 00Z"
  // Returns e.g. "13 апр 03:00" or "13 апр 00:00 (анализ)"
  try {
    const m = runLabel.match(/(\d{4})-(\d{2})-(\d{2})/);
    if (!m) return fhour === 0 ? "Анализ" : `+${fhour}ч`;
    const base = new Date(Date.UTC(+m[1], +m[2]-1, +m[3], 0, 0, 0));
    const valid = new Date(base.getTime() + fhour * 3600 * 1000);
    const d   = valid.getUTCDate();
    const mon = RU_MONTHS_SHORT[valid.getUTCMonth()];
    const h   = String(valid.getUTCHours()).padStart(2, "0");
    const suffix = fhour === 0 ? " (анализ)" : "";
    return `${d} ${mon} ${h}:00 UTC${suffix}`;
  } catch (_) {
    return `+${fhour}ч`;
  }
}

// ──────────────────────────────────────────────
// State
// ──────────────────────────────────────────────
const S = {
  periodIdx:       0,      // index into GFS_FHOURS
  gfsParam:        "gfs_t", // active GFS parameter
  percentile:      "99",
  scale:           2,
  smooth:          true,
  blur:            true,
  coastline:       true,
  contours:        true,
  contourLabels:   true,
  showStations:    true,
  showWindAnim:    false,
  _cmpBuildId:     0,
  viewMode:        "compare",   // "compare" | "detail"
  _detailTab:      "map",       // active tab in detail mode
  _periodSelected: false,
  gfsMeta:         null,
  map:             null,
  imageLayer:      null,
  coastlineLayer:  null,
  stationsLayer:   null,
  windAnimLayer:   null,
  popup:           null,
  _hoverTimer:     null,
  _imageExtent:    null,
  _serverTs:       "0",
  _monTab:         "dashboard",
};

// Mercator extent for the North Pacific domain (lon 117-246°, lat 26-72°),
// computed from EPSG:4326 → EPSG:3857.
const _EARTH_CIRC = 40075016.686;

// ──────────────────────────────────────────────
// Coordinate helpers
// ──────────────────────────────────────────────
function formatCoord(lat, lon) {
  const latD = Math.floor(Math.abs(lat)), latM = Math.round((Math.abs(lat) - latD) * 60);
  const lonD = Math.floor(Math.abs(lon)), lonM = Math.round((Math.abs(lon) - lonD) * 60);
  return `${latD}°${latM}′${lat >= 0 ? "с.ш." : "ю.ш."} ${lonD}°${lonM}′${lon >= 0 ? "в.д." : "з.д."}`;
}

function lonNorm(lon) { return lon > 180 ? lon - 360 : lon; }

function inBounds(lat, lon360) {
  const lon = lon360 < 0 ? lon360 + 360 : lon360;
  return lat >= 26 && lat <= 72 && lon >= 117 && lon <= 246;
}

// ──────────────────────────────────────────────
// Loading overlay
// ──────────────────────────────────────────────
function showLoading(msg) {
  const el = document.getElementById("loading-overlay");
  if (el) el.classList.remove("hidden");
  const t = document.getElementById("loading-text");
  if (t) t.textContent = msg || "Загрузка…";
}
function hideLoading() {
  const el = document.getElementById("loading-overlay");
  if (el) el.classList.add("hidden");
}

// ──────────────────────────────────────────────
// Init
// ──────────────────────────────────────────────
async function init() {
  _loadStateFromLocalStorage();
  showLoading("Загрузка метаданных GFS…");
  try {
    const res = await fetch("/api/gfs/meta");
    if (!res.ok) throw new Error(res.statusText);
    S.gfsMeta = await res.json();
  } catch (e) {
    hideLoading();
    alert("Не удалось загрузить метаданные GFS.\n" + e);
    return;
  }

  // Update run label
  const runLabel = S.gfsMeta.run_label || "—";
  const ri = document.getElementById("run-info");
  if (ri) ri.textContent = runLabel;
  const cl = document.getElementById("cmp-run-label");
  if (cl) cl.textContent = runLabel;

  // Mercator extent of the render domain — computed locally so the map can be
  // built before any tile request completes (backend reports the same values
  // in gfsMeta.mercator_extent).
  const _tr = (lon, lat) => {
    const x = lon / 360 * _EARTH_CIRC;
    const latR = lat * Math.PI / 180;
    const y = Math.log(Math.tan(Math.PI / 4 + latR / 2)) * _EARTH_CIRC / (2 * Math.PI);
    return [x, y];
  };
  const [xMin] = _tr(117.0, 26.0);
  const xMax   = xMin + (246.0 - 117.0) / 360.0 * _EARTH_CIRC;
  const [, yMin] = _tr(0, 26.0);
  const [, yMax] = _tr(0, 72.0);
  S._imageExtent = [xMin, yMin, xMax, yMax];
  S._serverTs = String(Date.now());

  try {
    initMap();
    _loadCoastlineLayer();
    buildPeriodButtons();
    syncUI();
    await _applyViewMode();
  } catch (e) {
    console.error("Init error:", e);
    document.getElementById("loading-text").textContent = "Ошибка инициализации: " + e.message;
    return;
  }
  hideLoading();
  document.addEventListener("click", _onDocClick);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      _hidePopup();
      closePanel();
      return;
    }

    // Ignore keyboard shortcuts if the user is currently typing in an input, textarea, or select element
    const activeEl = document.activeElement;
    if (activeEl && (
      activeEl.tagName === "INPUT" ||
      activeEl.tagName === "TEXTAREA" ||
      activeEl.tagName === "SELECT" ||
      activeEl.isContentEditable
    )) {
      return;
    }

    // Normalizing key string to lower-case and checking Cyrillic equivalents
    const key = e.key.toLowerCase();

    // 1. Cycle forecast hours with ArrowLeft and ArrowRight
    if (e.key === "ArrowLeft") {
      e.preventDefault();
      let prevIdx = S.periodIdx - 1;
      if (prevIdx < 0) prevIdx = GFS_FHOURS.length - 1;
      S.periodIdx = prevIdx;
      S._periodSelected = true;
      _saveStateToLocalStorage("periodIdx");
      syncUI();
      if (S.viewMode === "compare") {
        _buildCompareGrid();
      } else {
        refreshMap();
      }
    } else if (e.key === "ArrowRight") {
      e.preventDefault();
      let nextIdx = S.periodIdx + 1;
      if (nextIdx >= GFS_FHOURS.length) nextIdx = 0;
      S.periodIdx = nextIdx;
      S._periodSelected = true;
      _saveStateToLocalStorage("periodIdx");
      syncUI();
      if (S.viewMode === "compare") {
        _buildCompareGrid();
      } else {
        refreshMap();
      }
    }

    // 2. Toggle wind animation ('w' or 'ц')
    else if (key === "w" || key === "ц") {
      e.preventDefault();
      toggleWindAnim(!S.showWindAnim);
    }

    // 3. Toggle stations layer ('s' or 'ы')
    else if (key === "s" || key === "ы") {
      e.preventDefault();
      toggleStations(!S.showStations);
    }

    // 4. Toggle coastline layer ('c' or 'с')
    else if (key === "c" || key === "с") {
      e.preventDefault();
      setCoastline(!S.coastline);
    }

    // 5. Cycle GFS parameters ('p' or 'з')
    else if (key === "p" || key === "з") {
      e.preventDefault();
      const paramsList = Object.keys(GFS_PARAMS);
      const currIdx = paramsList.indexOf(S.gfsParam);
      let nextParamIdx = currIdx + 1;
      if (nextParamIdx >= paramsList.length || nextParamIdx < 0) {
        nextParamIdx = 0;
      }
      setParam(paramsList[nextParamIdx]);
    }
  });
}

// ──────────────────────────────────────────────
// Map init
// ──────────────────────────────────────────────
function _buildMaskLayer(extent) {
  const [xMin, yMin, xMax, yMax] = extent;
  const HUGE = 40075016 * 3;
  const color = "rgba(8,10,22,0.88)";
  const rects = [
    [[-HUGE, yMax], [HUGE, yMax], [HUGE, HUGE], [-HUGE, HUGE], [-HUGE, yMax]],
    [[-HUGE, -HUGE], [HUGE, -HUGE], [HUGE, yMin], [-HUGE, yMin], [-HUGE, -HUGE]],
    [[-HUGE, yMin], [xMin, yMin], [xMin, yMax], [-HUGE, yMax], [-HUGE, yMin]],
    [[xMax, yMin], [HUGE, yMin], [HUGE, yMax], [xMax, yMax], [xMax, yMin]],
  ];
  const style = new ol.style.Style({ fill: new ol.style.Fill({ color }) });
  const features = rects.map(coords => {
    const f = new ol.Feature({ geometry: new ol.geom.Polygon([coords]) });
    f.setStyle(style);
    return f;
  });
  return new ol.layer.Vector({ source: new ol.source.Vector({ features }), zIndex: 8 });
}

function _buildRuLabelsLayer() {
  const places = [
    { lon: 175, lat: 40,  text: "Тихий океан",   size: 15, bold: true },
    { lon: 148, lat: 55,  text: "Охотское море",  size: 11, bold: false },
    { lon: -178,lat: 61,  text: "Берингово море", size: 11, bold: false, ext: true },
    { lon: 134, lat: 38,  text: "Японское море",  size: 10, bold: false },
    { lon: 115, lat: 64,  text: "РОССИЯ",         size: 13, bold: true },
    { lon: 150, lat: 66,  text: "РОССИЯ",         size: 12, bold: true },
    { lon: -150,lat: 64,  text: "АЛЯСКА",         size: 12, bold: true, ext: true },
    { lon: -125,lat: 55,  text: "КАНАДА",         size: 13, bold: true, ext: true },
    { lon: -122,lat: 42,  text: "США",            size: 13, bold: true, ext: true },
    { lon: 140, lat: 36,  text: "ЯПОНИЯ",         size: 11, bold: true },
    { lon: 110, lat: 32,  text: "КИТАЙ",          size: 12, bold: true },
    { lon: 128, lat: 37,  text: "КОРЕЯ",          size: 10, bold: false },
  ];
  const features = places.map(p => {
    const coord = ol.proj.fromLonLat([p.lon, p.lat]);
    if (p.ext) coord[0] += _EARTH_CIRC;
    const f = new ol.Feature({ geometry: new ol.geom.Point(coord) });
    f.setStyle(new ol.style.Style({
      text: new ol.style.Text({
        text:         p.text,
        font:         `${p.bold ? "600" : "400"} ${p.size}px Inter, system-ui`,
        fill:         new ol.style.Fill({ color: "rgba(40,40,60,0.65)" }),
        stroke:       new ol.style.Stroke({ color: "rgba(255,255,255,0.8)", width: 3 }),
        overflow:     true,
        placement:    "point",
        textAlign:    "center",
      }),
    }));
    return f;
  });
  return new ol.layer.Vector({
    source: new ol.source.Vector({ features }),
    zIndex: 15,
    declutter: true,
  });
}

function initMap() {
  const baseTile = new ol.layer.Tile({
    source: new ol.source.XYZ({
      url:         "https://{a-d}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}.png",
      attributions:"© CartoDB © OpenStreetMap contributors",
      maxZoom:     19,
      crossOrigin: "anonymous",
      wrapX:       true,
    }),
    opacity: 1.0, zIndex: 1,
  });

  S.imageLayer = new ol.layer.Image({ opacity: 0.82, zIndex: 5, source: null });

  const graticule = new ol.layer.Graticule({
    strokeStyle: new ol.style.Stroke({ color: "rgba(120,120,150,0.35)", width: 0.6, lineDash: [3, 5] }),
    showLabels: true, wrapX: false, zIndex: 20,
    lonLabelStyle: new ol.style.Text({ font: "10px Inter, monospace", fill: new ol.style.Fill({ color: "rgba(60,60,80,0.7)" }) }),
    latLabelStyle: new ol.style.Text({ font: "10px Inter, monospace", fill: new ol.style.Fill({ color: "rgba(60,60,80,0.7)" }) }),
  });

  const popupEl = document.getElementById("map-popup");
  S.popup = new ol.Overlay({
    element:     popupEl,
    positioning: "bottom-center",
    offset:      [0, -6],
    autoPan:     { animation: { duration: 200 } },
    stopEvent:   true,
  });

  const viewCenter = [
    (S._imageExtent[0] + S._imageExtent[2]) / 2,
    (S._imageExtent[1] + S._imageExtent[3]) / 2,
  ];

  const ruLabels = _buildRuLabelsLayer();

  S.map = new ol.Map({
    target:   "map",
    layers:   [baseTile, S.imageLayer, ruLabels, graticule],
    overlays: [S.popup],
    view: new ol.View({
      projection:     "EPSG:3857",
      center:         viewCenter,
      zoom:           3,
      minZoom:        3,
      maxZoom:        10,
      enableRotation: false,
      extent: [
        S._imageExtent[0] - 80000, S._imageExtent[1] - 80000,
        S._imageExtent[2] + 80000, S._imageExtent[3] + 80000,
      ],
    }),
  });

  S.map.once("rendercomplete", () => {
    if (!S._imageExtent) return;
    S.map.getView().fit(S._imageExtent, { padding: [10, 80, 60, 80], maxZoom: 5 });
  });

  S.map.on("click",        onMapClick);
  S.map.on("pointermove",  onPointerMove);
}

// ──────────────────────────────────────────────
// Coastline layer
// ──────────────────────────────────────────────
async function _loadCoastlineLayer() {
  const fmt = new ol.format.GeoJSON();
  let data;
  try {
    data = await fetch("/api/coastline.geojson").then(r => r.json());
  } catch (e) {
    console.warn("Coastline load failed:", e);
    return;
  }
  const westFeats = fmt.readFeatures(
    { type: "FeatureCollection", features: data.features.filter(f => f.properties.half === "west") },
    { featureProjection: "EPSG:3857", dataProjection: "EPSG:4326" }
  );
  const eastFeats = fmt.readFeatures(
    { type: "FeatureCollection", features: data.features.filter(f => f.properties.half === "east") },
    { featureProjection: "EPSG:3857", dataProjection: "EPSG:4326" }
  );
  eastFeats.forEach(f => {
    f.getGeometry().applyTransform((coords, out, stride) => {
      stride = stride || 2;
      for (let i = 0; i < coords.length; i += stride) {
        out[i]   = coords[i] + _EARTH_CIRC;
        out[i+1] = coords[i+1];
      }
      return out;
    });
  });
  const source = new ol.source.Vector({ features: [...westFeats, ...eastFeats] });
  S.coastlineLayer = new ol.layer.Vector({
    source,
    style: [
      new ol.style.Style({ stroke: new ol.style.Stroke({ color: "rgba(15,25,50,0.12)", width: 3.5 }) }),
      new ol.style.Style({ stroke: new ol.style.Stroke({ color: "rgba(15,25,55,0.50)", width: 0.8 }) }),
    ],
    zIndex: 9,
    visible: S.coastline,
  });
  S.map.addLayer(S.coastlineLayer);
}

// ──────────────────────────────────────────────
// Build map URL query string
// ──────────────────────────────────────────────
function _mapParams(extra = {}) {
  const p = {
    percentile: S.percentile,
    ...(S.scale > 1 ? { scale: S.scale } : {}),
    ...(!S.blur ? { blur: 0 } : {}),
    ...(!S.contours ? { contours: 0 } : {}),
    ...(S.contourLabels ? { contour_labels: 1 } : {}),
    ...extra,
  };
  return new URLSearchParams(p).toString();
}

// Current forecast-hour index, clamped to the available range
function _fhIdx() {
  return Math.max(0, Math.min(S.periodIdx, GFS_FHOURS.length - 1));
}

function _mapUrl(param, fhIdx, extra = {}) {
  return `/api/gfs/map/${param}/${fhIdx}.png?${_mapParams(extra)}`;
}

function _colorscaleUrl(param, fhIdx) {
  const q = new URLSearchParams({ fhour_idx: fhIdx, percentile: S.percentile });
  return `/api/gfs/colorscale/${param}?${q}`;
}

// ──────────────────────────────────────────────
// Refresh map image
// ──────────────────────────────────────────────
async function refreshMap() {
  const fhIdx  = _fhIdx();
  const param  = S.gfsParam || "gfs_t";
  const mapUrl = _mapUrl(param, fhIdx);
  const csUrl  = _colorscaleUrl(param, fhIdx);

  if (S._imageExtent) {
    S.imageLayer.setSource(null);
    const src = new ol.source.ImageStatic({
      url:            mapUrl,
      imageExtent:    S._imageExtent,
      crossOrigin:    "anonymous",
      imageSmoothing: S.smooth,
    });
    S.imageLayer.setSource(src);
  }

  try {
    const cs = await fetch(csUrl).then(r => r.json());
    renderLegend(cs);
  } catch (_) {}
}

// ──────────────────────────────────────────────
// Legend (vertical bands)
// ──────────────────────────────────────────────
function renderLegend(cs) {
  const rawUnit = cs.unit || "";
  const unitEl = document.getElementById("legend-unit");
  unitEl.textContent = "";
  unitEl.style.display = "none";
  document.getElementById("legend-ticks").innerHTML = "";

  const canvas = document.getElementById("legend-canvas");
  const ctx    = canvas.getContext("2d");

  const allTicks = (cs.ticks || []).slice().sort((a, b) => a.norm - b.norm);
  const ticks    = allTicks.filter(t => t.norm > 0.02 && t.norm < 0.98);
  const N = ticks.length;
  const UNIT_H = rawUnit ? 20 : 0;
  const BAND_H = Math.max(20, Math.floor(280 / Math.max(N, 1)));

  if (N < 1) {
    canvas.width = 52; canvas.height = 300;
    ctx.clearRect(0, 0, 52, 300);
    for (let y = 0; y < 300; y++) {
      const idx = Math.round((1 - y / 299) * 255);
      const [r, g, b] = cs.lut[idx];
      ctx.fillStyle = `rgb(${r},${g},${b})`;
      ctx.fillRect(0, y, 52, 1);
    }
    return;
  }
  ctx.font = "bold 11px Inter, system-ui";
  const maxLabelW = Math.max(
    ...ticks.map(t => ctx.measureText(t.label).width),
    rawUnit ? ctx.measureText(rawUnit).width : 0
  );
  const PAD = 8;
  const W   = Math.max(44, Math.ceil(maxLabelW) + PAD * 2);
  const H   = UNIT_H + N * BAND_H;
  canvas.width = W; canvas.height = H;
  ctx.clearRect(0, 0, W, H);

  if (rawUnit) {
    ctx.fillStyle = "rgba(240,240,245,0.95)";
    ctx.fillRect(0, 0, W, UNIT_H);
    ctx.font = "bold 10px Inter, system-ui";
    ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.fillStyle = "#1a2030";
    ctx.fillText(rawUnit, W / 2, UNIT_H / 2);
  }
  ctx.font = "bold 11px Inter, system-ui";
  ctx.textAlign = "center"; ctx.textBaseline = "middle";
  for (let i = 0; i < N; i++) {
    const tick = ticks[N - 1 - i];
    const y0   = UNIT_H + i * BAND_H;
    const lutIdx = Math.max(0, Math.min(255, Math.round(tick.norm * 255)));
    const [r, g, b] = cs.lut[lutIdx];
    ctx.fillStyle = `rgb(${r},${g},${b})`;
    ctx.fillRect(0, y0, W, BAND_H);
    const lum = 0.299 * r + 0.587 * g + 0.114 * b;
    ctx.fillStyle   = lum > 128 ? "rgba(0,0,0,0.85)" : "rgba(255,255,255,0.95)";
    ctx.shadowColor = lum > 128 ? "rgba(255,255,255,0.4)" : "rgba(0,0,0,0.5)";
    ctx.shadowBlur  = 2;
    ctx.fillText(tick.label, W / 2, y0 + BAND_H / 2);
    ctx.shadowBlur  = 0;
  }
}

// Horizontal legend for compare view
function _renderLegendH(cs) {
  const container = document.getElementById("cmp-legend-h");
  if (!container) return;
  const rawUnit = (cs.unit || "");
  const allTicks = (cs.ticks || []).slice().sort((a, b) => a.norm - b.norm);
  const ticks = allTicks.filter(t => t.norm > 0.02 && t.norm < 0.98);
  const N = ticks.length;
  if (N < 1) { container.innerHTML = ""; return; }
  let canvas = container.querySelector("canvas");
  if (!canvas) {
    canvas = document.createElement("canvas");
    container.innerHTML = "";
    container.appendChild(canvas);
  }
  const ctx = canvas.getContext("2d");
  const BAND_H = 28;
  const UNIT_W = rawUnit ? 38 : 0;
  ctx.font = "bold 10px Inter, system-ui";
  const minBandW = Math.max(34, Math.ceil(Math.max(...ticks.map(t => ctx.measureText(t.label).width))) + 10);
  const W = UNIT_W + N * minBandW;
  canvas.width = W; canvas.height = BAND_H;
  ctx.clearRect(0, 0, W, BAND_H);
  if (rawUnit) {
    ctx.fillStyle = "rgba(230,232,240,0.95)";
    ctx.fillRect(0, 0, UNIT_W, BAND_H);
    ctx.font = "bold 9px Inter, system-ui";
    ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.fillStyle = "#1a2030";
    ctx.fillText(rawUnit, UNIT_W / 2, BAND_H / 2);
  }
  ctx.font = "bold 10px Inter, system-ui";
  ctx.textAlign = "center"; ctx.textBaseline = "middle";
  ticks.forEach((tick, i) => {
    const x0 = UNIT_W + i * minBandW;
    const lutIdx = Math.max(0, Math.min(255, Math.round(tick.norm * 255)));
    const [r, g, b] = cs.lut[lutIdx];
    ctx.fillStyle = `rgb(${r},${g},${b})`;
    ctx.fillRect(x0, 0, minBandW, BAND_H);
    const lum = 0.299 * r + 0.587 * g + 0.114 * b;
    ctx.fillStyle   = lum > 128 ? "rgba(0,0,0,0.85)" : "rgba(255,255,255,0.95)";
    ctx.shadowColor = lum > 128 ? "rgba(255,255,255,0.4)" : "rgba(0,0,0,0.5)";
    ctx.shadowBlur = 2;
    ctx.fillText(tick.label, x0 + minBandW / 2, BAND_H / 2);
    ctx.shadowBlur = 0;
  });
}

// ──────────────────────────────────────────────
// Refresh legend (both compare and detail)
// ──────────────────────────────────────────────
async function _refreshLegend() {
  const fhIdx = _fhIdx();
  const param = S.gfsParam || "gfs_t";
  const csUrl = _colorscaleUrl(param, fhIdx);
  try {
    const cs = await fetch(csUrl).then(r => r.json());
    if (S.viewMode === "compare") {
      _renderLegendH(cs);
    } else {
      renderLegend(cs);
    }
  } catch (_) {}
}

// ──────────────────────────────────────────────
// Period buttons (forecast hours)
// ──────────────────────────────────────────────
function buildPeriodButtons() {
  const container = document.getElementById("period-btns");
  if (!container) return;
  container.innerHTML = "";

  GFS_SHORT.forEach((lbl, i) => {
    const btn = document.createElement("button");
    const isActive = S._periodSelected && i === S.periodIdx;
    btn.className = "period-btn" + (isActive ? " active" : "");
    btn.setAttribute("aria-label", `Горизонт прогноза ${GFS_LABELS[i]}`);
    btn.setAttribute("aria-pressed", isActive ? "true" : "false");
    btn.textContent = lbl;
    btn.onclick = () => {
      S.periodIdx = i;
      S._periodSelected = true;
      _saveStateToLocalStorage("periodIdx");
      closePanel();
      if (S.viewMode === "compare") {
        S.viewMode = "detail";
        _applyViewMode();
      } else {
        syncUI();
        refreshMap();
      }
    };
    container.appendChild(btn);
  });
}

// ──────────────────────────────────────────────
// Compare grid — 6 forecast-hour maps (2 rows × 3 cols)
// ──────────────────────────────────────────────
async function _buildCompareGrid() {
  S._cmpBuildId = (S._cmpBuildId || 0) + 1;
  const buildId = S._cmpBuildId;
  const smooth  = S.smooth ? "auto" : "pixelated";

  const grid = document.getElementById("compare-grid");
  while (grid.firstChild) grid.removeChild(grid.firstChild);
  grid.style.gridTemplateColumns = "repeat(3, 1fr)";

  const param    = S.gfsParam || "gfs_t";
  const runLabel = S.gfsMeta?.run_label || "";
  GFS_LABELS.forEach((lbl, i) => {
    const fhour = GFS_FHOURS[i];
    const url = _mapUrl(param, i, { _v: `${S._serverTs}_${buildId}` });
    const validTime = _formatValidTime(runLabel, fhour);

    const cell = document.createElement("div");
    cell.className = "cmp-cell" + (S._periodSelected && i === S.periodIdx ? " active" : "");
    cell.setAttribute("role", "button");
    cell.setAttribute("tabindex", "0");
    cell.setAttribute("aria-label", `${lbl}: ${validTime}. Нажмите для подробного просмотра`);

    const selectCell = () => {
      S.periodIdx       = i;
      S._periodSelected = true;
      _saveStateToLocalStorage("periodIdx");
      S.viewMode        = "detail";
      closePanel();
      _applyViewMode();
    };

    cell.onclick = selectCell;
    cell.onkeydown = (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        selectCell();
      }
    };

    const lbl_el = document.createElement("div");
    lbl_el.className = "cmp-label";
    lbl_el.innerHTML = `<span class="cmp-lbl-short">${GFS_SHORT[i]}</span><span class="cmp-lbl-date">${validTime}</span>`;

    const wrap = document.createElement("div");
    wrap.className = "cmp-map-wrap";

    const img = document.createElement("img");
    img.className = "cmp-img";
    img.loading   = "eager";
    img.src       = url;
    img.alt       = lbl;
    img.style.imageRendering = smooth;

    const coast = document.createElement("img");
    coast.className = "cmp-coast";
    coast.src       = "/api/coastline.svg";
    coast.alt       = "";
    coast.style.display = S.coastline ? "" : "none";

    wrap.appendChild(img);
    wrap.appendChild(coast);

    cell.appendChild(lbl_el);
    cell.appendChild(wrap);
    grid.appendChild(cell);
  });
}

// ──────────────────────────────────────────────
// UI sync
// ──────────────────────────────────────────────
function syncUI() {
  const { periodIdx, percentile, scale, smooth, blur } = S;

  // Sync param selects
  ["cmp-param-select", "lp-param-select"].forEach(id => {
    const sel = document.getElementById(id);
    if (sel && sel.value !== S.gfsParam) sel.value = S.gfsParam;
  });

  // Update detail period label
  if (S.viewMode === "detail") _updateDetailPeriodLabel();

  const syncGroup = (selector, isActFn) => {
    document.querySelectorAll(selector).forEach((b, i) => {
      const active = isActFn(b, i);
      b.classList.toggle("active", active);
      b.setAttribute("aria-pressed", active ? "true" : "false");
    });
  };

  syncGroup(".pct-btn", b => b.dataset.pct === String(percentile));
  syncGroup(".scale-btn", b => Number(b.dataset.scale) === scale);
  syncGroup(".smooth-btn", b => (b.dataset.smooth === "1") === smooth);
  syncGroup(".blur-btn", b => (b.dataset.blur === "1") === blur);
  syncGroup(".coast-btn", b => (b.dataset.coast === "1") === S.coastline);
  syncGroup(".contour-btn", b => (b.dataset.contour === "1") === S.contours);
  syncGroup(".contlbl-btn", b => (b.dataset.contlbl === "1") === S.contourLabels);
  syncGroup(".period-btn", (_, i) => S._periodSelected && i === periodIdx);

  // Sync station and wind anim toggle buttons aria-pressed
  document.querySelectorAll(".station-toggle-btn").forEach(b => {
    const active = b.textContent.includes("Вкл") === S.showStations;
    b.setAttribute("aria-pressed", active ? "true" : "false");
  });
  document.querySelectorAll(".wind-anim-btn").forEach(b => {
    const active = (b.textContent.includes("Вкл") && S.showWindAnim) || (b.textContent.includes("Выкл") && !S.showWindAnim);
    b.setAttribute("aria-pressed", active ? "true" : "false");
  });
}

// ──────────────────────────────────────────────
// View mode: compare ↔ detail
// ──────────────────────────────────────────────
function goCompare() {
  S.viewMode = "compare";
  _applyViewMode();
}

async function _applyViewMode() {
  const compareEl  = document.getElementById("compare-view");
  const backBtn    = document.getElementById("back-btn");
  const mapEl      = document.getElementById("map");
  const legend     = document.getElementById("legend");
  const cmpLegendH = document.getElementById("cmp-legend-h");

  const detailNav  = document.getElementById("detail-nav");
  const panelToggle = document.getElementById("panel-toggle");

  if (S.viewMode === "compare") {
    document.body.classList.remove("detail-mode");
    compareEl.classList.remove("hidden");
    if (detailNav)    detailNav.style.display  = "none";
    if (mapEl)        mapEl.style.display      = "none";
    if (legend)       legend.classList.add("hidden");
    if (cmpLegendH)   cmpLegendH.classList.remove("hidden");
    if (panelToggle)  panelToggle.style.display = "none";
    if (backBtn)      backBtn.style.display     = "none";
    // Hide all detail panels and overlay views
    document.querySelectorAll(".detail-panel").forEach(p => p.classList.remove("active"));
    const _fvEl = document.getElementById("forecast-view");
    if (_fvEl) _fvEl.style.display = "none";
    closePanel();
    await _buildCompareGrid();
    await _refreshLegend();
  } else {
    // Detail mode
    document.body.classList.add("detail-mode");
    compareEl.classList.add("hidden");
    if (detailNav)    detailNav.style.display  = "flex";
    if (mapEl)        mapEl.style.display      = "";
    if (legend)       legend.classList.remove("hidden");
    if (cmpLegendH)   cmpLegendH.classList.add("hidden");
    if (panelToggle)  panelToggle.style.display = "";
    if (backBtn)      backBtn.style.display     = "none";  // replaced by detailNav back btn
    // Update period label in nav bar
    _updateDetailPeriodLabel();
    if (S.map) S.map.updateSize();
    syncUI();
    // Default tab: map
    showDetailTab(S._detailTab || "map");
    await refreshMap();
    if (typeof initStationsLayer === "function") initStationsLayer();
  }
}

// ──────────────────────────────────────────────
// Settings handlers
// ──────────────────────────────────────────────
function _saveStateToLocalStorage(key) {
  try {
    localStorage.setItem(`gfs_dashboard_${key}`, String(S[key]));
  } catch (e) {
    console.warn("localStorage write failed:", e);
  }
}

function _loadStateFromLocalStorage() {
  const keys = [
    { key: "periodIdx", type: "int" },
    { key: "gfsParam", type: "string" },
    { key: "percentile", type: "string" },
    { key: "scale", type: "int" },
    { key: "smooth", type: "bool" },
    { key: "blur", type: "bool" },
    { key: "coastline", type: "bool" },
    { key: "contours", type: "bool" },
    { key: "contourLabels", type: "bool" },
    { key: "showStations", type: "bool" },
    { key: "showWindAnim", type: "bool" }
  ];
  keys.forEach(({ key, type }) => {
    try {
      const val = localStorage.getItem(`gfs_dashboard_${key}`);
      if (val !== null) {
        if (type === "int") {
          S[key] = parseInt(val, 10);
          if (key === "periodIdx") S._periodSelected = true;
        } else if (type === "bool") {
          S[key] = val === "true";
        } else {
          S[key] = val;
        }
      }
    } catch (e) {
      console.warn("localStorage read failed:", e);
    }
  });
}

function setBlur(on) {
  S.blur = on;
  _saveStateToLocalStorage("blur");
  syncUI();
  if (S.viewMode === "compare") { _buildCompareGrid(); _refreshLegend(); }
  else refreshMap();
}
function setContours(on) {
  S.contours = on;
  if (!on) S.contourLabels = false;
  _saveStateToLocalStorage("contours");
  _saveStateToLocalStorage("contourLabels");
  syncUI();
  if (S.viewMode === "compare") { _buildCompareGrid(); _refreshLegend(); }
  else refreshMap();
}
function setContourLabels(on) {
  S.contourLabels = on;
  _saveStateToLocalStorage("contourLabels");
  syncUI();
  if (S.viewMode === "compare") { _buildCompareGrid(); _refreshLegend(); }
  else refreshMap();
}
function setPct(pct) {
  S.percentile = pct;
  _saveStateToLocalStorage("percentile");
  syncUI();
  if (S.viewMode === "compare") { _buildCompareGrid(); _refreshLegend(); }
  else refreshMap();
}
function setScale(n) {
  S.scale = n;
  _saveStateToLocalStorage("scale");
  syncUI();
  if (S.viewMode === "compare") _buildCompareGrid();
  else refreshMap();
}
function setSmooth(on) {
  S.smooth = on;
  _saveStateToLocalStorage("smooth");
  _applySmoothing();
  syncUI();
  if (S.viewMode === "detail") refreshMap();
  else _buildCompareGrid();
}
function setCoastline(on) {
  S.coastline = on;
  if (S.coastlineLayer) S.coastlineLayer.setVisible(on);
  document.querySelectorAll(".cmp-coast").forEach(el => { el.style.display = on ? "" : "none"; });
  _saveStateToLocalStorage("coastline");
  syncUI();
}

function setParam(param) {
  S.gfsParam = param;
  _saveStateToLocalStorage("gfsParam");
  _gfs_png_cache_bust();
  syncUI();
  if (S.viewMode === "compare") { _buildCompareGrid(); _refreshLegend(); }
  else { refreshMap(); _updateDetailPeriodLabel(); }
}

// Bust image URLs by changing S._serverTs
function _gfs_png_cache_bust() {
  S._serverTs = String(Date.now());
}

function toggleStations(on) {
  S.showStations = on;
  _saveStateToLocalStorage("showStations");
  document.querySelectorAll(".station-toggle-btn").forEach(b => {
    const active = b.textContent.includes("Вкл") === on;
    b.classList.toggle("active", active);
    b.setAttribute("aria-pressed", active ? "true" : "false");
  });
  if (typeof updateStationsVisibility === "function") updateStationsVisibility(on);
}

function toggleWindAnim(on) {
  S.showWindAnim = on;
  _saveStateToLocalStorage("showWindAnim");
  document.querySelectorAll(".wind-anim-btn").forEach(b => {
    const active = (b.textContent.includes("Вкл") && on) || (b.textContent.includes("Выкл") && !on);
    b.classList.toggle("active", active);
    b.setAttribute("aria-pressed", active ? "true" : "false");
  });
  if (on) {
    _startWindAnimation();
  } else {
    _stopWindAnimation();
  }
}

let _windAnimCanvas = null;
let _windAnimFrame  = null;
let _windData       = null;

async function _startWindAnimation() {
  const fhIdx = _fhIdx();
  try {
    _windData = await fetch(`/api/gfs/wind/${fhIdx}`).then(r => r.json());
  } catch (e) {
    console.warn("Wind data load failed:", e); return;
  }
  // Create canvas overlay on the map
  const mapEl = document.getElementById("map");
  if (!_windAnimCanvas) {
    _windAnimCanvas = document.createElement("canvas");
    _windAnimCanvas.style.cssText = "position:absolute;top:0;left:0;pointer-events:none;z-index:50";
    mapEl.appendChild(_windAnimCanvas);
  }
  _windAnimCanvas.width  = mapEl.offsetWidth;
  _windAnimCanvas.height = mapEl.offsetHeight;
  _animateWindFrame();
}

function _stopWindAnimation() {
  if (_windAnimFrame) { cancelAnimationFrame(_windAnimFrame); _windAnimFrame = null; }
  if (_windAnimCanvas) { _windAnimCanvas.getContext("2d").clearRect(0, 0, _windAnimCanvas.width, _windAnimCanvas.height); }
}

const _windParticles = [];
function _animateWindFrame() {
  if (!_windData || !S.showWindAnim || !S.map) return;
  const canvas = _windAnimCanvas;
  const ctx    = canvas.getContext("2d");
  const W = canvas.width, H = canvas.height;

  // Init particles if empty
  if (_windParticles.length === 0) {
    for (let i = 0; i < 600; i++) {
      _windParticles.push({ x: Math.random() * W, y: Math.random() * H, age: Math.random() * 60 });
    }
  }

  ctx.fillStyle = "rgba(8,10,22,0.06)";
  ctx.fillRect(0, 0, W, H);

  const view     = S.map.getView();
  const extent   = view.calculateExtent(S.map.getSize());
  const lats     = _windData.lat;
  const lons     = _windData.lon;
  const us       = _windData.u;
  const vs       = _windData.v;
  const nlat     = lats.length;
  const nlon     = lons.length;
  const maxAge   = 80;

  const _EARTH_C = 40075016.686;
  function mercX(lon360) { return lon360 / 360 * _EARTH_C; }
  function mercY(lat)    {
    const r = lat * Math.PI / 180;
    return Math.log(Math.tan(Math.PI / 4 + r / 2)) * _EARTH_C / (2 * Math.PI);
  }
  function toPixel(lon360, lat) {
    const mx = mercX(lon360), my = mercY(lat);
    const px = (mx - extent[0]) / (extent[2] - extent[0]) * W;
    const py = (1 - (my - extent[1]) / (extent[3] - extent[1])) * H;
    return [px, py];
  }
  function fromPixel(px, py) {
    const mx = extent[0] + px / W * (extent[2] - extent[0]);
    const my = extent[1] + (1 - py / H) * (extent[3] - extent[1]);
    const lon360 = mx / _EARTH_C * 360;
    const lat    = Math.atan(Math.exp(my * 2 * Math.PI / _EARTH_C)) * 2 / Math.PI * 90 * 2 - 90;
    return [lon360, lat];
  }
  function sampleWind(lon360, lat) {
    const gi = (lat - lats[0]) / (lats[nlat-1] - lats[0]) * (nlat - 1);
    const gj = (lon360 - lons[0]) / (lons[nlon-1] - lons[0]) * (nlon - 1);
    const i0 = Math.max(0, Math.min(nlat - 2, Math.floor(gi)));
    const j0 = Math.max(0, Math.min(nlon - 2, Math.floor(gj)));
    const fi = gi - i0, fj = gj - j0;
    return [
      (1-fi)*(1-fj)*us[i0][j0]   + (1-fi)*fj*us[i0][j0+1] +
      fi*(1-fj)*us[i0+1][j0] + fi*fj*us[i0+1][j0+1],
      (1-fi)*(1-fj)*vs[i0][j0]   + (1-fi)*fj*vs[i0][j0+1] +
      fi*(1-fj)*vs[i0+1][j0] + fi*fj*vs[i0+1][j0+1],
    ];
  }

  _windParticles.forEach(p => {
    if (p.age > maxAge || p.x < 0 || p.x > W || p.y < 0 || p.y > H) {
      p.x = Math.random() * W; p.y = Math.random() * H; p.age = 0;
    }
    const [lon360, lat] = fromPixel(p.x, p.y);
    if (lat < 26 || lat > 72 || lon360 < 117 || lon360 > 246) {
      p.x = Math.random() * W; p.y = Math.random() * H; p.age = 0; return;
    }
    const [u, v] = sampleWind(lon360, lat);
    const speed  = Math.sqrt(u*u + v*v);
    const [x1, y1] = toPixel(lon360 + u * 0.04, lat + v * 0.04);
    const alpha = Math.min(0.9, 0.3 + speed / 20);
    ctx.strokeStyle = `rgba(100,200,255,${alpha})`;
    ctx.lineWidth   = 0.8 + speed / 25;
    ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(x1, y1); ctx.stroke();
    p.x = x1; p.y = y1; p.age++;
  });

  _windAnimFrame = requestAnimationFrame(_animateWindFrame);
}

function showMonTab(tab) {
  S._monTab = tab;
  document.querySelectorAll(".mon-tab").forEach(b => {
    b.classList.toggle("active", b.textContent.toLowerCase().includes(
      tab === "dashboard" ? "дашборд" :
      tab === "stations" ? "станции" :
      tab === "agents" ? "агент" :
      tab === "requests" ? "заявки" :
      tab === "forecast" ? "прогноз" :
      tab === "calendar" ? "календарь" : tab
    ));
  });
  const content = document.getElementById("mon-content");
  if (!content) return;
  switch (tab) {
    case "dashboard":
      if (typeof loadDashboard === "function") loadDashboard(content);
      else content.innerHTML = "<div style='opacity:0.5;padding:8px'>Загрузка дашборда…</div>";
      break;
    case "stations":
      if (typeof loadStationsPanel === "function") loadStationsPanel(content);
      else content.innerHTML = "<div style='opacity:0.5;padding:8px'>Загрузка станций…</div>";
      break;
    case "agents":
      if (typeof loadAgentsPanel === "function") loadAgentsPanel(content);
      else content.innerHTML = "<div style='opacity:0.5;padding:8px'>Загрузка агентов…</div>";
      break;
    case "requests":
      if (typeof loadRequestsPanel === "function") loadRequestsPanel(content);
      else content.innerHTML = "<div style='opacity:0.5;padding:8px'>Загрузка заявок…</div>";
      break;
    case "forecast":
      if (typeof loadForecastPanel === "function") loadForecastPanel(content);
      else content.innerHTML = "<div style='opacity:0.5;padding:8px'>Загрузка прогноза…</div>";
      break;
    case "calendar":
      if (typeof loadCalendarPanel === "function") loadCalendarPanel(content);
      else content.innerHTML = "<div style='opacity:0.5;padding:8px'>Загрузка календаря…</div>";
      break;
    default:
      content.innerHTML = "";
  }
}

function _updateDetailPeriodLabel() {
  const el = document.getElementById("detail-period-label");
  if (!el) return;
  const fhour    = GFS_FHOURS[_fhIdx()];
  const runLabel = S.gfsMeta?.run_label || "";
  const paramLbl = GFS_PARAMS[S.gfsParam] || S.gfsParam;
  const validTime = _formatValidTime(runLabel, fhour);
  el.textContent = `${paramLbl} · ${validTime}`;
}

function showDetailTab(tab) {
  S._detailTab = tab;
  // Update active tab button and aria-selected state
  document.querySelectorAll(".detail-tab").forEach(b => {
    const isActive = b.dataset.tab === tab;
    b.classList.toggle("active", isActive);
    b.setAttribute("aria-selected", isActive ? "true" : "false");
  });

  const mapEl     = document.getElementById("map");
  const leftPanel = document.getElementById("left-panel");
  const legend    = document.getElementById("legend");
  const panelToggle = document.getElementById("panel-toggle");

  // Hide all detail panels and overlay views first
  document.querySelectorAll(".detail-panel").forEach(p => p.classList.remove("active"));
  const fvEl = document.getElementById("forecast-view");
  if (fvEl) fvEl.style.display = "none";

  // Tabs that use external JS overlays vs inline panels
  const overlayTabs = ["forecast", "agents", "calendar", "requests"];

  if (tab === "map") {
    if (mapEl)       mapEl.style.display       = "";
    if (legend)      legend.classList.remove("hidden");
    if (panelToggle) panelToggle.style.display  = "";
  } else if (overlayTabs.includes(tab)) {
    // Show overlay on top of map — map stays visible behind
    if (mapEl)       mapEl.style.display       = "";
    if (legend)      legend.classList.add("hidden");
    if (panelToggle) panelToggle.style.display  = "none";
    closePanel();
    if (tab === "forecast" && fvEl) fvEl.style.display = "flex";
    _loadDetailPanel(tab, fvEl || document.createElement("div"));
  } else {
    // Inline panel (monitoring)
    if (mapEl)       mapEl.style.display       = "none";
    if (legend)      legend.classList.add("hidden");
    if (panelToggle) panelToggle.style.display  = "none";
    closePanel();

    const panelId = `detail-panel-${tab}`;
    const panel   = document.getElementById(panelId);
    if (panel) {
      panel.classList.add("active");
      _loadDetailPanel(tab, panel);
    }
  }
}

function _loadDetailPanel(tab, container) {
  switch (tab) {
    case "monitoring":
      // Reload every time so data is fresh
      container.innerHTML = "";
      _renderMonitoringInPanel(container);
      break;
    case "forecast":
      // forecast.js renders into its own #forecast-view div
      if (typeof window.showForecastView === "function") window.showForecastView();
      break;
    case "agents":
      // monitoring.js creates its own fullscreen overlay
      if (typeof window.showMonitoringView === "function") window.showMonitoringView();
      break;
    case "calendar":
      // calendar.js creates its own fullscreen overlay
      if (typeof window.showCalendarView === "function") window.showCalendarView();
      break;
    case "requests":
      // requests_ui.js creates its own fullscreen overlay
      if (typeof window.showRequestsView === "function") window.showRequestsView();
      break;
    default:
      container.innerHTML = "";
  }
}

function _renderMonitoringInPanel(container) {
  container.innerHTML = `
    <div style="padding:20px;max-width:900px;margin:0 auto">
      <div id="mon-inline-summary" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px;margin-bottom:20px"></div>
      <h3 style="margin-bottom:12px;font-size:14px;color:rgba(255,255,255,0.7)">Последние события агентов</h3>
      <div id="mon-inline-feed" style="display:flex;flex-direction:column;gap:8px"></div>
    </div>`;
  _fetchMonitoringSummary(container);
}

async function _fetchMonitoringSummary(container) {
  try {
    const [sumRes, feedRes] = await Promise.all([
      fetch("/api/monitoring/dashboard/summary").then(r => r.ok ? r.json() : null),
      fetch("/api/monitoring/feed?limit=20").then(r => r.ok ? r.json() : []),
    ]);
    const sum  = document.getElementById("mon-inline-summary");
    const feed = document.getElementById("mon-inline-feed");
    if (sum && sumRes) {
      const total = (sumRes.stations_online||0)+(sumRes.stations_warning||0)+(sumRes.stations_critical||0)+(sumRes.stations_offline||0);
      const items = [
        ["Станций всего",   total || "—"],
        ["Онлайн",          sumRes.stations_online ?? "—"],
        ["Внимание",        sumRes.stations_warning ?? "—"],
        ["Критичных",       sumRes.stations_critical ?? "—"],
        ["Открытых заявок", sumRes.open_requests ?? "—"],
        ["Аномалий (24ч)",  sumRes.recent_anomalies ?? "—"],
      ];
      sum.innerHTML = items.map(([k,v]) => `
        <div style="background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);border-radius:8px;padding:12px 16px">
          <div style="font-size:11px;color:rgba(255,255,255,0.45);margin-bottom:4px">${k}</div>
          <div style="font-size:22px;font-weight:700;color:#4a9eff">${v}</div>
        </div>`).join("");
    }
    if (feed && Array.isArray(feedRes)) {
      const sev = {info:"#4a9eff",warning:"#f59e0b",critical:"#ef4444"};
      feed.innerHTML = feedRes.map(e => `
        <div style="background:rgba(255,255,255,0.04);border-left:3px solid ${sev[e.severity]||"#888"};border-radius:4px;padding:10px 14px">
          <div style="display:flex;justify-content:space-between;margin-bottom:4px">
            <strong style="font-size:12px">${e.agent_name || "—"}</strong>
            <span style="font-size:10px;color:rgba(255,255,255,0.4)">${new Date(e.created_at).toLocaleString("ru")}</span>
          </div>
          <div style="font-size:12px;color:rgba(255,255,255,0.7)">${e.title}</div>
          ${e.body ? `<div style="font-size:11px;color:rgba(255,255,255,0.45);margin-top:4px">${e.body}</div>` : ""}
        </div>`).join("");
    }
  } catch(e) {
    console.warn("Monitoring summary failed:", e);
  }
}

function _applySmoothing() {
  const val = S.smooth ? "auto" : "pixelated";
  document.querySelectorAll("#map canvas, #map .ol-layer canvas").forEach(c => { c.style.imageRendering = val; });
  document.querySelectorAll(".cmp-img").forEach(img => { img.style.imageRendering = val; });
}

// ──────────────────────────────────────────────
// Panel
// ──────────────────────────────────────────────
function togglePanel() {
  const panel = document.getElementById("left-panel");
  const toggle = document.getElementById("panel-toggle");
  if (panel) {
    const isOpen = panel.classList.toggle("panel-open");
    if (toggle) toggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
  }
}
function closePanel() {
  const panel = document.getElementById("left-panel");
  const toggle = document.getElementById("panel-toggle");
  if (panel) panel.classList.remove("panel-open");
  if (toggle) toggle.setAttribute("aria-expanded", "false");
}
function toggleLpSection(id) {
  const section = document.getElementById(id);
  const isOpen = section.classList.toggle("open");
  const hdrBtn = section.querySelector(".lp-section-hdr");
  if (hdrBtn) {
    hdrBtn.setAttribute("aria-expanded", isOpen ? "true" : "false");
  }
}

function _onDocClick(e) {
  const panel  = document.getElementById("left-panel");
  const toggle = document.getElementById("panel-toggle");
  if (panel.classList.contains("panel-open") &&
      !panel.contains(e.target) && !toggle.contains(e.target)) {
    closePanel();
  }
}

// ──────────────────────────────────────────────
// Hover tooltip — shows coordinates only
// ──────────────────────────────────────────────
function onPointerMove(evt) {
  if (evt.dragging) return;
  const [lon, lat] = ol.proj.toLonLat(evt.coordinate);
  const tip = document.getElementById("hover-tooltip");
  if (!inBounds(lat, lon)) {
    tip.classList.add("hidden");
    return;
  }
  const px = evt.pixel;
  tip.style.left = px[0] + "px";
  tip.style.top  = px[1] + "px";
  tip.textContent = formatCoord(lat, lonNorm(lon < 0 ? lon + 360 : lon));
  tip.classList.remove("hidden");
}

// ──────────────────────────────────────────────
// Map click — popup with coords
// ──────────────────────────────────────────────
async function onMapClick(evt) {
  const [lon, lat] = ol.proj.toLonLat(evt.coordinate);
  if (!inBounds(lat, lon)) { _hidePopup(); return; }
  const lon360 = lon < 0 ? lon + 360 : lon;
  const coordStr = formatCoord(lat, lonNorm(lon360));
  const pinSvg = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#4a9eff" stroke-width="2" style="vertical-align:middle;margin-right:4px"><circle cx="12" cy="10" r="3"/><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z"/></svg>`;
  document.getElementById("map-popup-content").innerHTML =
    `<div class="popup-coord">${pinSvg}${coordStr}</div>`;
  document.getElementById("map-popup").style.display = "";
  S.popup.setPosition(evt.coordinate);
}

function _hidePopup() {
  document.getElementById("map-popup").style.display = "none";
  S.popup.setPosition(undefined);
}

// Format number with comma decimal separator
function fmtNum(v, dec = 2) {
  if (v === null || v === undefined || !isFinite(v)) return "—";
  return v.toFixed(dec).replace(".", ",");
}

// ──────────────────────────────────────────────
// Compatibility bridges for legacy modules
// ──────────────────────────────────────────────
function initStationsLayer() {
  // stations.js uses window.olMap — expose it
  if (S.map && !window.olMap) window.olMap = S.map;
  if (typeof window.initStationLayer === "function") window.initStationLayer();
}

function updateStationsVisibility(on) {
  // stations.js controls its own layer visibility
  if (typeof window._stationLayerSetVisible === "function") window._stationLayerSetVisible(on);
}

// loadDashboard, loadStationsPanel etc. — thin wrappers around monitoring.js
function loadDashboard(container) {
  if (typeof window.showMonitoringView === "function") {
    // Show full-screen monitoring overlay (original behavior)
    window.showMonitoringView();
  } else {
    container.innerHTML = "<div style='padding:8px;opacity:0.7'>Мониторинг загружается…</div>";
  }
}
function loadStationsPanel(container) { loadDashboard(container); }
function loadAgentsPanel(container)   { loadDashboard(container); }
function loadRequestsPanel(container) {
  if (typeof window.initRequestsUI === "function") window.initRequestsUI(container);
  else loadDashboard(container);
}
function loadForecastPanel(container) {
  if (typeof window.initForecastUI === "function") window.initForecastUI(container);
  else loadDashboard(container);
}
function loadCalendarPanel(container) {
  if (typeof window.initCalendarUI === "function") window.initCalendarUI(container);
  else loadDashboard(container);
}

// ──────────────────────────────────────────────
// Start
// ──────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  init();
});
