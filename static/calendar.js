/* SST Dashboard v6 — calendar.js: Daily Planning Calendar */
"use strict";

(function() {
    const EVENT_TYPES = {
        equipment_check: { label: 'Проверка оборудования', color: '#2563eb', icon: '🔧' },
        shift_change:    { label: 'Смена вахты',           color: '#059669', icon: '🔄' },
        maintenance:     { label: 'Техобслуживание',       color: '#d97706', icon: '⚙️' },
        meeting:         { label: 'Совещание',             color: '#7c3aed', icon: '👥' },
        inspection:      { label: 'Инспекция',             color: '#dc2626', icon: '📋' },
        other:           { label: 'Другое',                color: '#6b7280', icon: '📌' }
    };

    const PRIORITY_CONFIG = {
        P1: { label: 'P1', color: '#ef4444', bg: '#fef2f2' },
        P2: { label: 'P2', color: '#f59e0b', bg: '#fffbeb' },
        P3: { label: 'P3', color: '#3b82f6', bg: '#eff6ff' }
    };

    const FOCUS_TYPE_COLORS = {
        '#3b82f6': 'Глубокая работа',
        '#7c3aed': 'Совещание',
        '#059669': 'Полевые работы',
        '#06b6d4': 'Анализ данных',
        '#f59e0b': 'Планирование'
    };

    const MONTHS_RU = [
        'Январь','Февраль','Март','Апрель','Май','Июнь',
        'Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь'
    ];
    const MONTHS_RU_GEN = [
        'января','февраля','марта','апреля','мая','июня',
        'июля','августа','сентября','октября','ноября','декабря'
    ];
    const DAYS_SHORT = ['Пн','Вт','Ср','Чт','Пт','Сб','Вс'];
    const DAYS_FULL = ['Воскресенье','Понедельник','Вторник','Среда','Четверг','Пятница','Суббота'];

    const HOUR_START = 7;
    const HOUR_END = 21;
    const HOUR_HEIGHT = 60;

    let _selectedDate = new Date();
    let _miniYear, _miniMonth;
    let _events = [], _tasks = [], _focusBlocks = [];
    let _container = null;
    let _dragState = null;

    // ── Inject Styles ───────────────────────────
    function injectStyles() {
        if (document.getElementById('cal-v6-styles')) return;
        const style = document.createElement('style');
        style.id = 'cal-v6-styles';
        style.textContent = `
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

            #calendar-view * { box-sizing: border-box; }

            #calendar-view {
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            }

            .cal-panel {
                background: #ffffff;
                border-radius: 16px;
                width: calc(100vw - 60px);
                max-width: 1440px;
                height: calc(100vh - 60px);
                display: flex;
                overflow: hidden;
                box-shadow: 0 25px 80px rgba(0,0,0,0.2), 0 0 0 1px rgba(0,0,0,0.05);
                animation: calSlideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1);
            }

            @keyframes calSlideUp {
                from { opacity: 0; transform: translateY(20px) scale(0.98); }
                to { opacity: 1; transform: translateY(0) scale(1); }
            }

            @keyframes calFadeIn {
                from { opacity: 0; }
                to { opacity: 1; }
            }

            /* Left Sidebar */
            .cal-left {
                width: 260px;
                min-width: 260px;
                border-right: 1px solid #f1f5f9;
                display: flex;
                flex-direction: column;
                background: #fafbfc;
            }

            .cal-left-header {
                padding: 20px 20px 16px;
                border-bottom: 1px solid #f1f5f9;
            }

            .cal-mini-nav {
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 12px;
            }

            .cal-mini-nav-title {
                font-size: 13px;
                font-weight: 600;
                color: #1e293b;
            }

            .cal-mini-btn {
                width: 28px; height: 28px;
                display: flex; align-items: center; justify-content: center;
                border: none; background: transparent;
                color: #94a3b8; cursor: pointer; border-radius: 6px;
                font-size: 14px; transition: all 0.15s;
            }
            .cal-mini-btn:hover { background: #e2e8f0; color: #475569; }

            .cal-mini-grid {
                display: grid;
                grid-template-columns: repeat(7, 1fr);
                gap: 1px;
            }

            .cal-mini-day-name {
                text-align: center;
                font-size: 10px;
                font-weight: 600;
                color: #94a3b8;
                padding: 4px 0;
            }

            .cal-mini-day {
                text-align: center;
                font-size: 11px;
                padding: 4px 0;
                cursor: pointer;
                border-radius: 6px;
                color: #475569;
                transition: all 0.1s;
                font-weight: 500;
            }
            .cal-mini-day:hover { background: #e2e8f0; }
            .cal-mini-day:focus-visible, .cal-priority-tab:focus-visible {
                outline: 2px solid #2563eb;
                outline-offset: 1px;
            }
            .cal-mini-day.today { background: #2563eb; color: #fff; font-weight: 700; }
            .cal-mini-day.selected { background: #dbeafe; color: #2563eb; font-weight: 700; }
            .cal-mini-day.other-month { color: #cbd5e1; }
            .cal-mini-day.has-event::after {
                content: '';
                display: block;
                width: 4px; height: 4px;
                border-radius: 50%;
                background: #2563eb;
                margin: 1px auto 0;
            }

            /* Upcoming Events */
            .cal-upcoming {
                flex: 1;
                overflow-y: auto;
                padding: 16px 20px;
            }

            .cal-upcoming-title {
                font-size: 11px;
                font-weight: 700;
                color: #94a3b8;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                margin-bottom: 10px;
            }

            .cal-upcoming-item {
                padding: 10px 12px;
                background: #fff;
                border-radius: 8px;
                margin-bottom: 6px;
                border-left: 3px solid #e2e8f0;
                cursor: pointer;
                transition: all 0.15s;
            }
            .cal-upcoming-item:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.06); }

            .cal-upcoming-item-title {
                font-size: 12px;
                font-weight: 600;
                color: #1e293b;
                margin-bottom: 2px;
            }

            .cal-upcoming-item-time {
                font-size: 10px;
                color: #94a3b8;
            }

            /* Center - Day View */
            .cal-center {
                flex: 1;
                display: flex;
                flex-direction: column;
                min-width: 0;
            }

            .cal-center-header {
                padding: 16px 24px;
                border-bottom: 1px solid #f1f5f9;
                display: flex;
                align-items: center;
                justify-content: space-between;
                background: #fff;
            }

            .cal-day-nav {
                display: flex;
                align-items: center;
                gap: 8px;
            }

            .cal-nav-btn {
                width: 32px; height: 32px;
                display: flex; align-items: center; justify-content: center;
                border: 1px solid #e2e8f0; background: #fff;
                border-radius: 8px; cursor: pointer; color: #475569;
                font-size: 14px; transition: all 0.15s;
            }
            .cal-nav-btn:hover { background: #f8fafc; border-color: #cbd5e1; }

            .cal-today-btn {
                padding: 6px 14px;
                border: 1px solid #e2e8f0; background: #fff;
                border-radius: 8px; cursor: pointer; color: #475569;
                font-size: 12px; font-weight: 600; font-family: inherit;
                transition: all 0.15s;
            }
            .cal-today-btn:hover { background: #f8fafc; border-color: #cbd5e1; }

            .cal-day-title {
                font-size: 18px;
                font-weight: 700;
                color: #0f172a;
                margin-left: 12px;
            }

            .cal-day-subtitle {
                font-size: 12px;
                color: #94a3b8;
                font-weight: 500;
                margin-left: 8px;
            }

            .cal-header-actions {
                display: flex;
                gap: 8px;
                align-items: center;
            }

            .cal-add-btn {
                padding: 7px 16px;
                background: #2563eb;
                color: #fff;
                border: none;
                border-radius: 8px;
                font-size: 12px;
                font-weight: 600;
                cursor: pointer;
                font-family: inherit;
                transition: all 0.15s;
                display: flex;
                align-items: center;
                gap: 4px;
            }
            .cal-add-btn:hover { background: #1d4ed8; }

            .cal-close-btn {
                width: 32px; height: 32px;
                display: flex; align-items: center; justify-content: center;
                border: 1px solid #e2e8f0; background: #fff;
                border-radius: 8px; cursor: pointer; color: #94a3b8;
                font-size: 16px; transition: all 0.15s;
            }
            .cal-close-btn:hover { background: #fef2f2; color: #ef4444; border-color: #fecaca; }

            /* Timeline */
            .cal-timeline-wrap {
                flex: 1;
                overflow-y: auto;
                position: relative;
            }

            .cal-timeline {
                position: relative;
                min-height: ${(HOUR_END - HOUR_START) * HOUR_HEIGHT}px;
            }

            .cal-hour-row {
                height: ${HOUR_HEIGHT}px;
                display: flex;
                border-bottom: 1px solid #f8fafc;
                position: relative;
            }

            .cal-hour-label {
                width: 60px;
                min-width: 60px;
                padding: 8px 12px 0 0;
                text-align: right;
                font-size: 11px;
                font-weight: 500;
                color: #94a3b8;
            }

            .cal-hour-content {
                flex: 1;
                border-left: 1px solid #f1f5f9;
                position: relative;
            }

            .cal-hour-content::after {
                content: '';
                position: absolute;
                left: 0; right: 0;
                top: 50%;
                border-bottom: 1px dashed #f1f5f9;
            }

            /* Event Block on Timeline */
            .cal-event-block {
                position: absolute;
                left: 68px;
                right: 12px;
                border-radius: 8px;
                padding: 6px 10px;
                font-size: 11px;
                cursor: pointer;
                overflow: hidden;
                transition: box-shadow 0.15s, transform 0.1s;
                z-index: 2;
                border-left: 3px solid;
            }
            .cal-event-block:hover {
                box-shadow: 0 4px 12px rgba(0,0,0,0.12);
                transform: translateX(2px);
            }

            .cal-event-block-title {
                font-weight: 600;
                color: #1e293b;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }

            .cal-event-block-time {
                font-size: 10px;
                color: #64748b;
                margin-top: 1px;
            }

            /* Focus Block */
            .cal-focus-block {
                position: absolute;
                left: 60px;
                right: 0;
                border-radius: 0;
                padding: 6px 16px;
                font-size: 11px;
                font-weight: 600;
                opacity: 0.15;
                z-index: 1;
                pointer-events: none;
                display: flex;
                align-items: flex-start;
            }

            .cal-focus-label {
                position: absolute;
                left: 60px;
                font-size: 10px;
                font-weight: 600;
                padding: 2px 8px;
                border-radius: 0 0 6px 0;
                z-index: 1;
                pointer-events: none;
            }

            /* Current Time Line */
            .cal-now-line {
                position: absolute;
                left: 54px;
                right: 0;
                height: 2px;
                background: #ef4444;
                z-index: 5;
                pointer-events: none;
            }
            .cal-now-line::before {
                content: '';
                position: absolute;
                left: 0; top: -4px;
                width: 10px; height: 10px;
                border-radius: 50%;
                background: #ef4444;
            }

            /* Right Sidebar */
            .cal-right {
                width: 300px;
                min-width: 300px;
                border-left: 1px solid #f1f5f9;
                display: flex;
                flex-direction: column;
                background: #fafbfc;
            }

            .cal-right-header {
                padding: 16px 20px;
                border-bottom: 1px solid #f1f5f9;
                display: flex;
                align-items: center;
                justify-content: space-between;
            }

            .cal-right-title {
                font-size: 14px;
                font-weight: 700;
                color: #0f172a;
            }

            .cal-task-count {
                font-size: 11px;
                font-weight: 600;
                color: #94a3b8;
                background: #f1f5f9;
                padding: 2px 8px;
                border-radius: 10px;
            }

            .cal-tasks-list {
                flex: 1;
                overflow-y: auto;
                padding: 12px 16px;
            }

            .cal-task-item {
                background: #fff;
                border-radius: 10px;
                padding: 12px 14px;
                margin-bottom: 8px;
                border: 1px solid #f1f5f9;
                transition: all 0.15s;
                cursor: grab;
                position: relative;
            }
            .cal-task-item:hover {
                border-color: #e2e8f0;
                box-shadow: 0 2px 8px rgba(0,0,0,0.04);
            }
            .cal-task-item.completed {
                opacity: 0.5;
            }
            .cal-task-item.dragging {
                opacity: 0.4;
                transform: scale(0.98);
            }

            .cal-task-top {
                display: flex;
                align-items: flex-start;
                gap: 8px;
            }

            .cal-task-drag {
                color: #d1d5db;
                cursor: grab;
                font-size: 12px;
                padding: 2px 0;
                user-select: none;
            }

            .cal-task-checkbox {
                width: 16px; height: 16px;
                border-radius: 50%;
                border: 2px solid #d1d5db;
                cursor: pointer;
                flex-shrink: 0;
                margin-top: 1px;
                transition: all 0.15s;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .cal-task-checkbox.checked {
                background: #10b981;
                border-color: #10b981;
            }
            .cal-task-checkbox.checked::after {
                content: '\\2713';
                color: #fff;
                font-size: 10px;
                font-weight: 700;
            }
            .cal-task-checkbox:focus-visible {
                outline: 2px solid #2563eb;
                outline-offset: 2px;
            }

            .cal-task-info { flex: 1; min-width: 0; }

            .cal-task-title {
                font-size: 12px;
                font-weight: 600;
                color: #1e293b;
                line-height: 1.3;
            }
            .cal-task-item.completed .cal-task-title {
                text-decoration: line-through;
                color: #94a3b8;
            }

            .cal-task-meta {
                display: flex;
                align-items: center;
                gap: 6px;
                margin-top: 6px;
                flex-wrap: wrap;
            }

            .cal-priority-badge {
                font-size: 10px;
                font-weight: 700;
                padding: 1px 6px;
                border-radius: 4px;
            }

            .cal-task-est {
                font-size: 10px;
                color: #94a3b8;
            }

            .cal-ai-badge {
                font-size: 9px;
                font-weight: 600;
                color: #7c3aed;
                background: #f5f3ff;
                padding: 2px 6px;
                border-radius: 4px;
                display: inline-flex;
                align-items: center;
                gap: 3px;
            }

            .cal-add-task-btn {
                margin: 8px 16px 16px;
                padding: 10px;
                background: transparent;
                border: 2px dashed #e2e8f0;
                border-radius: 10px;
                color: #94a3b8;
                font-size: 12px;
                font-weight: 600;
                cursor: pointer;
                font-family: inherit;
                transition: all 0.15s;
            }
            .cal-add-task-btn:hover { border-color: #cbd5e1; color: #64748b; background: #f8fafc; }

            /* Modal */
            .cal-modal-overlay {
                position: fixed; inset: 0;
                background: rgba(15,23,42,0.4);
                backdrop-filter: blur(4px);
                z-index: 9000;
                display: flex; align-items: center; justify-content: center;
                animation: calFadeIn 0.15s;
            }

            .cal-modal {
                background: #fff;
                border-radius: 14px;
                padding: 24px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.2);
                width: 420px;
                max-height: 90vh;
                overflow-y: auto;
                animation: calSlideUp 0.2s cubic-bezier(0.16, 1, 0.3, 1);
            }

            .cal-modal h3 {
                margin: 0 0 18px;
                font-size: 16px;
                font-weight: 700;
                color: #0f172a;
            }

            .cal-field {
                margin-bottom: 14px;
            }

            .cal-field label {
                display: block;
                font-size: 12px;
                font-weight: 600;
                color: #475569;
                margin-bottom: 4px;
            }

            .cal-field input, .cal-field select, .cal-field textarea {
                width: 100%;
                padding: 8px 12px;
                border: 1px solid #d1d5db;
                border-radius: 8px;
                font-size: 13px;
                outline: none;
                font-family: inherit;
                transition: border-color 0.15s;
            }
            .cal-field input:focus, .cal-field select:focus, .cal-field textarea:focus {
                border-color: #2563eb;
                box-shadow: 0 0 0 3px rgba(37,99,235,0.1);
            }

            .cal-field textarea { resize: vertical; }

            .cal-field-row {
                display: flex;
                gap: 10px;
            }
            .cal-field-row .cal-field { flex: 1; }

            .cal-submit-btn {
                width: 100%;
                padding: 10px;
                background: #2563eb;
                color: #fff;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 600;
                cursor: pointer;
                font-family: inherit;
                transition: background 0.15s;
                margin-top: 4px;
            }
            .cal-submit-btn:hover { background: #1d4ed8; }

            .cal-error-msg {
                display: none;
                margin-bottom: 10px;
                padding: 8px 12px;
                border-radius: 8px;
                background: #fef2f2;
                color: #dc2626;
                font-size: 12px;
            }

            /* Scrollbar */
            .cal-timeline-wrap::-webkit-scrollbar,
            .cal-tasks-list::-webkit-scrollbar,
            .cal-upcoming::-webkit-scrollbar {
                width: 5px;
            }
            .cal-timeline-wrap::-webkit-scrollbar-track,
            .cal-tasks-list::-webkit-scrollbar-track,
            .cal-upcoming::-webkit-scrollbar-track {
                background: transparent;
            }
            .cal-timeline-wrap::-webkit-scrollbar-thumb,
            .cal-tasks-list::-webkit-scrollbar-thumb,
            .cal-upcoming::-webkit-scrollbar-thumb {
                background: #e2e8f0;
                border-radius: 3px;
            }

            /* Event detail popup */
            .cal-event-popup {
                position: fixed;
                z-index: 9100;
                background: #fff;
                border-radius: 12px;
                padding: 18px;
                box-shadow: 0 12px 40px rgba(0,0,0,0.15);
                width: 300px;
                animation: calSlideUp 0.15s cubic-bezier(0.16, 1, 0.3, 1);
            }

            .cal-section-label {
                font-size: 11px;
                font-weight: 700;
                color: #94a3b8;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                margin: 16px 16px 8px;
            }
        `;
        document.head.appendChild(style);
    }

    // ── Show / Hide ─────────────────────────────
    window.showCalendarView = function() {
        hideAllViews();
        injectStyles();
        const now = new Date();
        _selectedDate = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        _miniYear = now.getFullYear();
        _miniMonth = now.getMonth();
        _container = document.getElementById('calendar-view');
        if (!_container) {
            _container = document.createElement('div');
            _container.id = 'calendar-view';
            Object.assign(_container.style, {
                position: 'fixed', inset: '0', zIndex: '8000',
                background: 'rgba(15,23,42,0.45)', backdropFilter: 'blur(6px)',
                display: 'none', alignItems: 'center', justifyContent: 'center'
            });
            document.body.appendChild(_container);
        }
        _container.style.display = 'flex';
        loadAndRender();
    };

    window.hideCalendarView = function() {
        if (_container) _container.style.display = 'none';
    };

    function hideAllViews() {
        if (window.hideRequestsView) hideRequestsView();
        if (window.hideCabinetView) hideCabinetView();
    }

    // ── Data Fetching ───────────────────────────
    async function fetchEvents() {
        const ds = formatDateISO(_selectedDate);
        const nextDay = new Date(_selectedDate);
        nextDay.setDate(nextDay.getDate() + 1);
        const de = formatDateISO(nextDay);
        try {
            const resp = await window.authFetch(`/api/monitoring/calendar/events?start=${ds}&end=${de}`);
            if (resp.ok) _events = await resp.json();
            else _events = [];
        } catch(e) { _events = []; }
    }

    async function fetchTasks() {
        const ds = formatDateISO(_selectedDate);
        try {
            const resp = await window.authFetch(`/api/monitoring/calendar/tasks?date=${ds}`);
            if (resp.ok) _tasks = await resp.json();
            else _tasks = [];
        } catch(e) { _tasks = []; }
    }

    async function fetchFocusBlocks() {
        try {
            const resp = await window.authFetch('/api/monitoring/calendar/focus-blocks');
            if (resp.ok) _focusBlocks = await resp.json();
            else _focusBlocks = [];
        } catch(e) { _focusBlocks = []; }
    }

    async function fetchMonthEvents(year, month) {
        const start = `${year}-${pad(month+1)}-01`;
        const dim = daysInMonth(year, month);
        const end = `${year}-${pad(month+1)}-${pad(dim)}`;
        try {
            const resp = await window.authFetch(`/api/monitoring/calendar/events?start=${start}&end=${end}`);
            if (resp.ok) return await resp.json();
        } catch(e) {}
        return [];
    }

    async function loadAndRender() {
        _container.innerHTML = '<div style="color:#fff;font-size:14px;font-family:Inter,sans-serif">Загрузка...</div>';
        await Promise.all([fetchEvents(), fetchTasks(), fetchFocusBlocks()]);
        render();
    }

    // ── Main Render ─────────────────────────────
    function render() {
        const panel = document.createElement('div');
        panel.className = 'cal-panel';

        // Left sidebar
        const left = document.createElement('div');
        left.className = 'cal-left';
        renderLeftSidebar(left);

        // Center
        const center = document.createElement('div');
        center.className = 'cal-center';
        renderCenter(center);

        // Right sidebar
        const right = document.createElement('div');
        right.className = 'cal-right';
        renderRightSidebar(right);

        panel.appendChild(left);
        panel.appendChild(center);
        panel.appendChild(right);

        _container.innerHTML = '';
        _container.appendChild(panel);

        // Close on backdrop click
        _container.addEventListener('click', function(e) {
            if (e.target === _container) hideCalendarView();
        });

        // Scroll to current hour
        setTimeout(function() {
            const tw = panel.querySelector('.cal-timeline-wrap');
            if (tw) {
                const now = new Date();
                const scrollTo = Math.max(0, (now.getHours() - HOUR_START - 1) * HOUR_HEIGHT);
                tw.scrollTop = scrollTo;
            }
        }, 50);
    }

    // ── Left Sidebar ────────────────────────────
    function renderLeftSidebar(left) {
        // Mini calendar header
        const header = document.createElement('div');
        header.className = 'cal-left-header';

        const nav = document.createElement('div');
        nav.className = 'cal-mini-nav';
        nav.innerHTML = `
            <button class="cal-mini-btn" data-action="mini-prev" aria-label="Предыдущий месяц">&#8249;</button>
            <span class="cal-mini-nav-title">${MONTHS_RU[_miniMonth]} ${_miniYear}</span>
            <button class="cal-mini-btn" data-action="mini-next" aria-label="Следующий месяц">&#8250;</button>
        `;

        nav.querySelector('[data-action="mini-prev"]').addEventListener('click', function() {
            _miniMonth--;
            if (_miniMonth < 0) { _miniMonth = 11; _miniYear--; }
            updateMiniCalendar(header);
        });
        nav.querySelector('[data-action="mini-next"]').addEventListener('click', function() {
            _miniMonth++;
            if (_miniMonth > 11) { _miniMonth = 0; _miniYear++; }
            updateMiniCalendar(header);
        });

        header.appendChild(nav);

        // Mini grid
        const grid = document.createElement('div');
        grid.className = 'cal-mini-grid';
        grid.id = 'cal-mini-grid';
        header.appendChild(grid);

        left.appendChild(header);

        renderMiniGrid(grid);

        // Upcoming events
        const upcoming = document.createElement('div');
        upcoming.className = 'cal-upcoming';

        const uTitle = document.createElement('div');
        uTitle.className = 'cal-upcoming-title';
        uTitle.textContent = 'События дня';
        upcoming.appendChild(uTitle);

        if (_events.length === 0) {
            const empty = document.createElement('div');
            empty.style.cssText = 'font-size:12px;color:#94a3b8;padding:8px 0;';
            empty.textContent = 'Нет событий на этот день';
            upcoming.appendChild(empty);
        } else {
            _events.forEach(function(ev) {
                const item = document.createElement('div');
                item.className = 'cal-upcoming-item';
                const evType = EVENT_TYPES[ev.event_type] || EVENT_TYPES.other;
                item.style.borderLeftColor = ev.color || evType.color;
                item.innerHTML = `
                    <div class="cal-upcoming-item-title">${esc(ev.title)}</div>
                    <div class="cal-upcoming-item-time">${formatTime(ev.starts_at)} - ${formatTime(ev.ends_at)}</div>
                `;
                item.addEventListener('click', function() { showEventDetail(ev); });
                upcoming.appendChild(item);
            });
        }

        // Focus blocks section
        if (_focusBlocks.length > 0) {
            const fbTitle = document.createElement('div');
            fbTitle.className = 'cal-upcoming-title';
            fbTitle.style.marginTop = '16px';
            fbTitle.textContent = 'Фокус-блоки';
            upcoming.appendChild(fbTitle);

            const dayOfWeek = _selectedDate.getDay();
            _focusBlocks.forEach(function(fb) {
                if (fb.day_of_week !== null && fb.day_of_week !== undefined && fb.day_of_week !== dayOfWeek && fb.recurring) return;
                const item = document.createElement('div');
                item.className = 'cal-upcoming-item';
                item.style.borderLeftColor = fb.color || '#3b82f6';
                item.innerHTML = `
                    <div class="cal-upcoming-item-title">${esc(fb.title)}</div>
                    <div class="cal-upcoming-item-time">${fb.start_time ? fb.start_time.substring(0,5) : ''} - ${fb.end_time ? fb.end_time.substring(0,5) : ''}</div>
                `;
                upcoming.appendChild(item);
            });
        }

        left.appendChild(upcoming);
    }

    function renderMiniGrid(grid) {
        grid.innerHTML = '';
        DAYS_SHORT.forEach(function(d) {
            const el = document.createElement('div');
            el.className = 'cal-mini-day-name';
            el.textContent = d;
            grid.appendChild(el);
        });

        const firstDay = new Date(_miniYear, _miniMonth, 1).getDay();
        const offset = (firstDay === 0 ? 6 : firstDay - 1);
        const total = daysInMonth(_miniYear, _miniMonth);
        const today = new Date();

        // Previous month padding
        const prevTotal = daysInMonth(_miniYear, _miniMonth - 1);
        for (let i = offset - 1; i >= 0; i--) {
            const el = document.createElement('div');
            el.className = 'cal-mini-day other-month';
            el.textContent = prevTotal - i;
            grid.appendChild(el);
        }

        for (let d = 1; d <= total; d++) {
            const el = document.createElement('div');
            el.className = 'cal-mini-day';
            el.setAttribute('role', 'button');
            el.setAttribute('tabindex', '0');

            const isToday = today.getFullYear() === _miniYear && today.getMonth() === _miniMonth && today.getDate() === d;
            const isSel = _selectedDate.getFullYear() === _miniYear && _selectedDate.getMonth() === _miniMonth && _selectedDate.getDate() === d;

            if (isToday) el.classList.add('today');
            if (isSel && !isToday) el.classList.add('selected');

            el.setAttribute('aria-selected', isSel ? 'true' : 'false');
            el.setAttribute('aria-label', `${d} ${MONTHS_RU_GEN[_miniMonth]} ${_miniYear}`);

            el.textContent = d;
            const dayNum = d;
            const selectDay = function() {
                _selectedDate = new Date(_miniYear, _miniMonth, dayNum);
                loadAndRender();
            };
            el.addEventListener('click', selectDay);
            el.addEventListener('keydown', function(e) {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    selectDay();
                }
            });
            grid.appendChild(el);
        }

        // Next month padding
        const rem = (offset + total) % 7;
        if (rem > 0) {
            for (let i = 1; i <= 7 - rem; i++) {
                const el = document.createElement('div');
                el.className = 'cal-mini-day other-month';
                el.textContent = i;
                grid.appendChild(el);
            }
        }
    }

    function updateMiniCalendar(header) {
        const navTitle = header.querySelector('.cal-mini-nav-title');
        navTitle.textContent = MONTHS_RU[_miniMonth] + ' ' + _miniYear;
        const grid = header.querySelector('#cal-mini-grid');
        renderMiniGrid(grid);
    }

    // ── Center (Day View) ───────────────────────
    function renderCenter(center) {
        // Header
        const header = document.createElement('div');
        header.className = 'cal-center-header';

        const dayNav = document.createElement('div');
        dayNav.className = 'cal-day-nav';

        const prevBtn = document.createElement('button');
        prevBtn.className = 'cal-nav-btn';
        prevBtn.setAttribute('aria-label', 'Предыдущий день');
        prevBtn.innerHTML = '&#8249;';
        prevBtn.addEventListener('click', function() { navigateDay(-1); });

        const nextBtn = document.createElement('button');
        nextBtn.className = 'cal-nav-btn';
        nextBtn.setAttribute('aria-label', 'Следующий день');
        nextBtn.innerHTML = '&#8250;';
        nextBtn.addEventListener('click', function() { navigateDay(1); });

        const todayBtn = document.createElement('button');
        todayBtn.className = 'cal-today-btn';
        todayBtn.textContent = 'Сегодня';
        todayBtn.addEventListener('click', function() {
            const now = new Date();
            _selectedDate = new Date(now.getFullYear(), now.getMonth(), now.getDate());
            _miniYear = now.getFullYear();
            _miniMonth = now.getMonth();
            loadAndRender();
        });

        const dayTitle = document.createElement('span');
        dayTitle.className = 'cal-day-title';
        dayTitle.textContent = _selectedDate.getDate() + ' ' + MONTHS_RU_GEN[_selectedDate.getMonth()];

        const daySubtitle = document.createElement('span');
        daySubtitle.className = 'cal-day-subtitle';
        daySubtitle.textContent = DAYS_FULL[_selectedDate.getDay()] + ', ' + _selectedDate.getFullYear();

        dayNav.appendChild(prevBtn);
        dayNav.appendChild(nextBtn);
        dayNav.appendChild(todayBtn);
        dayNav.appendChild(dayTitle);
        dayNav.appendChild(daySubtitle);

        const actions = document.createElement('div');
        actions.className = 'cal-header-actions';

        // Focus timer pill button
        const focusBtn = document.createElement('button');
        focusBtn.className = 'cal-focus-pill-btn';
        focusBtn.id = 'cal-focus-pill';
        focusBtn.setAttribute('aria-label', 'Открыть таймер фокуса Pomodoro');
        focusBtn.innerHTML = '⏱️ <span id="cal-focus-pill-text">' + formatTimerStr(FocusTimer.timeLeft) + '</span>';
        focusBtn.style.cssText = 'padding:6px 12px;border:1px solid #3b82f6;background:#eff6ff;color:#1d4ed8;border-radius:8px;font-size:12px;font-weight:600;cursor:pointer;display:flex;align-items:center;gap:6px;transition:all 0.15s;';
        focusBtn.addEventListener('click', function() {
            toggleFocusWidget();
        });

        const addEventBtn = document.createElement('button');
        addEventBtn.className = 'cal-add-btn';
        addEventBtn.innerHTML = '<span style="font-size:14px">+</span> Событие';
        addEventBtn.addEventListener('click', showAddEventForm);

        const closeBtn = document.createElement('button');
        closeBtn.className = 'cal-close-btn';
        closeBtn.setAttribute('aria-label', 'Закрыть календарь');
        closeBtn.innerHTML = '&times;';
        closeBtn.addEventListener('click', hideCalendarView);

        actions.appendChild(focusBtn);
        actions.appendChild(addEventBtn);
        actions.appendChild(closeBtn);

        header.appendChild(dayNav);
        header.appendChild(actions);
        center.appendChild(header);

        // Active Task Focus Banner
        if (TaskTracker.activeTaskId) {
            const activeTask = _tasks.find(t => t.id === TaskTracker.activeTaskId);
            if (activeTask) {
                const banner = document.createElement('div');
                banner.id = 'cal-active-task-banner';
                banner.style.cssText = 'padding:10px 24px;background:#1e293b;color:#fff;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #334155;';

                const leftInfo = document.createElement('div');
                leftInfo.style.cssText = 'display:flex;align-items:center;gap:12px;';

                const pulseDot = document.createElement('span');
                pulseDot.style.cssText = 'width:10px;height:10px;border-radius:50%;background:#10b981;box-shadow:0 0 8px #10b981;';

                const taskTitle = document.createElement('span');
                taskTitle.style.cssText = 'font-size:13px;font-weight:600;';
                taskTitle.textContent = activeTask.title;

                const timerVal = document.createElement('span');
                timerVal.id = 'cal-banner-timer';
                timerVal.style.cssText = 'font-size:12px;font-family:monospace;color:#94a3b8;background:#0f172a;padding:2px 8px;border-radius:4px;';
                timerVal.textContent = formatTimerStr(TaskTracker.elapsedSeconds);

                leftInfo.appendChild(pulseDot);
                leftInfo.appendChild(taskTitle);
                leftInfo.appendChild(timerVal);

                const rightControls = document.createElement('div');
                rightControls.style.cssText = 'display:flex;align-items:center;gap:8px;';

                const pauseBtn = document.createElement('button');
                pauseBtn.style.cssText = 'padding:4px 12px;border:1px solid #475569;background:#334155;color:#fff;border-radius:6px;font-size:12px;font-weight:600;cursor:pointer;';
                pauseBtn.textContent = '⏸ Пауза';
                pauseBtn.addEventListener('click', function() {
                    TaskTracker.stop();
                    loadAndRender();
                });

                const doneBtn = document.createElement('button');
                doneBtn.style.cssText = 'padding:4px 12px;border:none;background:#10b981;color:#fff;border-radius:6px;font-size:12px;font-weight:600;cursor:pointer;';
                doneBtn.textContent = '✓ Завершить';
                doneBtn.addEventListener('click', function() {
                    TaskTracker.stop();
                    toggleTask(activeTask.id, true);
                });

                rightControls.appendChild(pauseBtn);
                rightControls.appendChild(doneBtn);

                banner.appendChild(leftInfo);
                banner.appendChild(rightControls);
                center.appendChild(banner);
            }
        }

        // Timeline
        const timelineWrap = document.createElement('div');
        timelineWrap.className = 'cal-timeline-wrap';

        const timeline = document.createElement('div');
        timeline.className = 'cal-timeline';

        // Render focus blocks first (background)
        renderFocusBlocks(timeline);

        // Hour rows
        for (let h = HOUR_START; h < HOUR_END; h++) {
            const row = document.createElement('div');
            row.className = 'cal-hour-row';

            const label = document.createElement('div');
            label.className = 'cal-hour-label';
            label.textContent = pad(h) + ':00';

            const content = document.createElement('div');
            content.className = 'cal-hour-content';

            row.appendChild(label);
            row.appendChild(content);
            timeline.appendChild(row);
        }

        // Render event blocks
        renderEventBlocks(timeline);

        // Current time line
        const now = new Date();
        const isToday = sameDay(_selectedDate, now);
        if (isToday && now.getHours() >= HOUR_START && now.getHours() < HOUR_END) {
            const minutesSinceStart = (now.getHours() - HOUR_START) * 60 + now.getMinutes();
            const topPx = (minutesSinceStart / 60) * HOUR_HEIGHT;
            const nowLine = document.createElement('div');
            nowLine.className = 'cal-now-line';
            nowLine.style.top = topPx + 'px';
            timeline.appendChild(nowLine);
        }

        timelineWrap.appendChild(timeline);
        center.appendChild(timelineWrap);
    }

    function renderFocusBlocks(timeline) {
        const dayOfWeek = _selectedDate.getDay();
        _focusBlocks.forEach(function(fb) {
            if (fb.day_of_week !== null && fb.day_of_week !== undefined && fb.day_of_week !== dayOfWeek && fb.recurring) return;

            const startParts = (fb.start_time || '09:00').split(':');
            const endParts = (fb.end_time || '10:00').split(':');
            const startH = parseInt(startParts[0]);
            const startM = parseInt(startParts[1] || 0);
            const endH = parseInt(endParts[0]);
            const endM = parseInt(endParts[1] || 0);

            if (endH <= HOUR_START || startH >= HOUR_END) return;

            const topMinutes = Math.max(0, (startH - HOUR_START) * 60 + startM);
            const bottomMinutes = Math.min((HOUR_END - HOUR_START) * 60, (endH - HOUR_START) * 60 + endM);
            const top = (topMinutes / 60) * HOUR_HEIGHT;
            const height = ((bottomMinutes - topMinutes) / 60) * HOUR_HEIGHT;

            const block = document.createElement('div');
            block.className = 'cal-focus-block';
            block.style.top = top + 'px';
            block.style.height = height + 'px';
            block.style.background = fb.color || '#3b82f6';

            const label = document.createElement('div');
            label.className = 'cal-focus-label';
            label.style.top = top + 'px';
            label.style.color = fb.color || '#3b82f6';
            label.style.background = hexToRgba(fb.color || '#3b82f6', 0.12);
            label.textContent = fb.title;

            timeline.appendChild(block);
            timeline.appendChild(label);
        });
    }

    function renderEventBlocks(timeline) {
        _events.forEach(function(ev, idx) {
            const startDate = new Date(ev.starts_at);
            const endDate = new Date(ev.ends_at);

            let startH = startDate.getHours();
            let startM = startDate.getMinutes();
            let endH = endDate.getHours();
            let endM = endDate.getMinutes();

            if (endH <= HOUR_START && endM === 0) return;
            if (startH >= HOUR_END) return;

            const topMinutes = Math.max(0, (startH - HOUR_START) * 60 + startM);
            const bottomMinutes = Math.min((HOUR_END - HOUR_START) * 60, (endH - HOUR_START) * 60 + endM);
            const top = (topMinutes / 60) * HOUR_HEIGHT;
            const height = Math.max(24, ((bottomMinutes - topMinutes) / 60) * HOUR_HEIGHT);

            const evType = EVENT_TYPES[ev.event_type] || EVENT_TYPES.other;
            const color = ev.color || evType.color;

            const block = document.createElement('div');
            block.className = 'cal-event-block';
            block.style.top = top + 'px';
            block.style.height = height + 'px';
            block.style.background = hexToRgba(color, 0.08);
            block.style.borderLeftColor = color;

            // Slight offset for overlapping events
            if (idx > 0) {
                const prevEv = _events[idx - 1];
                const prevEnd = new Date(prevEv.ends_at);
                if (startDate < prevEnd) {
                    block.style.left = (68 + idx * 30) + 'px';
                }
            }

            block.innerHTML = `
                <div class="cal-event-block-title">${esc(ev.title)}</div>
                <div class="cal-event-block-time">${formatTime(ev.starts_at)} - ${formatTime(ev.ends_at)}</div>
            `;

            block.addEventListener('click', function(e) {
                e.stopPropagation();
                showEventDetail(ev);
            });

            timeline.appendChild(block);
        });
    }

    // ── Right Sidebar (Tasks) ───────────────────
    function renderRightSidebar(right) {
        const header = document.createElement('div');
        header.className = 'cal-right-header';

        const completedCount = _tasks.filter(function(t) { return t.completed; }).length;
        header.innerHTML = `
            <span class="cal-right-title">Задачи</span>
            <span class="cal-task-count">${completedCount}/${_tasks.length}</span>
        `;
        right.appendChild(header);

        // Priority filter tabs
        const tabs = document.createElement('div');
        tabs.style.cssText = 'display:flex;gap:4px;padding:10px 16px;border-bottom:1px solid #f1f5f9;';
        tabs.setAttribute('role', 'tablist');
        tabs.setAttribute('aria-label', 'Фильтр задач по приоритету');
        ['Все', 'P1', 'P2', 'P3'].forEach(function(tab) {
            const btn = document.createElement('button');
            btn.className = 'cal-priority-tab';
            btn.setAttribute('role', 'tab');
            btn.setAttribute('aria-selected', tab === 'Все' ? 'true' : 'false');
            btn.setAttribute('aria-label', tab === 'Все' ? 'Все приоритеты' : 'Приоритет ' + tab);
            btn.style.cssText = 'padding:4px 10px;border:1px solid #e2e8f0;background:#fff;border-radius:6px;font-size:11px;font-weight:600;cursor:pointer;font-family:inherit;color:#64748b;transition:all 0.15s;';
            btn.textContent = tab;
            if (tab === 'Все') {
                btn.style.background = '#0f172a';
                btn.style.color = '#fff';
                btn.style.borderColor = '#0f172a';
            }
            btn.addEventListener('click', function() {
                // Update active tab styles and aria-selected states
                tabs.querySelectorAll('button').forEach(function(b) {
                    b.style.background = '#fff';
                    b.style.color = '#64748b';
                    b.style.borderColor = '#e2e8f0';
                    b.setAttribute('aria-selected', 'false');
                });
                btn.style.background = '#0f172a';
                btn.style.color = '#fff';
                btn.style.borderColor = '#0f172a';
                btn.setAttribute('aria-selected', 'true');
                filterTasks(right, tab === 'Все' ? null : tab);
            });
            tabs.appendChild(btn);
        });
        right.appendChild(tabs);

        // Tasks list
        const list = document.createElement('div');
        list.className = 'cal-tasks-list';
        list.id = 'cal-tasks-list';
        renderTaskItems(list, _tasks);
        right.appendChild(list);

        // Add task button
        const addBtn = document.createElement('button');
        addBtn.className = 'cal-add-task-btn';
        addBtn.textContent = '+ Добавить задачу';
        addBtn.addEventListener('click', showAddTaskForm);
        right.appendChild(addBtn);
    }

    function renderTaskItems(list, tasks) {
        list.innerHTML = '';

        // Sort: incomplete first, then by priority
        const priorityOrder = { P1: 0, P2: 1, P3: 2 };
        const sorted = tasks.slice().sort(function(a, b) {
            if (a.completed !== b.completed) return a.completed ? 1 : -1;
            return (priorityOrder[a.priority] || 1) - (priorityOrder[b.priority] || 1);
        });

        if (sorted.length === 0) {
            list.innerHTML = '<div style="text-align:center;padding:24px;color:#94a3b8;font-size:12px;">Нет задач на этот день</div>';
            return;
        }

        sorted.forEach(function(task) {
            const item = document.createElement('div');
            item.className = 'cal-task-item' + (task.completed ? ' completed' : '');
            item.draggable = true;
            item.dataset.taskId = task.id;

            const p = PRIORITY_CONFIG[task.priority] || PRIORITY_CONFIG.P2;
            const aiSuggestion = getAISuggestion(task);
            const isTracking = TaskTracker.activeTaskId === task.id;
            const elapsedMins = Math.floor((TaskTracker.taskElapsed[task.id] || 0) / 60);
            const isOvertime = task.estimated_minutes && elapsedMins > task.estimated_minutes;
            const overtimeMins = isOvertime ? elapsedMins - task.estimated_minutes : 0;
            const parsed = parseShortSyntax(task.title);
            const tagBadges = (parsed.tags || []).map(function(t) { return '<span style="font-size:9px;font-weight:600;color:#2563eb;background:#eff6ff;padding:1px 5px;border-radius:4px;">#' + esc(t) + '</span>'; }).join(' ');

            item.innerHTML = `
                <div class="cal-task-top">
                    <span class="cal-task-drag">&#8942;&#8942;</span>
                    <div class="cal-task-checkbox ${task.completed ? 'checked' : ''}" data-task-id="${task.id}" role="checkbox" tabindex="0" aria-checked="${task.completed ? 'true' : 'false'}" aria-label="${task.completed ? 'Отметить задачу как невыполненную' : 'Отметить задачу как выполненную'}"></div>
                    <div class="cal-task-info">
                        <div class="cal-task-title">${esc(task.title)}</div>
                        <div class="cal-task-meta">
                            <span class="cal-priority-badge" style="color:${p.color};background:${p.bg}">${task.priority || 'P2'}</span>
                            ${task.estimated_minutes ? '<span class="cal-task-est">' + task.estimated_minutes + ' мин</span>' : ''}
                            <span class="cal-task-timer-badge ${isTracking ? 'active' : ''}">${isTracking ? '⏱️ ' + formatTimerStr(TaskTracker.elapsedSeconds) : (elapsedMins > 0 ? '⏱️ ' + elapsedMins + 'м' : '')}</span>
                            ${isOvertime ? '<span style="font-size:9px;font-weight:700;color:#dc2626;background:#fef2f2;padding:1px 5px;border-radius:4px;">⚠️ +' + overtimeMins + 'м</span>' : ''}
                            ${tagBadges}
                            ${aiSuggestion ? '<span class="cal-ai-badge">&#9733; ' + aiSuggestion + '</span>' : ''}
                        </div>
                    </div>
                    <button class="cal-task-track-btn ${isTracking ? 'tracking' : ''}" aria-label="${isTracking ? 'Остановить таймер' : 'Запустить таймер задачи'}">${isTracking ? '⏸' : '▶'}</button>
                </div>
            `;

            const trackBtn = item.querySelector('.cal-task-track-btn');
            trackBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                if (TaskTracker.activeTaskId === task.id) {
                    TaskTracker.stop();
                } else {
                    TaskTracker.start(task);
                }
                const list = document.getElementById('cal-tasks-list');
                if (list) renderTaskItems(list, _tasks);
            });

            // Toggle completion
            const checkbox = item.querySelector('.cal-task-checkbox');
            checkbox.addEventListener('click', function(e) {
                e.stopPropagation();
                toggleTask(task.id, !task.completed);
            });
            checkbox.addEventListener('keydown', function(e) {
                if (e.key === ' ' || e.key === 'Enter') {
                    e.preventDefault();
                    e.stopPropagation();
                    toggleTask(task.id, !task.completed);
                }
            });

            // Drag handlers
            item.addEventListener('dragstart', function(e) {
                item.classList.add('dragging');
                e.dataTransfer.setData('text/plain', task.id);
            });
            item.addEventListener('dragend', function() {
                item.classList.remove('dragging');
            });
            item.addEventListener('dragover', function(e) {
                e.preventDefault();
                const dragging = list.querySelector('.dragging');
                if (dragging && dragging !== item) {
                    const rect = item.getBoundingClientRect();
                    const mid = rect.top + rect.height / 2;
                    if (e.clientY < mid) {
                        list.insertBefore(dragging, item);
                    } else {
                        list.insertBefore(dragging, item.nextSibling);
                    }
                }
            });

            list.appendChild(item);
        });
    }

    function filterTasks(right, priority) {
        const list = right.querySelector('#cal-tasks-list');
        const filtered = priority ? _tasks.filter(function(t) { return t.priority === priority; }) : _tasks;
        renderTaskItems(list, filtered);
    }

    function getAISuggestion(task) {
        if (task.completed) return null;
        const title = (task.title || '').toLowerCase();
        if (title.includes('отчёт') || title.includes('отчет') || title.includes('анализ') || title.includes('подготовка')) {
            return 'Рекомендуемое время: 10:00-12:00';
        }
        if (title.includes('проверк') || title.includes('калибровк') || title.includes('замена') || title.includes('осмотр')) {
            return 'Рекомендуемое время: 08:00-10:00';
        }
        if (title.includes('совещани') || title.includes('обсужд') || title.includes('согласован')) {
            return 'Рекомендуемое время: 14:00-15:00';
        }
        if (task.priority === 'P1') {
            return 'Рекомендуемое время: 09:00-11:00';
        }
        return null;
    }

    async function toggleTask(taskId, completed) {
        try {
            const resp = await window.authFetch(`/api/monitoring/calendar/tasks/${taskId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ completed: completed })
            });
            if (resp.ok) loadAndRender();
        } catch(e) { console.error('Toggle task error:', e); }
    }

    // ── Navigation ──────────────────────────────
    function navigateDay(offset) {
        _selectedDate.setDate(_selectedDate.getDate() + offset);
        _miniYear = _selectedDate.getFullYear();
        _miniMonth = _selectedDate.getMonth();
        loadAndRender();
    }

    // ── Event Detail Popup ──────────────────────
    function showEventDetail(ev) {
        removePopups();
        const popup = document.createElement('div');
        popup.className = 'cal-modal-overlay';
        popup.id = 'cal-event-popup-overlay';

        const evType = EVENT_TYPES[ev.event_type] || EVENT_TYPES.other;
        const color = ev.color || evType.color;

        popup.innerHTML = `
            <div class="cal-modal" style="width:380px;">
                <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:16px;">
                    <div>
                        <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
                            <div style="width:10px;height:10px;border-radius:50%;background:${color};"></div>
                            <span style="font-size:11px;font-weight:600;color:${color};">${evType.label}</span>
                        </div>
                        <h3 style="margin:0;font-size:16px;font-weight:700;color:#0f172a;">${esc(ev.title)}</h3>
                    </div>
                    <button class="cal-close-btn" id="cal-popup-close" aria-label="Закрыть">&times;</button>
                </div>
                <div style="display:flex;flex-direction:column;gap:10px;">
                    <div style="display:flex;align-items:center;gap:8px;font-size:13px;color:#475569;">
                        <span style="color:#94a3b8;">&#128337;</span>
                        ${formatTime(ev.starts_at)} - ${formatTime(ev.ends_at)}
                    </div>
                    ${ev.description ? '<div style="font-size:13px;color:#475569;background:#f8fafc;padding:10px 12px;border-radius:8px;">' + esc(ev.description) + '</div>' : ''}
                </div>
            </div>
        `;

        document.body.appendChild(popup);
        popup.querySelector('#cal-popup-close').addEventListener('click', function() { popup.remove(); });
        popup.addEventListener('click', function(e) { if (e.target === popup) popup.remove(); });
    }

    // ── Add Event Form ──────────────────────────
    function showAddEventForm() {
        removePopups();
        const overlay = document.createElement('div');
        overlay.className = 'cal-modal-overlay';
        overlay.id = 'cal-event-form-overlay';
        overlay.setAttribute('role', 'dialog');
        overlay.setAttribute('aria-modal', 'true');
        overlay.setAttribute('aria-label', 'Новое событие');
        overlay.setAttribute('tabindex', '-1');

        let typeOptions = '';
        Object.keys(EVENT_TYPES).forEach(function(k) {
            typeOptions += '<option value="' + k + '">' + EVENT_TYPES[k].label + '</option>';
        });

        const ds = formatDateISO(_selectedDate);

        overlay.innerHTML = `
            <div class="cal-modal">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:18px;">
                    <h3 style="margin:0;">Новое событие</h3>
                    <button class="cal-close-btn" id="cal-ef-close" aria-label="Закрыть">&times;</button>
                </div>
                <div class="cal-field">
                    <label>Название</label>
                    <input id="cal-ef-title" type="text" placeholder="Введите название" />
                </div>
                <div class="cal-field">
                    <label>Тип события</label>
                    <select id="cal-ef-type">${typeOptions}</select>
                </div>
                <div class="cal-field-row">
                    <div class="cal-field">
                        <label>Начало</label>
                        <input id="cal-ef-start" type="datetime-local" value="${ds}T09:00" />
                    </div>
                    <div class="cal-field">
                        <label>Окончание</label>
                        <input id="cal-ef-end" type="datetime-local" value="${ds}T10:00" />
                    </div>
                </div>
                <div class="cal-field">
                    <label>Описание</label>
                    <textarea id="cal-ef-desc" rows="3" placeholder="Описание (необязательно)"></textarea>
                </div>
                <div class="cal-error-msg" id="cal-ef-error"></div>
                <button class="cal-submit-btn" id="cal-ef-submit">Сохранить</button>
            </div>
        `;

        document.body.appendChild(overlay);
        const titleInput = overlay.querySelector('#cal-ef-title');
        if (titleInput) titleInput.focus();

        overlay.querySelector('#cal-ef-close').addEventListener('click', function() { overlay.remove(); });
        overlay.addEventListener('click', function(e) { if (e.target === overlay) overlay.remove(); });

        const submitBtn = overlay.querySelector('#cal-ef-submit');
        submitBtn.addEventListener('click', async function() {
            const errEl = overlay.querySelector('#cal-ef-error');
            errEl.style.display = 'none';
            const title = overlay.querySelector('#cal-ef-title').value.trim();
            const type = overlay.querySelector('#cal-ef-type').value;
            const startVal = overlay.querySelector('#cal-ef-start').value;
            const endVal = overlay.querySelector('#cal-ef-end').value;
            const desc = overlay.querySelector('#cal-ef-desc').value.trim();

            if (!title || !startVal || !endVal) {
                errEl.textContent = 'Заполните все обязательные поля';
                errEl.style.display = 'block';
                return;
            }

            try {
                submitBtn.disabled = true;
                submitBtn.textContent = 'Сохранение...';
                const resp = await window.authFetch('/api/monitoring/calendar/events', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        title: title,
                        event_type: type,
                        starts_at: new Date(startVal).toISOString(),
                        ends_at: new Date(endVal).toISOString(),
                        description: desc,
                        all_day: false,
                        color: EVENT_TYPES[type] ? EVENT_TYPES[type].color : null
                    })
                });
                if (!resp.ok) throw new Error('Ошибка сохранения');
                overlay.remove();
                loadAndRender();
            } catch(e) {
                submitBtn.disabled = false;
                submitBtn.textContent = 'Сохранить';
                errEl.textContent = e.message;
                errEl.style.display = 'block';
            }
        });
    }

    // ── Add Task Form ───────────────────────────
    function showAddTaskForm() {
        removePopups();
        const overlay = document.createElement('div');
        overlay.className = 'cal-modal-overlay';
        overlay.id = 'cal-task-form-overlay';
        overlay.setAttribute('role', 'dialog');
        overlay.setAttribute('aria-modal', 'true');
        overlay.setAttribute('aria-label', 'Новая задача');
        overlay.setAttribute('tabindex', '-1');

        const ds = formatDateISO(_selectedDate);

        overlay.innerHTML = `
            <div class="cal-modal">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:18px;">
                    <h3 style="margin:0;">Новая задача</h3>
                    <button class="cal-close-btn" id="cal-tf-close" aria-label="Закрыть">&times;</button>
                </div>
                <div class="cal-field">
                    <label>Название</label>
                    <input id="cal-tf-title" type="text" placeholder="Что нужно сделать? (поддерживает !P1, @30m, #тег)" />
                    <div id="cal-tf-preview" style="font-size:11px;color:#64748b;margin-top:4px;display:none;padding:4px 8px;background:#f8fafc;border-radius:6px;border:1px solid #e2e8f0;"></div>
                </div>
                <div class="cal-field-row">
                    <div class="cal-field">
                        <label>Приоритет</label>
                        <select id="cal-tf-priority">
                            <option value="P1">P1 — Критичный</option>
                            <option value="P2" selected>P2 — Обычный</option>
                            <option value="P3">P3 — Низкий</option>
                        </select>
                    </div>
                    <div class="cal-field">
                        <label>Оценка (мин)</label>
                        <div style="display:flex;gap:4px;align-items:center;">
                            <input id="cal-tf-est" type="number" min="5" step="5" value="30" style="flex:1;" />
                            <button type="button" class="cal-est-preset" data-mins="15" aria-label="Установить оценку 15 минут" style="padding:6px 8px;border:1px solid #d1d5db;background:#f8fafc;border-radius:6px;font-size:11px;font-weight:600;cursor:pointer;color:#475569;">15m</button>
                            <button type="button" class="cal-est-preset" data-mins="30" aria-label="Установить оценку 30 минут" style="padding:6px 8px;border:1px solid #d1d5db;background:#f8fafc;border-radius:6px;font-size:11px;font-weight:600;cursor:pointer;color:#475569;">30m</button>
                            <button type="button" class="cal-est-preset" data-mins="60" aria-label="Установить оценку 60 минут" style="padding:6px 8px;border:1px solid #d1d5db;background:#f8fafc;border-radius:6px;font-size:11px;font-weight:600;cursor:pointer;color:#475569;">60m</button>
                        </div>
                    </div>
                </div>
                <div class="cal-field">
                    <label>Дата</label>
                    <input id="cal-tf-date" type="date" value="${ds}" />
                </div>
                <div class="cal-field">
                    <label>Описание</label>
                    <textarea id="cal-tf-desc" rows="2" placeholder="Дополнительные детали (необязательно)"></textarea>
                </div>
                <div class="cal-error-msg" id="cal-tf-error"></div>
                <button class="cal-submit-btn" id="cal-tf-submit">Добавить задачу</button>
            </div>
        `;

        document.body.appendChild(overlay);
        const titleInput = overlay.querySelector('#cal-tf-title');
        const prioritySelect = overlay.querySelector('#cal-tf-priority');
        const estInput = overlay.querySelector('#cal-tf-est');

        if (titleInput) {
            titleInput.focus();
            const previewEl = overlay.querySelector('#cal-tf-preview');
            titleInput.addEventListener('input', function() {
                const parsed = parseShortSyntax(titleInput.value);
                if (parsed.priority) prioritySelect.value = parsed.priority;
                if (parsed.estimatedMinutes) estInput.value = parsed.estimatedMinutes;

                if (previewEl) {
                    if (parsed.priority || parsed.estimatedMinutes || (parsed.tags && parsed.tags.length > 0)) {
                        let parts = [];
                        if (parsed.cleanTitle) parts.push(`<strong>Заголовок:</strong> ${esc(parsed.cleanTitle)}`);
                        if (parsed.priority) parts.push(`<strong>Приоритет:</strong> ${parsed.priority}`);
                        if (parsed.estimatedMinutes) parts.push(`<strong>Оценка:</strong> ${parsed.estimatedMinutes}m`);
                        if (parsed.tags && parsed.tags.length) parts.push(`<strong>Теги:</strong> ${parsed.tags.map(t => '#' + esc(t)).join(', ')}`);
                        previewEl.innerHTML = parts.join(' • ');
                        previewEl.style.display = 'block';
                    } else {
                        previewEl.style.display = 'none';
                    }
                }
            });
        }

        overlay.querySelectorAll('.cal-est-preset').forEach(function(btn) {
            btn.addEventListener('click', function() {
                const mins = btn.getAttribute('data-mins');
                if (estInput) {
                    estInput.value = mins;
                    estInput.dispatchEvent(new Event('input'));
                }
            });
        });

        overlay.querySelector('#cal-tf-close').addEventListener('click', function() { overlay.remove(); });
        overlay.addEventListener('click', function(e) { if (e.target === overlay) overlay.remove(); });

        const submitBtn = overlay.querySelector('#cal-tf-submit');
        submitBtn.addEventListener('click', async function() {
            const errEl = overlay.querySelector('#cal-tf-error');
            errEl.style.display = 'none';
            const rawTitle = overlay.querySelector('#cal-tf-title').value.trim();
            const parsed = parseShortSyntax(rawTitle);
            const title = parsed.cleanTitle || rawTitle;
            const priority = parsed.priority || overlay.querySelector('#cal-tf-priority').value;
            const est = parsed.estimatedMinutes || parseInt(overlay.querySelector('#cal-tf-est').value) || null;
            const date = overlay.querySelector('#cal-tf-date').value;
            const desc = overlay.querySelector('#cal-tf-desc').value.trim();

            if (!title) {
                errEl.textContent = 'Введите название задачи';
                errEl.style.display = 'block';
                return;
            }

            try {
                submitBtn.disabled = true;
                submitBtn.textContent = 'Сохранение...';
                const resp = await window.authFetch('/api/monitoring/calendar/tasks', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        title: title,
                        priority: priority,
                        estimated_minutes: est,
                        due_date: date ? date + 'T00:00:00Z' : null,
                        description: desc || null
                    })
                });
                if (!resp.ok) throw new Error('Ошибка сохранения');
                overlay.remove();
                loadAndRender();
            } catch(e) {
                submitBtn.disabled = false;
                submitBtn.textContent = 'Добавить задачу';
                errEl.textContent = e.message;
                errEl.style.display = 'block';
            }
        });
    }

    // ── Super Productivity Short Syntax & Focus Timer Logic ─────
    function parseShortSyntax(rawText) {
        let text = rawText || '';
        let priority = null;
        let estimatedMinutes = null;
        const tags = [];

        const pMatch = text.match(/!(P1|P2|P3|high|med|low)/i);
        if (pMatch) {
            const pVal = pMatch[1].toUpperCase();
            if (pVal === 'HIGH') priority = 'P1';
            else if (pVal === 'MED') priority = 'P2';
            else if (pVal === 'LOW') priority = 'P3';
            else priority = pVal;
            text = text.replace(pMatch[0], '');
        }

        const tMatch = text.match(/@(\d+)(h|m)?/i);
        if (tMatch) {
            const val = parseInt(tMatch[1], 10);
            const unit = (tMatch[2] || 'm').toLowerCase();
            if (unit === 'h') estimatedMinutes = val * 60;
            else estimatedMinutes = val;
            text = text.replace(tMatch[0], '');
        }

        const tagMatches = text.match(/#([\wа-яА-Я0-9_-]+)/gi);
        if (tagMatches) {
            tagMatches.forEach(function(t) {
                tags.push(t.substring(1));
                text = text.replace(t, '');
            });
        }

        return {
            cleanTitle: text.replace(/\s+/g, ' ').trim(),
            priority: priority,
            estimatedMinutes: estimatedMinutes,
            tags: tags
        };
    }

    // Focus Session / Pomodoro Timer state
    const FocusTimer = {
        mode: 'work', // 'work' | 'break'
        timeLeft: 1500, // 25 min default
        totalTime: 1500,
        sessionsCompleted: 0,
        isRunning: false,
        intervalId: null,

        start: function() {
            if (this.isRunning) return;
            this.isRunning = true;
            const self = this;
            this.intervalId = setInterval(function() {
                if (self.timeLeft > 0) {
                    self.timeLeft--;
                    self.updatePillText();
                    self.updateWidgetUI();
                } else {
                    self.onExpire();
                }
            }, 1000);
            this.updatePillText();
            this.updateWidgetUI();
        },

        pause: function() {
            this.isRunning = false;
            if (this.intervalId) {
                clearInterval(this.intervalId);
                this.intervalId = null;
            }
            this.updatePillText();
            this.updateWidgetUI();
        },

        toggle: function() {
            if (this.isRunning) this.pause();
            else this.start();
        },

        reset: function(newMode) {
            this.pause();
            if (newMode) this.mode = newMode;
            if (this.mode === 'work') {
                this.timeLeft = 1500;
                this.totalTime = 1500;
            } else {
                this.timeLeft = 300;
                this.totalTime = 300;
            }
            this.updatePillText();
            this.updateWidgetUI();
        },

        onExpire: function() {
            this.pause();
            playChimeSound();
            if (this.mode === 'work') {
                this.sessionsCompleted++;
                const isLongBreak = this.sessionsCompleted % 4 === 0;
                alert('⏱️ Время фокуса истекло! (Сессия ' + this.sessionsCompleted + ')\nВремя сделать ' + (isLongBreak ? '15-минутный длинный' : '5-минутный') + ' перерыв.');
                this.reset('break');
                if (isLongBreak) {
                    this.timeLeft = 900;
                    this.totalTime = 900;
                    this.updatePillText();
                    this.updateWidgetUI();
                }
            } else {
                alert('⏱️ Перерыв окончен! Готовы продолжить фокус-сессию?');
                this.reset('work');
            }
        },

        updatePillText: function() {
            const el = document.getElementById('cal-focus-pill-text');
            if (el) {
                el.textContent = (this.mode === 'work' ? 'Фокус: ' : 'Перерыв: ') + formatTimerStr(this.timeLeft);
            }
        },

        updateWidgetUI: function() {
            const modal = document.getElementById('focus-timer-modal');
            if (!modal) return;
            const timerVal = modal.querySelector('#focus-timer-val');
            const modeLbl = modal.querySelector('#focus-timer-mode');
            const playBtn = modal.querySelector('#focus-timer-play');
            const progressBar = modal.querySelector('#focus-timer-progress');

            if (timerVal) timerVal.textContent = formatTimerStr(this.timeLeft);
            if (modeLbl) modeLbl.textContent = (this.mode === 'work' ? 'Сессия фокуса (25 мин)' : 'Перерыв (5 мин)') + ' • Завершено сессий: ' + this.sessionsCompleted;
            if (playBtn) playBtn.textContent = this.isRunning ? 'Пауза' : 'Старт';
            if (progressBar && this.totalTime > 0) {
                const pct = Math.max(0, Math.min(100, ((this.totalTime - this.timeLeft) / this.totalTime) * 100));
                progressBar.style.width = pct + '%';
            }
        }
    };

    // Per-Task Time Tracker state
    const TaskTracker = {
        activeTaskId: null,
        elapsedSeconds: 0,
        taskElapsed: {},
        intervalId: null,

        start: function(task) {
            if (this.activeTaskId === task.id) return;
            this.stop();
            this.activeTaskId = task.id;
            this.elapsedSeconds = this.taskElapsed[task.id] || 0;
            const self = this;
            this.intervalId = setInterval(function() {
                self.elapsedSeconds++;
                self.taskElapsed[task.id] = self.elapsedSeconds;
                const badge = document.querySelector(`.cal-task-item[data-task-id="${task.id}"] .cal-task-timer-badge`);
                if (badge) {
                    badge.classList.add('active');
                    badge.textContent = '⏱️ ' + formatTimerStr(self.elapsedSeconds);
                }
                const bannerTimer = document.getElementById('cal-banner-timer');
                if (bannerTimer) {
                    bannerTimer.textContent = formatTimerStr(self.elapsedSeconds);
                }
            }, 1000);
        },

        stop: function() {
            if (this.intervalId) {
                clearInterval(this.intervalId);
                this.intervalId = null;
            }
            if (this.activeTaskId) {
                this.taskElapsed[this.activeTaskId] = this.elapsedSeconds;
            }
            this.activeTaskId = null;
        }
    };

    function playChimeSound() {
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = 'sine';
            osc.frequency.setValueAtTime(587.33, ctx.currentTime); // D5
            osc.frequency.exponentialRampToValueAtTime(880, ctx.currentTime + 0.3); // A5
            gain.gain.setValueAtTime(0.15, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.5);
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start();
            osc.stop(ctx.currentTime + 0.5);
        } catch(e) {}
    }

    function toggleFocusWidget() {
        let modal = document.getElementById('focus-timer-modal');
        if (modal) {
            modal.remove();
            return;
        }

        modal = document.createElement('div');
        modal.id = 'focus-timer-modal';
        modal.className = 'cal-modal-overlay';
        modal.setAttribute('role', 'dialog');
        modal.setAttribute('aria-modal', 'true');
        modal.setAttribute('aria-label', 'Таймер фокуса');

        modal.innerHTML = `
            <div class="cal-modal" style="width:340px;text-align:center;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
                    <h3 style="margin:0;font-size:16px;">⏱️ Режим Фокуса (Pomodoro)</h3>
                    <button class="cal-close-btn" id="focus-timer-close" aria-label="Закрыть">&times;</button>
                </div>
                <div id="focus-timer-mode" style="font-size:13px;color:#64748b;margin-bottom:12px;font-weight:500;">
                    ${FocusTimer.mode === 'work' ? 'Сессия фокуса (25 мин)' : 'Перерыв (5 мин)'}
                </div>
                <div id="focus-timer-val" style="font-size:42px;font-weight:700;font-family:monospace;color:#0f172a;margin:12px 0;">
                    ${formatTimerStr(FocusTimer.timeLeft)}
                </div>
                <div style="width:100%;height:6px;background:#e2e8f0;border-radius:3px;overflow:hidden;margin-bottom:18px;">
                    <div id="focus-timer-progress" style="height:100%;background:#3b82f6;width:${Math.max(0, Math.min(100, ((FocusTimer.totalTime - FocusTimer.timeLeft) / FocusTimer.totalTime) * 100))}%;transition:width 0.3s;"></div>
                </div>
                <div style="display:flex;justify-content:center;gap:10px;margin-bottom:16px;">
                    <button class="cal-submit-btn" id="focus-timer-play" style="padding:8px 20px;">${FocusTimer.isRunning ? 'Пауза' : 'Старт'}</button>
                    <button class="cal-today-btn" id="focus-timer-reset" style="padding:8px 14px;">Сброс</button>
                </div>
                <div style="display:flex;justify-content:center;gap:8px;font-size:12px;">
                    <button id="focus-mode-work" style="padding:4px 10px;border-radius:6px;border:1px solid #cbd5e1;background:${FocusTimer.mode === 'work' ? '#3b82f6' : '#fff'};color:${FocusTimer.mode === 'work' ? '#fff' : '#64748b'};cursor:pointer;">25м Фокус</button>
                    <button id="focus-mode-break" style="padding:4px 10px;border-radius:6px;border:1px solid #cbd5e1;background:${FocusTimer.mode === 'break' ? '#3b82f6' : '#fff'};color:${FocusTimer.mode === 'break' ? '#fff' : '#64748b'};cursor:pointer;">5м Перерыв</button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        modal.querySelector('#focus-timer-close').addEventListener('click', function() { modal.remove(); });
        modal.addEventListener('click', function(e) { if (e.target === modal) modal.remove(); });

        modal.querySelector('#focus-timer-play').addEventListener('click', function() {
            FocusTimer.toggle();
        });
        modal.querySelector('#focus-timer-reset').addEventListener('click', function() {
            FocusTimer.reset();
        });
        modal.querySelector('#focus-mode-work').addEventListener('click', function() {
            FocusTimer.reset('work');
        });
        modal.querySelector('#focus-mode-break').addEventListener('click', function() {
            FocusTimer.reset('break');
        });
    }

    function formatTimerStr(seconds) {
        const m = Math.floor(seconds / 60);
        const s = seconds % 60;
        return pad(m) + ':' + pad(s);
    }

    // Expose globals for Omni-bar & app integration
    window.focusTimer = FocusTimer;
    window.parseShortSyntax = parseShortSyntax;
    window.toggleFocusWidget = toggleFocusWidget;

    // ── Helpers ──────────────────────────────────
    function pad(n) { return n < 10 ? '0' + n : '' + n; }
    function daysInMonth(y, m) { return new Date(y, m + 1, 0).getDate(); }
    function esc(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

    function formatDateISO(d) {
        return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate());
    }

    function formatTime(isoStr) {
        if (!isoStr) return '';
        const d = new Date(isoStr);
        return pad(d.getHours()) + ':' + pad(d.getMinutes());
    }

    function sameDay(a, b) {
        return a.getFullYear() === b.getFullYear() &&
               a.getMonth() === b.getMonth() &&
               a.getDate() === b.getDate();
    }

    function hexToRgba(hex, alpha) {
        if (!hex || hex.length < 7) return 'rgba(59,130,246,' + alpha + ')';
        const r = parseInt(hex.slice(1,3), 16);
        const g = parseInt(hex.slice(3,5), 16);
        const b = parseInt(hex.slice(5,7), 16);
        return 'rgba(' + r + ',' + g + ',' + b + ',' + alpha + ')';
    }

    function removePopups() {
        ['cal-event-popup-overlay', 'cal-event-form-overlay', 'cal-task-form-overlay'].forEach(function(id) {
            const el = document.getElementById(id);
            if (el) el.remove();
        });
    }
})();
