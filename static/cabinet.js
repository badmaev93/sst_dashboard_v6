/* SST Dashboard v5 — cabinet.js: Personal cabinet per role */
"use strict";

(function() {
    let _container = null;

    // ── Show / Hide ─────────────────────────────
    window.showCabinetView = function() {
        hideAllViews();
        _container = document.getElementById('cabinet-view');
        if (!_container) {
            _container = document.createElement('div');
            _container.id = 'cabinet-view';
            applyOverlayStyle(_container);
            document.body.appendChild(_container);
        }
        _container.style.display = 'flex';
        loadAndRender();
    };

    window.hideCabinetView = function() {
        if (_container) _container.style.display = 'none';
    };

    function hideAllViews() {
        if (window.hideCalendarView) hideCalendarView();
        if (window.hideRequestsView) hideRequestsView();
    }

    function applyOverlayStyle(el) {
        Object.assign(el.style, {
            position: 'fixed', inset: '0', zIndex: '8000',
            background: 'rgba(15,23,42,0.45)', backdropFilter: 'blur(4px)',
            display: 'none', alignItems: 'flex-start', justifyContent: 'center',
            paddingTop: '40px'
        });
    }

    // ── Load & Render ───────────────────────────
    async function loadAndRender() {
        _container.innerHTML = '<div style="color:#fff;font-size:15px;margin-top:80px">Загрузка...</div>';

        let user = null;
        let personnel = [];
        try {
            user = await getCurrentUser();
        } catch (e) { /* noop */ }

        if (!user) {
            _container.innerHTML = '';
            const msg = document.createElement('div');
            Object.assign(msg.style, {
                background: '#fff', borderRadius: '14px', padding: '40px', textAlign: 'center',
                boxShadow: '0 20px 60px rgba(0,0,0,0.18)', fontFamily: 'inherit'
            });
            msg.innerHTML = '<p style="font-size:15px;color:#64748b;margin:0 0 16px">Необходимо войти в систему</p>' +
                '<button onclick="showLoginForm();hideCabinetView()" style="padding:10px 24px;background:#2563eb;' +
                'color:#fff;border:none;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer">Войти</button>';
            _container.innerHTML = '';
            _container.appendChild(msg);
            return;
        }

        try {
            const resp = await authFetch('/api/monitoring/users/personnel');
            if (resp.ok) personnel = await resp.json();
        } catch (e) { /* noop */ }

        render(user, personnel);
    }

    function render(user, personnel) {
        const panel = document.createElement('div');
        Object.assign(panel.style, {
            background: '#fff', borderRadius: '14px', width: '800px', maxHeight: '85vh',
            overflow: 'auto', boxShadow: '0 20px 60px rgba(0,0,0,0.18)',
            fontFamily: 'inherit', padding: '28px'
        });

        const role = user.role || 'observer';
        const rm = window.ROLE_MAP || {};
        const ri = rm[role] || { label: role, color: '#6b7280', bg: '#f3f4f6' };

        let html = '';

        // Header with user info
        html += `
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:24px">
                <div style="display:flex;align-items:center;gap:14px">
                    <div style="width:48px;height:48px;border-radius:50%;background:${ri.bg};
                         display:flex;align-items:center;justify-content:center;
                         font-weight:700;font-size:20px;color:${ri.color}">
                        ${(user.full_name || user.username || '?')[0].toUpperCase()}
                    </div>
                    <div>
                        <div style="font-size:18px;font-weight:700;color:#1a2030">
                            ${esc(user.full_name || user.username)}
                        </div>
                        <div style="display:flex;align-items:center;gap:8px;margin-top:4px">
                            ${window.roleBadge ? window.roleBadge(role) : ri.label}
                            ${user.stations && user.stations.length ? '<span style="font-size:11px;color:#94a3b8">Станции: ' + user.stations.join(', ') + '</span>' : ''}
                        </div>
                    </div>
                </div>
                <button id="cab-close" style="padding:8px 12px;background:#f1f5f9;color:#64748b;border:none;
                        border-radius:8px;font-size:16px;cursor:pointer;line-height:1">&times;</button>
            </div>
        `;

        // Role-specific dashboard
        if (role === 'supervisor') {
            html += renderSupervisor(user, personnel);
        } else if (role === 'observer') {
            html += renderObserver(user);
        } else if (role === 'engineer') {
            html += renderEngineer(user);
        } else if (role === 'data_analyst') {
            html += renderAnalyst(user);
        } else {
            html += renderDefault(user);
        }

        panel.innerHTML = html;
        _container.innerHTML = '';
        _container.appendChild(panel);

        document.getElementById('cab-close').addEventListener('click', hideCabinetView);

        // Bind navigation buttons
        panel.querySelectorAll('[data-nav]').forEach(function(btn) {
            btn.addEventListener('click', function() {
                const target = btn.dataset.nav;
                hideCabinetView();
                if (target === 'calendar' && window.showCalendarView) showCalendarView();
                if (target === 'requests' && window.showRequestsView) showRequestsView();
            });
        });

        // Bind observer reading form
        const readingForm = panel.querySelector('#obs-reading-form');
        if (readingForm) {
            readingForm.addEventListener('submit', async function(e) {
                e.preventDefault();
                const errEl = panel.querySelector('#obs-reading-error');
                const station = panel.querySelector('#obs-station').value.trim();
                const value = panel.querySelector('#obs-value').value.trim();
                const param = panel.querySelector('#obs-param').value;
                if (!station || !value) {
                    errEl.textContent = 'Заполните станцию и значение';
                    errEl.style.display = 'block';
                    return;
                }
                try {
                    errEl.style.display = 'none';
                    const resp = await authFetch('/api/monitoring/readings/', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ station: station, parameter: param, value: parseFloat(value) })
                    });
                    if (!resp.ok) throw new Error('Ошибка отправки');
                    panel.querySelector('#obs-value').value = '';
                    const ok = document.createElement('div');
                    Object.assign(ok.style, {
                        padding: '8px 12px', borderRadius: '8px', background: '#d1fae5',
                        color: '#059669', fontSize: '12px', marginTop: '8px'
                    });
                    ok.textContent = 'Показание отправлено';
                    readingForm.appendChild(ok);
                    setTimeout(function() { ok.remove(); }, 3000);
                } catch (err) {
                    errEl.textContent = err.message;
                    errEl.style.display = 'block';
                }
            });
        }

        _container.addEventListener('click', function(e) {
            if (e.target === _container) hideCabinetView();
        });
    }

    // ── Supervisor Dashboard ────────────────────
    function renderSupervisor(user, personnel) {
        const stationCount = (user.stations || []).length || '—';
        return `
            <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:24px">
                ${summaryCard('Станции', stationCount, '#2563eb', '#dbeafe')}
                ${summaryCard('Персонал', personnel.length || '—', '#7c3aed', '#ede9fe')}
                ${summaryCard('Открытые заявки', '—', '#d97706', '#fef3c7')}
            </div>
            <h3 style="font-size:14px;font-weight:700;color:#1a2030;margin-bottom:12px">Быстрые действия</h3>
            <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:20px">
                ${navButton('Календарь', 'calendar', '#7c3aed')}
                ${navButton('Заявки', 'requests', '#2563eb')}
            </div>
            ${personnel.length ? renderPersonnelTable(personnel) : ''}
        `;
    }

    function renderPersonnelTable(personnel) {
        let rows = '';
        personnel.forEach(function(p) {
            const r = (window.ROLE_MAP || {})[p.role] || { label: p.role };
            rows += `<tr style="border-bottom:1px solid #f1f5f9">
                <td style="padding:8px 10px;font-weight:500">${esc(p.full_name || p.username || '-')}</td>
                <td style="padding:8px 10px">${window.roleBadge ? window.roleBadge(p.role) : r.label}</td>
                <td style="padding:8px 10px;color:#64748b;font-size:12px">${(p.stations || []).join(', ') || '-'}</td>
            </tr>`;
        });
        return `
            <h3 style="font-size:14px;font-weight:700;color:#1a2030;margin:20px 0 10px">Персонал</h3>
            <table style="width:100%;border-collapse:collapse;font-size:13px">
                <thead><tr style="border-bottom:2px solid #e2e8f0">
                    <th style="padding:8px 10px;text-align:left;font-size:11px;font-weight:600;color:#94a3b8;text-transform:uppercase">Имя</th>
                    <th style="padding:8px 10px;text-align:left;font-size:11px;font-weight:600;color:#94a3b8;text-transform:uppercase">Роль</th>
                    <th style="padding:8px 10px;text-align:left;font-size:11px;font-weight:600;color:#94a3b8;text-transform:uppercase">Станции</th>
                </tr></thead>
                <tbody>${rows}</tbody>
            </table>
        `;
    }

    // ── Observer Dashboard ──────────────────────
    function renderObserver(user) {
        const stations = user.stations || [];
        let stationCards = '';
        if (stations.length) {
            stations.forEach(function(st) {
                stationCards += `
                    <div style="padding:14px;border-radius:10px;background:#f8fafc;border:1px solid #e2e8f0">
                        <div style="font-size:13px;font-weight:700;color:#1a2030;margin-bottom:4px">${esc(st)}</div>
                        <div style="font-size:12px;color:#64748b">Назначенная станция</div>
                    </div>
                `;
            });
        } else {
            stationCards = '<div style="color:#94a3b8;font-size:13px">Нет назначенных станций</div>';
        }

        return `
            <h3 style="font-size:14px;font-weight:700;color:#1a2030;margin-bottom:12px">Назначенные станции</h3>
            <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px;margin-bottom:24px">
                ${stationCards}
            </div>
            <h3 style="font-size:14px;font-weight:700;color:#1a2030;margin-bottom:12px">Отправить показание</h3>
            <form id="obs-reading-form" style="max-width:400px">
                <div style="display:flex;gap:10px;margin-bottom:10px">
                    <label style="flex:1">
                        <span style="display:block;font-size:12px;font-weight:600;color:#475569;margin-bottom:4px">Станция</span>
                        <input id="obs-station" type="text" value="${stations[0] || ''}"
                               style="${inputStyle()}" />
                    </label>
                    <label style="flex:1">
                        <span style="display:block;font-size:12px;font-weight:600;color:#475569;margin-bottom:4px">Параметр</span>
                        <select id="obs-param" style="${inputStyle()}">
                            <option value="sst">ТПО</option>
                            <option value="air_temp">Темп. воздуха</option>
                            <option value="salinity">Соленость</option>
                            <option value="pressure">Давление</option>
                        </select>
                    </label>
                </div>
                <label style="display:block;margin-bottom:10px">
                    <span style="display:block;font-size:12px;font-weight:600;color:#475569;margin-bottom:4px">Значение</span>
                    <input id="obs-value" type="number" step="0.01" style="${inputStyle()}" />
                </label>
                <div id="obs-reading-error" style="display:none;margin-bottom:10px;padding:8px 12px;
                     border-radius:8px;background:#fef2f2;color:#dc2626;font-size:12px"></div>
                <button type="submit" style="padding:9px 22px;background:#059669;color:#fff;border:none;
                        border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;font-family:inherit">
                    Отправить
                </button>
            </form>
        `;
    }

    // ── Engineer Dashboard ──────────────────────
    function renderEngineer(user) {
        return `
            <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:14px;margin-bottom:24px">
                ${summaryCard('Назначенные станции', (user.stations || []).length || '—', '#d97706', '#fef3c7')}
                ${summaryCard('Проверки', '—', '#2563eb', '#dbeafe')}
            </div>
            <h3 style="font-size:14px;font-weight:700;color:#1a2030;margin-bottom:12px">Быстрые действия</h3>
            <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:20px">
                ${navButton('Календарь проверок', 'calendar', '#d97706')}
                ${navButton('Заявки на ТО', 'requests', '#2563eb')}
            </div>
            <h3 style="font-size:14px;font-weight:700;color:#1a2030;margin-bottom:12px">Станции</h3>
            <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px">
                ${(user.stations || []).map(function(st) {
                    return '<div style="padding:14px;border-radius:10px;background:#fef3c7;border:1px solid #fde68a">' +
                           '<div style="font-size:13px;font-weight:700;color:#92400e">' + esc(st) + '</div>' +
                           '<div style="font-size:12px;color:#a16207;margin-top:2px">Оборудование</div></div>';
                }).join('') || '<div style="color:#94a3b8;font-size:13px">Нет назначенных станций</div>'}
            </div>
        `;
    }

    // ── Analyst Dashboard ───────────────────────
    function renderAnalyst(user) {
        return `
            <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:14px;margin-bottom:24px">
                ${summaryCard('Карта ТПО', 'SST Map', '#2563eb', '#dbeafe')}
                ${summaryCard('Прогноз', 'Forecast', '#7c3aed', '#ede9fe')}
            </div>
            <h3 style="font-size:14px;font-weight:700;color:#1a2030;margin-bottom:12px">Инструменты</h3>
            <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin-bottom:20px">
                <div style="padding:16px;border-radius:10px;background:#dbeafe;border:1px solid #93c5fd;cursor:pointer"
                     onclick="hideCabinetView()">
                    <div style="font-size:14px;font-weight:700;color:#1e40af;margin-bottom:4px">Карта ТПО</div>
                    <div style="font-size:12px;color:#3b82f6">Интерактивная карта температуры поверхности океана</div>
                </div>
                <div style="padding:16px;border-radius:10px;background:#ede9fe;border:1px solid #c4b5fd;cursor:pointer">
                    <div style="font-size:14px;font-weight:700;color:#5b21b6;margin-bottom:4px">Прогнозирование</div>
                    <div style="font-size:12px;color:#7c3aed">Модели прогнозирования SST</div>
                </div>
                <div style="padding:16px;border-radius:10px;background:#d1fae5;border:1px solid #6ee7b7;cursor:pointer">
                    <div style="font-size:14px;font-weight:700;color:#065f46;margin-bottom:4px">Экспорт данных</div>
                    <div style="font-size:12px;color:#059669">Выгрузка данных в CSV/Excel</div>
                </div>
                <div style="padding:16px;border-radius:10px;background:#fef3c7;border:1px solid #fde68a;cursor:pointer"
                     data-nav="calendar">
                    <div style="font-size:14px;font-weight:700;color:#92400e;margin-bottom:4px">Календарь</div>
                    <div style="font-size:12px;color:#d97706">Расписание и события</div>
                </div>
            </div>
        `;
    }

    // ── Default Dashboard ───────────────────────
    function renderDefault(user) {
        return `
            <div style="text-align:center;padding:30px 0;color:#64748b">
                <p style="font-size:14px;margin:0 0 12px">Добро пожаловать в личный кабинет</p>
                <div style="display:flex;gap:10px;justify-content:center">
                    ${navButton('Календарь', 'calendar', '#7c3aed')}
                    ${navButton('Заявки', 'requests', '#2563eb')}
                </div>
            </div>
        `;
    }

    // ── Components ──────────────────────────────
    function summaryCard(label, value, color, bg) {
        return `<div style="padding:18px;border-radius:10px;background:${bg};border:1px solid ${color}20">
            <div style="font-size:24px;font-weight:800;color:${color}">${value}</div>
            <div style="font-size:12px;font-weight:600;color:${color};opacity:0.8;margin-top:2px">${label}</div>
        </div>`;
    }

    function navButton(label, target, color) {
        return `<button data-nav="${target}" style="padding:9px 20px;background:${color};color:#fff;border:none;
                border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;font-family:inherit;
                transition:opacity .15s" onmouseover="this.style.opacity='0.85'"
                onmouseout="this.style.opacity='1'">${label}</button>`;
    }

    // ── Helpers ──────────────────────────────────
    function esc(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }
    function inputStyle() {
        return 'width:100%;padding:8px 12px;border:1px solid #d1d5db;border-radius:8px;' +
               'font-size:13px;font-family:inherit;';
    }
})();
