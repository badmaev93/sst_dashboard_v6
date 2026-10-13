/* SST Dashboard v5 — stations.js: Station markers on OpenLayers map + detail panel */
"use strict";

(function() {
    const STATUS_COLORS = {
        normal:   '#22c55e',
        warning:  '#f59e0b',
        critical: '#ef4444',
        offline:  '#6b7280'
    };

    let _stationLayer = null;
    let _popup = null;
    let _stations = [];

    // ── Init Station Layer ──────────────────────
    window.initStationLayer = async function() {
        if (!window.olMap) {
            setTimeout(initStationLayer, 500);
            return;
        }
        await loadStations();
        createLayer();
        createPopup();
        bindClick();
    };

    // ── Load Stations from API ──────────────────
    async function loadStations() {
        try {
            const resp = await fetch('/api/monitoring/stations');
            if (resp.ok) {
                _stations = await resp.json();
            }
        } catch (e) {
            console.warn('stations.js: failed to load stations', e);
        }
    }

    // ── Create Vector Layer ─────────────────────
    function createLayer() {
        if (!window.ol || !_stations.length) return;

        const features = _stations.map(function(st) {
            const coords = ol.proj.fromLonLat([st.lon, st.lat]);
            const f = new ol.Feature({
                geometry: new ol.geom.Point(coords),
                station: st
            });
            f.setStyle(stationStyle(st));
            return f;
        });

        const source = new ol.source.Vector({ features: features });
        _stationLayer = new ol.layer.Vector({
            source: source,
            zIndex: 100
        });
        window.olMap.addLayer(_stationLayer);
    }

    // ── Station Marker Style ────────────────────
    function stationStyle(st) {
        const color = STATUS_COLORS[st.status] || STATUS_COLORS.normal;
        return new ol.style.Style({
            image: new ol.style.Circle({
                radius: 7,
                fill: new ol.style.Fill({ color: color }),
                stroke: new ol.style.Stroke({ color: '#fff', width: 2 })
            }),
            text: new ol.style.Text({
                text: st.code || '',
                offsetY: -16,
                font: '11px Inter, system-ui, sans-serif',
                fill: new ol.style.Fill({ color: '#1a2030' }),
                stroke: new ol.style.Stroke({ color: '#fff', width: 3 }),
                textAlign: 'center'
            })
        });
    }

    // ── Popup Overlay ───────────────────────────
    function createPopup() {
        let el = document.getElementById('station-popup');
        if (!el) {
            el = document.createElement('div');
            el.id = 'station-popup';
            Object.assign(el.style, {
                position: 'absolute',
                background: '#fff',
                borderRadius: '12px',
                padding: '16px',
                boxShadow: '0 8px 32px rgba(0,0,0,0.18)',
                minWidth: '220px',
                maxWidth: '300px',
                fontSize: '13px',
                fontFamily: 'Inter, system-ui, sans-serif',
                display: 'none',
                zIndex: '200',
                pointerEvents: 'auto'
            });
            document.body.appendChild(el);
        }
        _popup = el;
    }

    // ── Map Click Handler ───────────────────────
    function bindClick() {
        if (!window.olMap) return;

        window.olMap.on('singleclick', function(evt) {
            let found = false;
            window.olMap.forEachFeatureAtPixel(evt.pixel, function(feature) {
                if (found) return;
                const st = feature.get('station');
                if (!st) return;
                found = true;
                showPopup(st, evt.pixel);
            });
            if (!found) hidePopup();
        });

        window.olMap.on('pointermove', function(evt) {
            const hit = window.olMap.hasFeatureAtPixel(evt.pixel, {
                layerFilter: function(l) { return l === _stationLayer; }
            });
            window.olMap.getTargetElement().style.cursor = hit ? 'pointer' : '';
        });
    }

    // ── Show Popup ──────────────────────────────
    function showPopup(st, pixel) {
        if (!_popup) return;
        const statusColor = STATUS_COLORS[st.status] || '#6b7280';
        const statusLabel = {normal:'Норма',warning:'Внимание',critical:'Критично',offline:'Не в сети'}[st.status] || st.status;

        const latest = st.latest_reading || st.latest || st;
        const _f = (v, d) => v != null ? Number(v).toFixed(d).replace('.', ',') : '—';
        const sst = (latest.sst != null ? _f(latest.sst, 1) + '°C' : (st.sst != null ? _f(st.sst, 1) + '°C' : '—'));
        const air = (latest.temp_air != null ? _f(latest.temp_air, 1) + '°C' : (st.temp_air != null ? _f(st.temp_air, 1) + '°C' : '—'));
        const wind = (latest.wind_speed != null ? _f(latest.wind_speed, 1) + ' м/с' : (st.wind_speed != null ? _f(st.wind_speed, 1) + ' м/с' : '—'));
        const wave = (latest.wave_height != null ? _f(latest.wave_height, 1) + ' м' : (st.wave_height != null ? _f(st.wave_height, 1) + ' м' : '—'));
        const pres = (latest.pressure != null ? _f(latest.pressure, 0) + ' гПа' : (st.pressure != null ? _f(st.pressure, 0) + ' гПа' : '—'));
        const hum = (latest.humidity != null ? _f(latest.humidity, 0) + '%' : (st.humidity != null ? _f(st.humidity, 0) + '%' : '—'));
        const vis = (latest.visibility != null ? _f(latest.visibility, 1) + ' км' : (st.visibility != null ? _f(st.visibility, 1) + ' км' : '—'));
        const obsAt = latest.observed_at || latest.last_reading_at || st.last_reading_at;
        const obsTime = obsAt ? new Date(obsAt).toLocaleTimeString('ru-RU', {hour:'2-digit',minute:'2-digit'}) : '';

        _popup.innerHTML = `
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">
                <div style="font-size:15px;font-weight:700;color:#1a2030">${esc(st.name)}</div>
                <span style="display:inline-flex;align-items:center;gap:4px;padding:2px 8px;border-radius:10px;
                      background:${statusColor}18;color:${statusColor};font-size:11px;font-weight:600">
                  <span style="width:6px;height:6px;border-radius:50%;background:${statusColor}"></span>${statusLabel}
                </span>
            </div>
            <div style="font-size:11px;color:#94a3b8;margin-bottom:10px">${esc(st.code)} &bull; ${esc(st.region || '')}${obsTime ? ' &bull; ' + obsTime : ''}</div>
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;margin-bottom:10px">
                <div style="text-align:center;padding:8px 4px;background:#f0f7ff;border-radius:8px">
                    <div style="font-size:15px;font-weight:700;color:#2563eb">${sst}</div>
                    <div style="font-size:9px;color:#94a3b8;margin-top:1px">ТПО</div>
                </div>
                <div style="text-align:center;padding:8px 4px;background:#f0fdf4;border-radius:8px">
                    <div style="font-size:15px;font-weight:700;color:#059669">${air}</div>
                    <div style="font-size:9px;color:#94a3b8;margin-top:1px">Воздух</div>
                </div>
                <div style="text-align:center;padding:8px 4px;background:#fffbeb;border-radius:8px">
                    <div style="font-size:15px;font-weight:700;color:#d97706">${wind}</div>
                    <div style="font-size:9px;color:#94a3b8;margin-top:1px">Ветер</div>
                </div>
                <div style="text-align:center;padding:8px 4px;background:#fdf4ff;border-radius:8px">
                    <div style="font-size:14px;font-weight:700;color:#7c3aed">${wave}</div>
                    <div style="font-size:9px;color:#94a3b8;margin-top:1px">Волны</div>
                </div>
                <div style="text-align:center;padding:8px 4px;background:#f0f9ff;border-radius:8px">
                    <div style="font-size:14px;font-weight:700;color:#0891b2">${pres}</div>
                    <div style="font-size:9px;color:#94a3b8;margin-top:1px">Давление</div>
                </div>
                <div style="text-align:center;padding:8px 4px;background:#f9fafb;border-radius:8px">
                    <div style="font-size:14px;font-weight:700;color:#374151">${hum}</div>
                    <div style="font-size:9px;color:#94a3b8;margin-top:1px">Влажность</div>
                </div>
            </div>
            <div style="display:flex;gap:6px">
                <button onclick="showStationDetail(${st.id})" style="flex:1;padding:7px;background:#2563eb;
                        color:#fff;border:none;border-radius:8px;font-size:11px;font-weight:600;cursor:pointer;
                        font-family:inherit">Подробнее</button>
                <button onclick="showForecastPanel(${st.id})" style="flex:1;padding:7px;
                        background:linear-gradient(135deg,#8b5cf6,#06b6d4);color:#fff;border:none;
                        border-radius:8px;font-size:11px;font-weight:600;cursor:pointer;font-family:inherit">
                    AI Прогноз</button>
            </div>
        `;

        const mapEl = window.olMap.getTargetElement();
        const rect = mapEl.getBoundingClientRect();
        _popup.style.display = 'block';
        _popup.style.left = (rect.left + pixel[0] + 12) + 'px';
        _popup.style.top = (rect.top + pixel[1] - 20) + 'px';

        // Adjust if goes off screen
        const pr = _popup.getBoundingClientRect();
        if (pr.right > window.innerWidth - 10) {
            _popup.style.left = (rect.left + pixel[0] - pr.width - 12) + 'px';
        }
        if (pr.bottom > window.innerHeight - 10) {
            _popup.style.top = (window.innerHeight - pr.height - 10) + 'px';
        }
    }

    function hidePopup() {
        if (_popup) _popup.style.display = 'none';
    }

    // ── Station Detail Panel ────────────────────
    window.showStationDetail = async function(stationId) {
        hidePopup();
        let panel = document.getElementById('station-detail');
        if (panel) panel.remove();

        panel = document.createElement('div');
        panel.id = 'station-detail';
        panel.setAttribute('role', 'dialog');
        panel.setAttribute('aria-label', 'Детальная информация о станции');
        panel.setAttribute('tabindex', '-1');
        Object.assign(panel.style, {
            position: 'fixed', top: '0', right: '0',
            width: '420px', maxWidth: '96vw', height: '100vh',
            background: '#fff', boxShadow: '-4px 0 24px rgba(0,0,0,0.12)',
            zIndex: '9600', overflowY: 'auto', fontFamily: 'Inter, system-ui, sans-serif',
            padding: '24px', animation: 'panel-slide-in .3s ease both'
        });

        panel.innerHTML = '<div style="color:#94a3b8;padding:40px;text-align:center">Загрузка...</div>';
        document.body.appendChild(panel);
        panel.focus();

        try {
            const [stResp, rdResp] = await Promise.all([
                fetch('/api/monitoring/stations/' + stationId),
                fetch('/api/monitoring/stations/' + stationId + '/readings?limit=24')
            ]);

            const stData = stResp.ok ? await stResp.json() : null;
            const readingsData = rdResp.ok ? await rdResp.json() : [];

            // API returns {station: {...}, readings: [...]} OR flat station object
            const station = stData && stData.station ? stData.station : stData;
            // Prefer separate readings endpoint; fall back to embedded readings
            const readings = Array.isArray(readingsData) ? readingsData
                : (stData && Array.isArray(stData.readings) ? stData.readings : []);

            if (!station || !station.id) {
                panel.innerHTML = '<div style="color:#dc2626;padding:40px;text-align:center">Станция не найдена</div>';
                return;
            }

            // If no readings yet, add latest values from station object (from list endpoint)
            const effectiveReadings = readings.length ? readings : (
                station.sst != null ? [{
                    observed_at: station.last_reading_at || new Date().toISOString(),
                    sst: station.sst, temp_air: station.temp_air,
                    wind_speed: station.wind_speed, wave_height: station.wave_height,
                    pressure: station.pressure, visibility: station.visibility,
                    humidity: station.humidity, status: station.reading_status || station.status
                }] : []
            );

            renderDetail(panel, station, effectiveReadings);
        } catch (e) {
            panel.innerHTML = '<div style="color:#dc2626;padding:40px;text-align:center">Ошибка загрузки</div>';
        }
    };

    function renderDetail(panel, st, readings) {
        const statusColor = STATUS_COLORS[st.status] || '#6b7280';
        const statusLabel = {normal:'Норма',warning:'Внимание',critical:'Критично',offline:'Не в сети'}[st.status] || st.status;

        let html = `
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px">
                <div>
                    <div style="font-size:18px;font-weight:700;color:#1a2030">${esc(st.name)}</div>
                    <div style="font-size:12px;color:#94a3b8;margin-top:2px">${esc(st.code)} &bull; ${esc(st.region || '')}</div>
                </div>
                <div style="display:flex;align-items:center;gap:8px">
                    <span style="display:inline-flex;align-items:center;gap:4px;padding:4px 12px;
                          border-radius:20px;background:${statusColor}18;color:${statusColor};
                          font-size:12px;font-weight:600">
                        <span style="width:8px;height:8px;border-radius:50%;background:${statusColor}"></span>
                        ${statusLabel}
                    </span>
                    <button onclick="document.getElementById('station-detail').remove()"
                            style="width:32px;height:32px;border:none;background:#f3f4f6;border-radius:8px;
                            font-size:18px;color:#6b7280;cursor:pointer;display:flex;align-items:center;
                            justify-content:center">&times;</button>
                </div>
            </div>

            <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:8px;margin-bottom:20px">
                <div style="padding:12px;border-radius:10px;background:#f8fafc;text-align:center">
                    <div style="font-size:11px;color:#94a3b8;margin-bottom:2px">Широта</div>
                    <div style="font-size:14px;font-weight:600;color:#1a2030">${st.lat.toFixed(4).replace('.', ',')}°</div>
                </div>
                <div style="padding:12px;border-radius:10px;background:#f8fafc;text-align:center">
                    <div style="font-size:11px;color:#94a3b8;margin-bottom:2px">Долгота</div>
                    <div style="font-size:14px;font-weight:600;color:#1a2030">${st.lon.toFixed(4).replace('.', ',')}°</div>
                </div>
            </div>
        `;

        // Latest reading summary cards
        if (readings.length) {
            const lr = readings[0];
            html += '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:16px">';
            var cards = [
                {label:'ТПО', val:fmtVal(lr.sst,'°C'), color:'#2563eb', bg:'#eff6ff'},
                {label:'Воздух', val:fmtVal(lr.temp_air,'°C'), color:'#059669', bg:'#f0fdf4'},
                {label:'Ветер', val:fmtVal(lr.wind_speed,' м/с'), color:'#d97706', bg:'#fffbeb'},
                {label:'Волны', val:fmtVal(lr.wave_height,' м'), color:'#7c3aed', bg:'#faf5ff'},
                {label:'Давление', val:fmtVal(lr.pressure,' гПа'), color:'#0891b2', bg:'#f0f9ff'},
                {label:'Влажность', val:fmtVal(lr.humidity,'%'), color:'#374151', bg:'#f9fafb'},
            ];
            cards.forEach(function(c) {
                html += '<div style="padding:10px;border-radius:10px;background:'+c.bg+';text-align:center">';
                html += '<div style="font-size:16px;font-weight:700;color:'+c.color+'">'+c.val+'</div>';
                html += '<div style="font-size:10px;color:#94a3b8;margin-top:2px">'+c.label+'</div>';
                html += '</div>';
            });
            html += '</div>';
        }

        // Latest readings table
        if (readings.length) {
            html += '<div style="font-size:13px;font-weight:700;color:#1a2030;margin-bottom:8px">История показаний (24ч)</div>';
            html += '<div style="overflow-x:auto;margin-bottom:16px"><table style="width:100%;border-collapse:collapse;font-size:11px">';
            html += '<thead><tr style="border-bottom:2px solid #e2e8f0">';
            html += '<th style="padding:5px 6px;text-align:left;color:#94a3b8;font-size:9px;text-transform:uppercase">Время</th>';
            html += '<th style="padding:5px 6px;text-align:right;color:#94a3b8;font-size:9px">ТПО</th>';
            html += '<th style="padding:5px 6px;text-align:right;color:#94a3b8;font-size:9px">Возд.</th>';
            html += '<th style="padding:5px 6px;text-align:right;color:#94a3b8;font-size:9px">Ветер</th>';
            html += '<th style="padding:5px 6px;text-align:right;color:#94a3b8;font-size:9px">Волны</th>';
            html += '<th style="padding:5px 6px;text-align:right;color:#94a3b8;font-size:9px">Давл.</th>';
            html += '</tr></thead><tbody>';

            readings.slice(0, 12).forEach(function(r) {
                const t = r.observed_at ? new Date(r.observed_at).toLocaleTimeString('ru-RU', {hour:'2-digit',minute:'2-digit'}) : '—';
                html += '<tr style="border-bottom:1px solid #f1f5f9">';
                html += '<td style="padding:5px 6px;color:#64748b">' + t + '</td>';
                html += '<td style="padding:5px 6px;text-align:right;color:#2563eb;font-weight:600">' + fmtVal(r.sst, '°C') + '</td>';
                html += '<td style="padding:5px 6px;text-align:right;color:#475569">' + fmtVal(r.temp_air, '°C') + '</td>';
                html += '<td style="padding:5px 6px;text-align:right;color:#475569">' + fmtVal(r.wind_speed, ' м/с') + '</td>';
                html += '<td style="padding:5px 6px;text-align:right;color:#475569">' + fmtVal(r.wave_height, ' м') + '</td>';
                html += '<td style="padding:5px 6px;text-align:right;color:#475569">' + fmtVal(r.pressure, '') + '</td>';
                html += '</tr>';
            });
            html += '</tbody></table></div>';
        }

        // Chart tabs
        html += '<div style="display:flex;gap:6px;margin-bottom:8px" id="sd-chart-tabs">';
        ['sst','temp_air','wind_speed','wave_height'].forEach(function(k,i) {
            var labels = ['ТПО','Воздух','Ветер','Волны'];
            html += '<button data-key="'+k+'" onclick="window._sdSwitchChart(\''+k+'\')" style="'+
                'padding:4px 10px;border-radius:6px;border:1px solid '+(i===0?'#2563eb':'#e2e8f0')+';'+
                'background:'+(i===0?'#2563eb':'transparent')+';color:'+(i===0?'#fff':'#64748b')+';'+
                'font-size:11px;font-weight:600;cursor:pointer;font-family:inherit" class="sd-tab-btn">'+labels[i]+'</button>';
        });
        html += '</div>';
        html += '<canvas id="station-sst-chart" width="380" height="180"></canvas>';

        // Action buttons
        html += `
            <div style="display:flex;gap:8px;margin-top:20px">
                <button onclick="showForecastPanel(${st.id})" style="flex:1;padding:10px;
                        background:linear-gradient(135deg,#8b5cf6,#06b6d4);color:#fff;border:none;
                        border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;font-family:inherit">
                    AI Serendipity Прогноз
                </button>
            </div>
        `;

        panel.innerHTML = html;

        // Draw chart
        var _sdChart = null;
        var _sdReadings = readings;
        var CHART_KEYS = {
            sst:        { label:'ТПО (°C)',     color:'#2563eb', suffix:'°C' },
            temp_air:   { label:'Воздух (°C)',  color:'#059669', suffix:'°C' },
            wind_speed: { label:'Ветер (м/с)',  color:'#d97706', suffix:' м/с' },
            wave_height:{ label:'Волны (м)',    color:'#7c3aed', suffix:' м' },
        };

        window._sdSwitchChart = function(key) {
            document.querySelectorAll('.sd-tab-btn').forEach(function(b) {
                var active = b.dataset.key === key;
                b.style.background = active ? '#2563eb' : 'transparent';
                b.style.color = active ? '#fff' : '#64748b';
                b.style.borderColor = active ? '#2563eb' : '#e2e8f0';
            });
            if (_sdChart) { _sdChart.destroy(); _sdChart = null; }
            var cfg = CHART_KEYS[key] || CHART_KEYS.sst;
            var rev = _sdReadings.slice().reverse();
            var lbls = rev.map(function(r) { return r.observed_at ? new Date(r.observed_at).toLocaleTimeString('ru-RU',{hour:'2-digit',minute:'2-digit'}) : ''; });
            var vals = rev.map(function(r) { return r[key]; });
            var ctx2 = document.getElementById('station-sst-chart');
            if (!ctx2 || !window.Chart) return;
            _sdChart = new Chart(ctx2.getContext('2d'), {
                type: 'line',
                data: {
                    labels: lbls,
                    datasets: [{
                        label: cfg.label,
                        data: vals,
                        borderColor: cfg.color,
                        borderWidth: 2,
                        pointRadius: 2,
                        pointBackgroundColor: cfg.color,
                        backgroundColor: cfg.color + '15',
                        fill: true,
                        tension: 0.3
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            backgroundColor: 'rgba(17,24,39,0.92)',
                            cornerRadius: 8,
                            callbacks: { label: function(c) { return ' ' + cfg.label + ': ' + (c.parsed.y != null ? c.parsed.y.toFixed(1).replace('.', ',') : '—') + cfg.suffix; } }
                        }
                    },
                    scales: {
                        x: { display: true, ticks: { maxTicksLimit: 8, font: { size: 10 }, color: '#94a3b8' }, grid: { display: false } },
                        y: { grid: { color: 'rgba(0,0,0,0.05)' }, ticks: { font: { size: 10 }, color: '#94a3b8' } }
                    }
                }
            });
        };

        if (readings.length && window.Chart) {
            window._sdSwitchChart('sst');
        }
    }

    // ── Helpers ──────────────────────────────────
    function fmtVal(v, suffix) {
        if (v == null) return '—';
        return (typeof v === 'number' ? v.toFixed(1).replace('.', ',') : v) + (suffix || '');
    }

    function esc(s) {
        if (!s) return '';
        var d = document.createElement('div');
        d.textContent = s;
        return d.innerHTML;
    }
})();
