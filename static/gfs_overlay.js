/* GFS Forecast Overlay — Timeline slider + map tiles */
(function(){
  'use strict';

  const HOURS = [0, 6, 12, 24, 48, 72];
  const HOUR_LABELS = ['+0ч', '+6ч', '+12ч', '+24ч', '+48ч', '+72ч'];

  let gfsLayer = null;
  let currentHour = 0;
  let currentVariable = 'sst';
  let gfsActive = false;
  let sliderEl = null;
  let _cachedBounds = null;  // [lon_min, lat_min, lon_max, lat_max]

  async function getDynamicBounds() {
    if (_cachedBounds) return _cachedBounds;
    try {
      const resp = await fetch('/api/gfs/latest');
      if (resp.ok) {
        const info = await resp.json();
        if (info.bounds && info.bounds.length === 4) {
          _cachedBounds = info.bounds;
        }
      }
    } catch (_) {}
    if (!_cachedBounds) _cachedBounds = [125.0, 40.0, 180.0, 73.0];
    return _cachedBounds;
  }

  function getExtent() {
    const bounds = _cachedBounds || [125.0, 40.0, 180.0, 73.0];
    return ol.proj.transformExtent(bounds, 'EPSG:4326', 'EPSG:3857');
  }

  function buildTileUrl(variable, hour) {
    return `/api/gfs/tile/${variable}/${hour}?t=${Date.now()}`;
  }

  function createGfsLayer() {
    const extent = getExtent();
    gfsLayer = new ol.layer.Image({
      source: new ol.source.ImageStatic({
        url: buildTileUrl(currentVariable, currentHour),
        imageExtent: extent,
        projection: 'EPSG:3857',
      }),
      opacity: 0.7,
      zIndex: 5,
    });
    return gfsLayer;
  }

  function updateGfsLayer() {
    if (!gfsLayer || !window.olMap) return;
    const extent = getExtent();
    gfsLayer.setSource(new ol.source.ImageStatic({
      url: buildTileUrl(currentVariable, currentHour),
      imageExtent: extent,
      projection: 'EPSG:3857',
    }));
  }

  function createSlider() {
    if (document.getElementById('gfs-controls')) return;

    const container = document.createElement('div');
    container.id = 'gfs-controls';
    container.innerHTML = `
      <div class="gfs-panel">
        <div class="gfs-header">
          <div class="gfs-title">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M22 12h-4l-3 9L9 3l-3 9H2"/>
            </svg>
            GFS Прогноз
          </div>
          <div class="gfs-toggle-wrap">
            <button id="gfs-toggle" class="gfs-toggle-btn" onclick="window.toggleGfsOverlay()">
              Вкл
            </button>
          </div>
        </div>
        <div class="gfs-body" id="gfs-body">
          <div class="gfs-var-row">
            <button class="gfs-var-btn active" data-var="sst" onclick="window.setGfsVariable('sst')">ТПО</button>
            <button class="gfs-var-btn" data-var="wind" onclick="window.setGfsVariable('wind')">Ветер</button>
            <button class="gfs-var-btn" data-var="pressure" onclick="window.setGfsVariable('pressure')">Давление</button>
          </div>
          <div class="gfs-slider-row">
            <input type="range" id="gfs-slider" min="0" max="${HOURS.length-1}" value="0"
                   oninput="window.onGfsSlider(this.value)"/>
          </div>
          <div class="gfs-ticks">
            ${HOUR_LABELS.map((l,i) => `<span class="gfs-tick${i===0?' active':''}" data-idx="${i}">${l}</span>`).join('')}
          </div>
          <div class="gfs-info" id="gfs-info">Прогноз: сейчас (+0ч)</div>
          <div class="gfs-ai-badge">
            <span class="ai-dot"></span> AI Serendipity нейрокоррекция
          </div>
        </div>
      </div>
    `;

    const style = document.createElement('style');
    style.textContent = `
      #gfs-controls { position:absolute; bottom:20px; left:50%; transform:translateX(-50%);
        z-index:100; pointer-events:auto; }
      .gfs-panel { background:rgba(255,255,255,0.97); backdrop-filter:blur(12px);
        border-radius:16px; box-shadow:0 8px 32px rgba(0,0,0,0.15); padding:16px 20px;
        min-width:420px; font-family:'Inter',sans-serif; }
      .gfs-header { display:flex; align-items:center; justify-content:space-between; margin-bottom:12px; }
      .gfs-title { display:flex; align-items:center; gap:8px; font-weight:600; font-size:14px; color:#1a1a2e; }
      .gfs-toggle-btn { padding:4px 14px; border-radius:8px; border:1.5px solid #0066cc;
        background:transparent; color:#0066cc; font-size:12px; font-weight:600; cursor:pointer;
        transition:all .2s; }
      .gfs-toggle-btn.active { background:#0066cc; color:#fff; }
      .gfs-body { }
      .gfs-var-row { display:flex; gap:6px; margin-bottom:12px; }
      .gfs-var-btn { flex:1; padding:6px; border-radius:8px; border:1px solid #e0e0e0;
        background:#f8f9fa; color:#666; font-size:12px; font-weight:500; cursor:pointer;
        transition:all .2s; }
      .gfs-var-btn.active { background:#0066cc; color:#fff; border-color:#0066cc; }
      .gfs-slider-row { padding:0 4px; }
      #gfs-slider { width:100%; height:6px; -webkit-appearance:none; appearance:none;
        background:linear-gradient(90deg,#0066cc,#00c2ff,#ff6b35); border-radius:3px; outline:none; }
      #gfs-slider::-webkit-slider-thumb { -webkit-appearance:none; width:18px; height:18px;
        border-radius:50%; background:#fff; border:3px solid #0066cc; cursor:pointer;
        box-shadow:0 2px 6px rgba(0,0,0,0.2); }
      .gfs-ticks { display:flex; justify-content:space-between; padding:4px 2px 0;
        font-size:11px; color:#999; }
      .gfs-tick { cursor:pointer; transition:color .2s; }
      .gfs-tick.active { color:#0066cc; font-weight:600; }
      .gfs-info { text-align:center; font-size:12px; color:#666; margin-top:8px; }
      .gfs-ai-badge { display:flex; align-items:center; gap:6px; justify-content:center;
        margin-top:8px; font-size:11px; color:#8b5cf6; }
      .ai-dot { width:8px; height:8px; border-radius:50%;
        background:linear-gradient(135deg,#8b5cf6,#06b6d4); animation:pulse-ai 2s infinite; }
      @keyframes pulse-ai { 0%,100%{opacity:1} 50%{opacity:0.4} }
    `;
    document.head.appendChild(style);

    const sstView = document.getElementById('sst-view');
    if (sstView) sstView.appendChild(container);
    sliderEl = document.getElementById('gfs-slider');
  }

  window.toggleGfsOverlay = function() {
    gfsActive = !gfsActive;
    const btn = document.getElementById('gfs-toggle');
    const body = document.getElementById('gfs-body');
    if (gfsActive) {
      btn.classList.add('active');
      btn.textContent = 'Выкл';
      body.style.display = '';
      if (!gfsLayer && window.olMap) {
        createGfsLayer();
        window.olMap.addLayer(gfsLayer);
      }
      if (gfsLayer) gfsLayer.setVisible(true);
    } else {
      btn.classList.remove('active');
      btn.textContent = 'Вкл';
      body.style.display = 'none';
      if (gfsLayer) gfsLayer.setVisible(false);
    }
  };

  window.setGfsVariable = function(v) {
    currentVariable = v;
    document.querySelectorAll('.gfs-var-btn').forEach(b => {
      b.classList.toggle('active', b.dataset.var === v);
    });
    updateGfsLayer();
  };

  window.onGfsSlider = function(idx) {
    idx = parseInt(idx);
    currentHour = HOURS[idx];
    document.querySelectorAll('.gfs-tick').forEach((t,i) => {
      t.classList.toggle('active', i === idx);
    });
    const info = document.getElementById('gfs-info');
    if (info) {
      const labels = {0:'сейчас', 6:'6 часов', 12:'12 часов', 24:'1 сутки', 48:'2 суток', 72:'3 суток'};
      info.textContent = `Прогноз: ${labels[currentHour] || currentHour+'ч'} (+${currentHour}ч)`;
    }
    updateGfsLayer();
  };

  window.initGfsOverlay = async function() {
    // Pre-load dynamic bounds from /api/meta
    await getDynamicBounds();
    createSlider();
    // Pre-warm GFS cache
    fetch('/api/gfs/latest').catch(()=>{});
  };

  // Auto-init when SST view loads
  const origSwitch = window.switchView;
  if (typeof origSwitch === 'function') {
    // Will be called from index.html switchView
  }

  // GFS overlay disabled by default — init only when explicitly called
  // document.addEventListener('DOMContentLoaded', () => {
  //   setTimeout(() => { if (window.olMap) window.initGfsOverlay(); }, 1500);
  // });
})();
