/* SST Dashboard v5 — requests_ui.js: Request management UI */
"use strict";

(function() {
    const style = document.createElement('style');
    style.textContent = `
        #req-create:focus-visible,
        #req-close:focus-visible,
        #req-filter-status:focus-visible,
        #req-filter-type:focus-visible,
        #detail-close:focus-visible,
        #req-form-close:focus-visible,
        #req-form-submit:focus-visible,
        #detail-approve:focus-visible,
        #detail-reject:focus-visible,
        #detail-submit:focus-visible,
        button[data-action]:focus-visible {
            outline: 2px solid #0055aa;
            outline-offset: 1px;
        }
        tr[data-row="true"]:focus-visible {
            outline: 2px solid #0055aa;
            outline-offset: -1px;
        }
    `;
    document.head.appendChild(style);
})();


(function() {
    const STATUS_MAP = {
        pending:     { label: 'На подписи',  color: '#a16207', bg: '#fef9c3' },
        in_progress: { label: 'В работе',    color: '#2563eb', bg: '#dbeafe' },
        signed:      { label: 'Утверждена',  color: '#059669', bg: '#d1fae5' },
        rejected:    { label: 'Отклонена',   color: '#dc2626', bg: '#fee2e2' },
        completed:   { label: 'Завершена',   color: '#6b7280', bg: '#f3f4f6' },
        draft:       { label: 'Черновик',    color: '#475569', bg: '#f1f5f9' }
    };

    const TYPE_MAP = {
        supply:      { label: 'Снабжение' },
        maintenance: { label: 'ТО' },
        leave:       { label: 'Отпуск' },
        equipment:   { label: 'Оборудование' },
        inspection:  { label: 'Проверка' },
        repair:      { label: 'Ремонт' },
        calibration: { label: 'Калибровка' },
    };

    const PRIORITY_MAP = {
        low:    { label: 'Низкий',   color: '#059669' },
        normal: { label: 'Обычный',  color: '#2563eb' },
        medium: { label: 'Средний',  color: '#d97706' },
        high:   { label: 'Высокий',  color: '#dc2626' },
        urgent: { label: 'Срочный',  color: '#7c3aed' }
    };

    let _container = null;
    let _requests = [];
    let _filterStatus = '';
    let _filterType = '';
    let _userRole = null;

    async function _loadUserRole() {
        try {
            if (window.getCurrentUser) {
                const u = await window.getCurrentUser();
                _userRole = u && u.role ? u.role : null;
            }
        } catch (_) { _userRole = null; }
    }

    // ── Show / Hide ─────────────────────────────
    window.showRequestsView = function() {
        hideAllViews();
        _container = document.getElementById('requests-view');
        if (!_container) {
            _container = document.createElement('div');
            _container.id = 'requests-view';
            _container.setAttribute('role', 'dialog');
            _container.setAttribute('aria-modal', 'true');
            _container.setAttribute('aria-label', 'Управление заявками');
            _container.setAttribute('tabindex', '-1');
            applyOverlayStyle(_container);
            document.body.appendChild(_container);
        }
        _container.style.display = 'flex';
        loadAndRender();
        // Auto-focus
        setTimeout(() => { const btn = document.getElementById('req-close'); if(btn) btn.focus(); else _container.focus(); }, 100);
    };

    window.hideRequestsView = function() {
        if (_container) _container.style.display = 'none';
    };

    function hideAllViews() {
        if (window.hideCalendarView) hideCalendarView();
        if (window.hideCabinetView) hideCabinetView();
    }

    function applyOverlayStyle(el) {
        Object.assign(el.style, {
            position: 'fixed', top: '44px', left: '0', right: '0', bottom: '0',
            zIndex: '8000',
            background: '#f8f9fa',
            display: 'none', alignItems: 'flex-start', justifyContent: 'center',
            overflow: 'auto', paddingTop: '24px'
        });
    }

    // ── Fetch ───────────────────────────────────
    async function fetchRequests() {
        try {
            let url = '/api/monitoring/requests/';
            const params = [];
            if (_filterStatus) params.push('status=' + _filterStatus);
            if (_filterType) params.push('type=' + _filterType);
            if (params.length) url += '?' + params.join('&');
            const resp = await authFetch(url);
            if (resp.ok) _requests = await resp.json();
            else _requests = [];
        } catch (e) {
            _requests = [];
        }
    }

    async function loadAndRender() {
        if (_container) _container.innerHTML = '<div style="color:#fff;font-size:15px;margin-top:80px">Загрузка...</div>';
        await Promise.all([fetchRequests(), _loadUserRole()]);
        render();
    }

    // ── Render ──────────────────────────────────
    function render() {
        const panel = document.createElement('div');
        Object.assign(panel.style, {
            background: '#fff', borderRadius: '14px', width: '900px', maxHeight: '85vh',
            overflow: 'auto', boxShadow: '0 20px 60px rgba(0,0,0,0.18)',
            fontFamily: 'inherit', padding: '28px'
        });

        // Header
        let html = `
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px">
                <h2 style="margin:0;font-size:18px;font-weight:700;color:#1a2030">Заявки</h2>
                <div style="display:flex;gap:8px">
                    <button id="req-create" aria-label="Создать новую заявку" style="padding:8px 18px;background:#2563eb;color:#fff;border:none;
                            border-radius:8px;font-size:12px;font-weight:600;cursor:pointer;font-family:inherit">
                        Создать заявку
                    </button>
                    <button id="req-close" aria-label="Закрыть заявки" style="padding:8px 12px;background:#f1f5f9;color:#64748b;border:none;
                            border-radius:8px;font-size:16px;cursor:pointer;line-height:1">&times;</button>
                </div>
            </div>
        `;

        // Filters
        let statusOpts = '<option value="">Все статусы</option>';
        Object.keys(STATUS_MAP).forEach(function(k) {
            statusOpts += '<option value="' + k + '"' + (k === _filterStatus ? ' selected' : '') + '>' +
                          STATUS_MAP[k].label + '</option>';
        });
        let typeOpts = '<option value="">Все типы</option>';
        Object.keys(TYPE_MAP).forEach(function(k) {
            typeOpts += '<option value="' + k + '"' + (k === _filterType ? ' selected' : '') + '>' +
                        TYPE_MAP[k].label + '</option>';
        });

        html += `
            <div style="display:flex;gap:10px;margin-bottom:16px">
                <select id="req-filter-status" aria-label="Фильтр заявок по статусу" style="${selectStyle()}">${statusOpts}</select>
                <select id="req-filter-type" aria-label="Фильтр заявок по типу" style="${selectStyle()}">${typeOpts}</select>
            </div>
        `;

        // Table
        html += `<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:13px">
            <thead>
                <tr style="border-bottom:2px solid #e2e8f0">
                    <th style="${thStyle()}">Название</th>
                    <th style="${thStyle()}">Тип</th>
                    <th style="${thStyle()}">Приоритет</th>
                    <th style="${thStyle()}">Статус</th>
                    <th style="${thStyle()}">Станция</th>
                    <th style="${thStyle()}">Автор</th>
                    <th style="${thStyle()}">Дата</th>
                    <th style="${thStyle()}">Действия</th>
                </tr>
            </thead>
            <tbody>`;

        if (!_requests.length) {
            html += '<tr><td colspan="8" style="padding:30px;text-align:center;color:#94a3b8">Заявки не найдены</td></tr>';
        }

        _requests.forEach(function(r) {
            const st = STATUS_MAP[r.status] || { label: r.status, color: '#6b7280', bg: '#f3f4f6' };
            const tp = TYPE_MAP[r.req_type || r.type] || { label: r.req_type || r.type || '-' };
            const pr = PRIORITY_MAP[r.priority] || { label: r.priority || '-', color: '#6b7280' };

            html += `<tr style=\"border-bottom:1px solid #f1f5f9;cursor:pointer\" data-id=\"${r.id}\" data-row=\"true\" role=\"button\" tabindex=\"0\">
                <td style="${tdStyle()};font-weight:600;color:#1a2030;max-width:200px;overflow:hidden;
                    text-overflow:ellipsis;white-space:nowrap">${esc(r.title || '-')}</td>
                <td style="${tdStyle()}">${badge(tp.label, '#475569', '#f1f5f9')}</td>
                <td style="${tdStyle()}">${badge(pr.label, pr.color, '#fff')}</td>
                <td style="${tdStyle()}">${badge(st.label, st.color, st.bg)}</td>
                <td style="${tdStyle()};color:#64748b">${esc(r.station_name || r.station || '-')}</td>
                <td style="${tdStyle()};color:#64748b">${esc(r.author_name || r.author || '-')}</td>
                <td style="${tdStyle()};color:#94a3b8;white-space:nowrap">${formatDateShort(r.created_at || r.date || '')}</td>
                <td style="${tdStyle()}">${actionButtons(r)}</td>
            </tr>`;
        });

        html += '</tbody></table></div>';

        panel.innerHTML = html;
        _container.innerHTML = '';
        _container.appendChild(panel);

        // Bind events
        document.getElementById('req-close').addEventListener('click', hideRequestsView);
        document.getElementById('req-create').addEventListener('click', showCreateForm);
        document.getElementById('req-filter-status').addEventListener('change', function() {
            _filterStatus = this.value; loadAndRender();
        });
        document.getElementById('req-filter-type').addEventListener('change', function() {
            _filterType = this.value; loadAndRender();
        });

        // Action buttons
        panel.querySelectorAll('[data-action]').forEach(function(btn) {
            btn.addEventListener('click', async function() {
                const id = btn.dataset.id;
                const action = btn.dataset.action;
                let endpoint, method = 'POST';
                if (action === 'submit') {
                    endpoint = '/api/monitoring/requests/' + id;
                    method = 'PUT';
                    try {
                        btn.disabled = true; btn.textContent = '...';
                        await authFetch(endpoint, {
                            method,
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ status: 'pending' })
                        });
                        loadAndRender();
                    } catch (e) { btn.textContent = 'Ошибка'; }
                } else if (action === 'sign-approve') {
                    endpoint = '/api/monitoring/requests/' + id + '/sign?action=approve';
                    try {
                        btn.disabled = true; btn.textContent = '...';
                        await authFetch(endpoint, { method: 'POST' });
                        loadAndRender();
                    } catch (e) { btn.textContent = 'Ошибка'; }
                } else if (action === 'sign-reject') {
                    endpoint = '/api/monitoring/requests/' + id + '/sign?action=reject';
                    try {
                        btn.disabled = true; btn.textContent = '...';
                        await authFetch(endpoint, { method: 'POST' });
                        loadAndRender();
                    } catch (e) { btn.textContent = 'Ошибка'; }
                }
            });
        });

        // Row click → detail view
        panel.querySelectorAll('tr[data-row]').forEach(function(row) {
            row.addEventListener('keydown', function(e) {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    row.click();
                }
            });
            row.addEventListener('click', function(e) {
                if (e.target.closest('[data-action]')) return;
                const id = parseInt(row.dataset.id);
                var r = _requests.find(function(x) { return x.id === id; });
                if (r) showDetailView(r);
            });
        });

        // no click-outside-to-close — full screen view
    }

    // ── Detail View ─────────────────────────────
    function showDetailView(r) {
        var old = document.getElementById('req-detail-modal');
        if (old) old.remove();

        var modal = document.createElement('div');
        modal.id = 'req-detail-modal';
        modal.setAttribute('role', 'dialog');
        modal.setAttribute('aria-modal', 'true');
        modal.setAttribute('aria-label', 'Детали заявки');
        modal.setAttribute('tabindex', '-1');
        Object.assign(modal.style, {
            position: 'fixed', top: '47px', left: '0', right: '0', bottom: '0',
            zIndex: '8800', background: '#fff', padding: '32px 40px',
            overflow: 'auto', fontFamily: 'inherit'
        });

        var st = STATUS_MAP[r.status] || { label: r.status, color: '#6b7280', bg: '#f3f4f6' };
        var tp = TYPE_MAP[r.req_type || r.type] || { label: r.req_type || r.type || '-' };
        var pr = PRIORITY_MAP[r.priority] || { label: r.priority || '-', color: '#6b7280' };
        var isSupervisor = _userRole === 'supervisor' || _userRole === 'admin' || _userRole === 'leader';

        var signBtns = '';
        if (r.status === 'pending' && isSupervisor) {
            signBtns = `
                <div style="display:flex;gap:10px;margin-top:18px">
                    <button id="detail-approve" style="flex:1;padding:10px;background:#059669;color:#fff;
                        border:none;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;font-family:inherit">
                        ✍ Подписать (утвердить)
                    </button>
                    <button id="detail-reject" style="flex:1;padding:10px;background:#dc2626;color:#fff;
                        border:none;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;font-family:inherit">
                        ✕ Отклонить
                    </button>
                </div>`;
        } else if (r.status === 'draft') {
            signBtns = `
                <div style="margin-top:18px">
                    <button id="detail-submit" style="width:100%;padding:10px;background:#2563eb;color:#fff;
                        border:none;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;font-family:inherit">
                        📤 Отправить на подпись
                    </button>
                </div>`;
        }

        modal.innerHTML = `
          <div style="max-width:640px;margin:0 auto">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:16px">
                <div>
                    <h3 style="margin:0 0 6px;font-size:17px;font-weight:700;color:#1a2030">${esc(r.title || 'Без названия')}</h3>
                    <div style="display:flex;gap:8px;flex-wrap:wrap">
                        ${badge(st.label, st.color, st.bg)}
                        ${badge(tp.label, '#475569', '#f1f5f9')}
                        ${badge(pr.label, pr.color, '#fff')}
                    </div>
                </div>
                <button id="detail-close" aria-label="Закрыть детали заявки" style="background:#f1f5f9;border:none;border-radius:8px;
                    width:36px;height:36px;font-size:18px;cursor:pointer;color:#64748b;flex-shrink:0;z-index:10">&times;</button>
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px">
                <div style="font-size:12px">
                    <span style="color:#94a3b8;display:block;margin-bottom:2px">Станция</span>
                    <span style="font-weight:600;color:#334155">${esc(r.station_name || r.station || '—')}</span>
                </div>
                <div style="font-size:12px">
                    <span style="color:#94a3b8;display:block;margin-bottom:2px">Автор</span>
                    <span style="font-weight:600;color:#334155">${esc(r.author_name || r.author || '—')}</span>
                </div>
                <div style="font-size:12px">
                    <span style="color:#94a3b8;display:block;margin-bottom:2px">Создана</span>
                    <span style="font-weight:600;color:#334155">${formatDateShort(r.created_at || r.date || '')}</span>
                </div>
                <div style="font-size:12px">
                    <span style="color:#94a3b8;display:block;margin-bottom:2px">Подписана</span>
                    <span style="font-weight:600;color:#334155">${r.signed_at ? formatDateShort(r.signed_at) : '—'}</span>
                </div>
            </div>
            ${r.description ? '<div style="font-size:13px;color:#475569;line-height:1.6;padding:12px;background:#f8fafc;border-radius:8px;margin-bottom:6px">' + esc(r.description) + '</div>' : ''}
            ${signBtns}
          </div>
        `;

        document.body.appendChild(modal);
        setTimeout(() => { const btn = document.getElementById('detail-close'); if(btn) btn.focus(); else modal.focus(); }, 10);
        document.getElementById('detail-close').addEventListener('click', function() { modal.remove(); });

        if (r.status === 'pending' && isSupervisor) {
            document.getElementById('detail-approve').addEventListener('click', async function() {
                this.disabled = true; this.textContent = '...';
                try {
                    await authFetch('/api/monitoring/requests/' + r.id + '/sign?action=approve', { method: 'POST' });
                    modal.remove(); loadAndRender();
                } catch(e) { this.textContent = 'Ошибка'; }
            });
            document.getElementById('detail-reject').addEventListener('click', async function() {
                this.disabled = true; this.textContent = '...';
                try {
                    await authFetch('/api/monitoring/requests/' + r.id + '/sign?action=reject', { method: 'POST' });
                    modal.remove(); loadAndRender();
                } catch(e) { this.textContent = 'Ошибка'; }
            });
        }
        if (r.status === 'draft') {
            var submitBtn = document.getElementById('detail-submit');
            if (submitBtn) submitBtn.addEventListener('click', async function() {
                this.disabled = true; this.textContent = '...';
                try {
                    await authFetch('/api/monitoring/requests/' + r.id, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ status: 'pending' })
                    });
                    modal.remove(); loadAndRender();
                } catch(e) { this.textContent = 'Ошибка'; }
            });
        }
    }

    // ── Action Buttons ──────────────────────────
    function actionButtons(r) {
        let html = '';
        const sm = 'padding:5px 12px;border:none;border-radius:6px;font-size:11px;font-weight:600;' +
                   'cursor:pointer;font-family:inherit;margin-right:4px;transition:opacity .15s;';

        if (r.status === 'draft') {
            html += `<button data-action="submit" data-id="${r.id}"
                     style="${sm}background:#eff6ff;color:#2563eb;border:1px solid #bfdbfe">
                     📤 На подпись</button>`;
        }
        if (r.status === 'pending') {
            const isSupervisor = _userRole === 'supervisor' || _userRole === 'admin' || _userRole === 'leader';
            if (isSupervisor) {
                html += `<button data-action="sign-approve" data-id="${r.id}"
                         style="${sm}background:#ecfdf5;color:#059669;border:1px solid #6ee7b7">
                         ✍ Подписать</button>`;
                html += `<button data-action="sign-reject" data-id="${r.id}"
                         style="${sm}background:#fef2f2;color:#dc2626;border:1px solid #fca5a5">
                         ✕ Отклонить</button>`;
            } else {
                html += `<span style="font-size:11px;color:#a16207;background:#fef9c3;
                         padding:3px 8px;border-radius:6px;border:1px solid #fde68a">
                         ⏳ На подписи у руководителя</span>`;
            }
        }
        if (!html) html = '<span style="color:#cbd5e1;font-size:11px">&mdash;</span>';
        return html;
    }

    // ── Create Request Form ─────────────────────
    function showCreateForm() {
        let form = document.getElementById('req-create-form');
        if (form) form.remove();

        form = document.createElement('div');
        form.id = 'req-create-form';
        form.setAttribute('role', 'dialog');
        form.setAttribute('aria-modal', 'true');
        form.setAttribute('aria-label', 'Создание заявки');
        form.setAttribute('tabindex', '-1');
        Object.assign(form.style, {
            position: 'fixed', top: '50%', left: '50%', transform: 'translate(-50%,-50%)',
            zIndex: '8600', background: '#fff', borderRadius: '14px', padding: '28px',
            boxShadow: '0 20px 60px rgba(0,0,0,0.22)', width: '440px', fontFamily: 'inherit'
        });

        let typeOpts = '';
        Object.keys(TYPE_MAP).forEach(function(k) {
            typeOpts += '<option value="' + k + '">' + TYPE_MAP[k].label + '</option>';
        });
        let priorOpts = '';
        Object.keys(PRIORITY_MAP).forEach(function(k) {
            priorOpts += '<option value="' + k + '"' + (k === 'medium' ? ' selected' : '') + '>' +
                         PRIORITY_MAP[k].label + '</option>';
        });

        form.innerHTML = `
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:18px">
                <h3 style="margin:0;font-size:16px;font-weight:700;color:#1a2030">Создать заявку</h3>
                <button id="req-form-close" aria-label="Закрыть форму создания заявки" style="background:none;border:none;font-size:18px;
                        cursor:pointer;color:#94a3b8">&times;</button>
            </div>
            ${field('Название', '<input id="req-f-title" type="text" style="' + inputStyle() + '" />')}
            ${field('Описание', '<textarea id="req-f-desc" rows="3" style="' + inputStyle() + 'resize:vertical"></textarea>')}
            <div style="display:flex;gap:10px;margin-bottom:14px">
                <label style="flex:1">
                    <span style="display:block;font-size:12px;font-weight:600;color:#475569;margin-bottom:4px">Тип</span>
                    <select id="req-f-type" style="${inputStyle()}">${typeOpts}</select>
                </label>
                <label style="flex:1">
                    <span style="display:block;font-size:12px;font-weight:600;color:#475569;margin-bottom:4px">Приоритет</span>
                    <select id="req-f-priority" style="${inputStyle()}">${priorOpts}</select>
                </label>
            </div>
            ${field('Станция', '<input id="req-f-station" type="text" placeholder="Код станции" style="' + inputStyle() + '" />')}
            <div id="req-form-error" style="display:none;margin-bottom:10px;padding:8px 12px;
                 border-radius:8px;background:#fef2f2;color:#dc2626;font-size:12px"></div>
            <button id="req-form-submit" style="width:100%;padding:10px;background:#2563eb;color:#fff;
                    border:none;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;
                    font-family:inherit">Создать</button>
        `;

        document.body.appendChild(form);
        setTimeout(() => { const title = document.getElementById('req-f-title'); if(title) title.focus(); else form.focus(); }, 10);

        document.getElementById('req-form-close').addEventListener('click', function() { form.remove(); });
        document.getElementById('req-form-submit').addEventListener('click', async function() {
            const submitBtn = this;
            const errEl = document.getElementById('req-form-error');
            errEl.style.display = 'none';
            const title = document.getElementById('req-f-title').value.trim();
            const desc = document.getElementById('req-f-desc').value.trim();
            const type = document.getElementById('req-f-type').value;
            const priority = document.getElementById('req-f-priority').value;
            const station = document.getElementById('req-f-station').value.trim();

            if (!title) {
                errEl.textContent = 'Укажите название заявки';
                errEl.style.display = 'block';
                return;
            }

            submitBtn.disabled = true;
            submitBtn.textContent = 'Создание...';

            try {
                const resp = await authFetch('/api/monitoring/requests/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        title: title, description: desc, type: type,
                        priority: priority, station: station
                    })
                });
                if (!resp.ok) {
                    const d = await resp.json().catch(function() { return {}; });
                    throw new Error(d.detail || 'Ошибка создания заявки');
                }
                form.remove();
                loadAndRender();
            } catch (e) {
                submitBtn.disabled = false;
                submitBtn.textContent = 'Создать';
                errEl.textContent = e.message;
                errEl.style.display = 'block';
            }
        });
    }

    // ── Helpers ──────────────────────────────────
    function esc(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }
    function badge(text, color, bg) {
        return '<span style="display:inline-block;padding:2px 10px;border-radius:12px;font-size:11px;' +
               'font-weight:600;color:' + color + ';background:' + bg + ';white-space:nowrap">' + text + '</span>';
    }
    function formatDateShort(s) {
        if (!s) return '-';
        return s.substring(0, 10).split('-').reverse().join('.');
    }
    function thStyle() {
        return 'padding:8px 10px;text-align:left;font-size:11px;font-weight:600;color:#94a3b8;' +
               'text-transform:uppercase;letter-spacing:0.04em;white-space:nowrap';
    }
    function tdStyle() { return 'padding:10px 10px'; }
    function selectStyle() {
        return 'padding:7px 12px;border:1px solid #d1d5db;border-radius:8px;font-size:12px;' +
               'font-family:inherit;background:#fff;color:#334155;cursor:pointer';
    }
    function inputStyle() {
        return 'width:100%;padding:8px 12px;border:1px solid #d1d5db;border-radius:8px;' +
               'font-size:13px;font-family:inherit;';
    }
    function field(label, input) {
        return '<label style="display:block;margin-bottom:14px">' +
               '<span style="display:block;font-size:12px;font-weight:600;color:#475569;margin-bottom:4px">' +
               label + '</span>' + input + '</label>';
    }
})();
