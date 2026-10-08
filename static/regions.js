/* SST Dashboard v6 — regions.js: Regional overview layer on OpenLayers map */
"use strict";

(function() {
    const STATUS_COLORS = {
        normal:   '#22c55e',
        warning:  '#f59e0b',
        critical: '#ef4444',
        offline:  '#6b7280'
    };
    const STATUS_LABELS = {
        normal: 'Норма', warning: 'Внимание', critical: 'Критично', offline: 'Не в сети'
    };

    let _regionLayer = null;
    let _highlightLayer = null;
    let _allRegionsExtent = null;
    let _regionCard = null;
    let _hoveredFeature = null;

    // ── Init Region Layer ──────────────────────
    window.initRegionLayer = async function() {
        if (!window.olMap) {
            setTimeout(window.initRegionLayer, 500);
            return;
        }
        if (_regionLayer) return;
        await createRegionLayer();
        createHighlightLayer();
        bindHover();
        bindClick();
        createRegionCard();
    };

    // ── Show regions overview ──────────────────
    window.showRegionsView = function() {
        if (_regionLayer) _regionLayer.setVisible(true);
        if (_allRegionsExtent) {
            window.olMap.getView().fit(_allRegionsExtent, {
                padding: [60, 60, 60, 60],
                duration: 500
            });
        }
    };

    // ── Create vector layer from GeoJSON ───────
    async function createRegionLayer() {
        let geojson;
        try {
            const resp = await fetch('/api/regions/geojson');
            if (!resp.ok) return;
            geojson = await resp.json();
        } catch (e) {
            console.warn('regions.js: failed to load geojson', e);
            return;
        }

        const format = new ol.format.GeoJSON();
        const features = format.readFeatures(geojson, {
            featureProjection: 'EPSG:3857'
        });

        features.forEach(function(f) {
            const props = f.getProperties();
            const color = props.color || '#666';
            f.setStyle(regionStyle(color, props.name, false));
        });

        const source = new ol.source.Vector({ features: features });
        _regionLayer = new ol.layer.Vector({
            source: source,
            zIndex: 50,
            visible: false  // Полигоны регионов скрыты по умолчанию
        });
        window.olMap.addLayer(_regionLayer);

        _allRegionsExtent = source.getExtent();
    }

    // ── Highlight layer for hover ──────────────
    function createHighlightLayer() {
        _highlightLayer = new ol.layer.Vector({
            source: new ol.source.Vector(),
            zIndex: 51
        });
        window.olMap.addLayer(_highlightLayer);
    }

    // ── Region polygon style ───────────────────
    function regionStyle(color, label, highlighted) {
        var fillAlpha = highlighted ? 0.35 : 0.18;
        var r = parseInt(color.slice(1, 3), 16);
        var g = parseInt(color.slice(3, 5), 16);
        var b = parseInt(color.slice(5, 7), 16);

        return new ol.style.Style({
            fill: new ol.style.Fill({
                color: 'rgba(' + r + ',' + g + ',' + b + ',' + fillAlpha + ')'
            }),
            stroke: new ol.style.Stroke({
                color: color,
                width: highlighted ? 3 : 2
            }),
            text: new ol.style.Text({
                text: label || '',
                font: (highlighted ? 'bold 13px' : '12px') + ' Inter, system-ui, sans-serif',
                fill: new ol.style.Fill({ color: '#1a2030' }),
                stroke: new ol.style.Stroke({ color: 'rgba(255,255,255,0.9)', width: 4 }),
                overflow: true,
                textAlign: 'center',
                textBaseline: 'middle'
            })
        });
    }

    // ── Hover interaction ──────────────────────
    function bindHover() {
        window.olMap.on('pointermove', function(evt) {
            if (evt.dragging) return;

            var found = null;
            window.olMap.forEachFeatureAtPixel(evt.pixel, function(feature, layer) {
                if (layer === _regionLayer) {
                    found = feature;
                }
            });

            if (found === _hoveredFeature) return;

            // Reset previous
            if (_hoveredFeature) {
                var p = _hoveredFeature.getProperties();
                _hoveredFeature.setStyle(regionStyle(p.color || '#666', p.name, false));
            }

            _hoveredFeature = found;

            if (found) {
                var props = found.getProperties();
                found.setStyle(regionStyle(props.color || '#666', props.name, true));
                window.olMap.getTargetElement().style.cursor = 'pointer';
            } else {
                window.olMap.getTargetElement().style.cursor = '';
            }
        });
    }

    // ── Click interaction ──────────────────────
    function bindClick() {
        window.olMap.on('singleclick', function(evt) {
            var found = null;
            window.olMap.forEachFeatureAtPixel(evt.pixel, function(feature, layer) {
                if (layer === _regionLayer && !found) {
                    found = feature;
                }
            });

            if (found) {
                var geom = found.getGeometry();
                var extent = geom.getExtent();
                window.olMap.getView().fit(extent, {
                    padding: [50, 50, 50, 50],
                    duration: 500
                });

                var props = found.getProperties();
                showRegionCard(props.code, props.name, props.color);
            }
        });
    }

    // ── Region info card ───────────────────────
    function createRegionCard() {
        if (_regionCard) return;
        var card = document.createElement('div');
        card.id = 'region-card';
        card.setAttribute('role', 'dialog');
        card.setAttribute('aria-label', 'Детальная информация о регионе');
        card.setAttribute('tabindex', '-1');
        card.style.cssText = [
            'display:none',
            'position:fixed',
            'top:56px',
            'right:16px',
            'width:340px',
            'max-height:calc(100vh - 80px)',
            'overflow-y:auto',
            'background:#fff',
            'border-radius:14px',
            'box-shadow:0 8px 40px rgba(0,0,0,0.16)',
            'z-index:600',
            'font-family:Inter, system-ui, sans-serif',
            'padding:0'
        ].join(';');
        document.body.appendChild(card);
        _regionCard = card;
    }

    async function showRegionCard(code, name, color) {
        if (!_regionCard) return;
        _regionCard.style.display = 'block';
        _regionCard.focus();
        _regionCard.innerHTML = '<div style="padding:24px;text-align:center;color:#94a3b8">Загрузка...</div>';

        try {
            var resp = await fetch('/api/regions/' + encodeURIComponent(code));
            if (!resp.ok) throw new Error('API error');
            var data = await resp.json();
            renderRegionCard(data, color);
        } catch (e) {
            _regionCard.innerHTML = '<div style="padding:24px;text-align:center;color:#ef4444">Ошибка загрузки</div>';
        }
    }

    function renderRegionCard(data, color) {
        var sstDisplay = data.avg_sst != null ? data.avg_sst.toFixed(1).replace('.', ',') + '\u00B0C' : '\u2014';
        var alertBg = data.active_alerts > 0 ? '#fef2f2' : '#f0fdf4';
        var alertColor = data.active_alerts > 0 ? '#ef4444' : '#22c55e';

        var html = '';
        // Header
        html += '<div style="padding:20px 20px 0 20px">';
        html += '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px">';
        html += '<div style="display:flex;align-items:center;gap:10px">';
        html += '<div style="width:14px;height:14px;border-radius:4px;background:' + esc(color) + '"></div>';
        html += '<div style="font-size:17px;font-weight:700;color:#1a2030">' + esc(data.name) + '</div>';
        html += '</div>';
        html += '<button onclick="closeRegionCard()" aria-label="Закрыть" style="width:30px;height:30px;border:none;background:#f3f4f6;border-radius:8px;font-size:16px;color:#6b7280;cursor:pointer;display:flex;align-items:center;justify-content:center">&times;</button>';
        html += '</div>';

        // Stats row
        html += '<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-bottom:18px">';
        html += '<div style="text-align:center;padding:12px 8px;background:#f8fafc;border-radius:10px">';
        html += '<div style="font-size:22px;font-weight:700;color:#2563eb">' + sstDisplay + '</div>';
        html += '<div style="font-size:10px;color:#94a3b8;margin-top:2px">\u0421\u0440. \u0422\u041F\u041E</div></div>';
        html += '<div style="text-align:center;padding:12px 8px;background:#f8fafc;border-radius:10px">';
        html += '<div style="font-size:22px;font-weight:700;color:#1a2030">' + data.station_count + '</div>';
        html += '<div style="font-size:10px;color:#94a3b8;margin-top:2px">\u0421\u0442\u0430\u043D\u0446\u0438\u0439</div></div>';
        html += '<div style="text-align:center;padding:12px 8px;background:' + alertBg + ';border-radius:10px">';
        html += '<div style="font-size:22px;font-weight:700;color:' + alertColor + '">' + data.active_alerts + '</div>';
        html += '<div style="font-size:10px;color:#94a3b8;margin-top:2px">\u0422\u0440\u0435\u0432\u043E\u0433</div></div>';
        html += '</div></div>';

        // Stations list
        if (data.stations && data.stations.length) {
            html += '<div style="padding:0 20px 20px 20px">';
            html += '<div style="font-size:12px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:10px">\u0421\u0442\u0430\u043D\u0446\u0438\u0438</div>';

            data.stations.forEach(function(st) {
                var statusColor = STATUS_COLORS[st.status] || '#6b7280';
                var statusLabel = STATUS_LABELS[st.status] || st.status || '\u2014';
                var sst = st.sst != null ? st.sst.toFixed(1).replace('.', ',') + '\u00B0C' : '\u2014';
                var wind = st.wind_speed != null ? st.wind_speed.toFixed(1).replace('.', ',') + ' \u043C/\u0441' : '\u2014';
                var time = st.observed_at ? new Date(st.observed_at).toLocaleTimeString('ru-RU', {hour:'2-digit',minute:'2-digit'}) : '\u2014';

                html += '<div style="display:flex;align-items:center;gap:10px;padding:10px 12px;margin-bottom:6px;background:#f8fafc;border-radius:10px;cursor:pointer" ';
                html += 'role="button" tabindex="0" aria-label="Станция ' + esc(st.name) + '" ';
                html += 'onclick="if(window.showStationDetail)window.showStationDetail(' + st.id + ')" ';
                html += 'onkeydown="if(event.key===\'Enter\'||event.key===\' \'){event.preventDefault();if(window.showStationDetail)window.showStationDetail(' + st.id + ');}">';

                // Status dot
                html += '<span style="width:10px;height:10px;border-radius:50%;background:' + statusColor + ';flex-shrink:0" title="' + esc(statusLabel) + '"></span>';

                // Name and code
                html += '<div style="flex:1;min-width:0">';
                html += '<div style="font-size:13px;font-weight:600;color:#1a2030;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">' + esc(st.name) + '</div>';
                html += '<div style="font-size:10px;color:#94a3b8">' + esc(st.code) + '</div>';
                html += '</div>';

                // SST
                html += '<div style="text-align:right;flex-shrink:0">';
                html += '<div style="font-size:13px;font-weight:700;color:#2563eb">' + sst + '</div>';
                html += '<div style="font-size:10px;color:#94a3b8">' + time + '</div>';
                html += '</div>';

                html += '</div>';
            });

            html += '</div>';
        }

        // Back button
        html += '<div style="padding:0 20px 20px 20px">';
        html += '<button onclick="closeRegionCard();if(window.showRegionsView)window.showRegionsView()" ';
        html += 'style="width:100%;padding:10px;background:#f3f4f6;border:1px solid #e5e7eb;border-radius:10px;';
        html += 'font-family:inherit;font-size:13px;font-weight:600;color:#475569;cursor:pointer;transition:all 0.15s"';
        html += ' onmouseover="this.style.background=\'#e5e7eb\'" onmouseout="this.style.background=\'#f3f4f6\'">';
        html += '\u2190 \u041A \u043E\u0431\u0437\u043E\u0440\u0443 \u0440\u0435\u0433\u0438\u043E\u043D\u043E\u0432</button>';
        html += '</div>';

        _regionCard.innerHTML = html;
    }

    window.createRegionCard = createRegionCard;
    window.showRegionCard = showRegionCard;
    window.renderRegionCard = renderRegionCard;

    window.closeRegionCard = function() {
        if (_regionCard) _regionCard.style.display = 'none';
    };

    // ── Helpers ─────────────────────────────────
    function esc(s) {
        if (!s) return '';
        var d = document.createElement('div');
        d.textContent = s;
        return d.innerHTML;
    }
})();
