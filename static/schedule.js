/* schedule.js — График дежурств */
(function () {
  const API = '/api/monitoring/schedule';
  let _stations = [], _personnel = [], _schedule = [];
  let _weekOffset = 0;
  const _userRole = () => (window._currentUser || {}).role || '';

  function hdr() {
    const t = localStorage.getItem('access_token');
    return t ? { 'Authorization': 'Bearer ' + t, 'Content-Type': 'application/json' } : {};
  }

  function weekDates(offset) {
    const now = new Date();
    const monday = new Date(now);
    monday.setDate(now.getDate() - now.getDay() + 1 + offset * 7);
    monday.setHours(0, 0, 0, 0);
    const days = [];
    for (let i = 0; i < 7; i++) {
      const d = new Date(monday);
      d.setDate(monday.getDate() + i);
      days.push(d);
    }
    return days;
  }

  function fmtDate(d) {
    return d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' });
  }
  function fmtDow(d) {
    return d.toLocaleDateString('ru-RU', { weekday: 'short' });
  }
  function isoDate(d) {
    return d.toISOString().slice(0, 10);
  }
  function fmtTime(s) {
    if (!s) return '';
    const d = new Date(s);
    const h = String(d.getUTCHours()).padStart(2, '0');
    const m = String(d.getUTCMinutes()).padStart(2, '0');
    return h + ':' + m;
  }

  async function loadData() {
    const days = weekDates(_weekOffset);
    const from = days[0].toISOString();
    const to = new Date(days[6].getTime() + 86400000).toISOString();
    const [schedRes, stRes, persRes] = await Promise.all([
      fetch(API + '?date_from=' + encodeURIComponent(from) + '&date_to=' + encodeURIComponent(to), { headers: hdr() }),
      fetch(API + '/stations', { headers: hdr() }),
      fetch(API + '/personnel', { headers: hdr() }),
    ]);
    if (schedRes.ok) _schedule = await schedRes.json();
    if (stRes.ok) _stations = await stRes.json();
    if (persRes.ok) _personnel = await persRes.json();
  }

  function render() {
    const el = document.getElementById('schedule-view');
    if (!el) return;
    const days = weekDates(_weekOffset);
    const isSupervisor = _userRole() === 'supervisor';

    const monthLabel = days[0].toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' });
    const weekRange = fmtDate(days[0]) + ' — ' + fmtDate(days[6]);

    // Group schedule by station
    const byStation = {};
    _stations.forEach(s => { byStation[s.code] = { station: s, days: {} }; });
    _schedule.forEach(a => {
      const code = a.station_code;
      if (!byStation[code]) return;
      // Assign to each day it covers
      days.forEach(d => {
        const dayStr = isoDate(d);
        const start = new Date(a.shift_start);
        const end = new Date(a.shift_end);
        if (start <= new Date(d.getTime() + 86400000) && end >= d) {
          if (!byStation[code].days[dayStr]) byStation[code].days[dayStr] = [];
          byStation[code].days[dayStr].push(a);
        }
      });
    });

    let html = `
    <div style="max-width:1200px;margin:24px auto;padding:0 16px">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px;flex-wrap:wrap;gap:12px">
        <h2 style="margin:0;font-size:20px;font-weight:600;color:#1a1a2e">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#0066cc" stroke-width="2" style="vertical-align:middle;margin-right:6px">
            <rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>
          </svg>
          График дежурств
        </h2>
        <div style="display:flex;align-items:center;gap:8px">
          <button onclick="window._schedPrev()" style="padding:6px 12px;border:1px solid #d1d5db;border-radius:6px;background:#fff;cursor:pointer;font-size:14px">&larr;</button>
          <span style="font-size:14px;font-weight:500;min-width:180px;text-align:center">${weekRange} &middot; ${monthLabel}</span>
          <button onclick="window._schedNext()" style="padding:6px 12px;border:1px solid #d1d5db;border-radius:6px;background:#fff;cursor:pointer;font-size:14px">&rarr;</button>
          <button onclick="window._schedToday()" style="padding:6px 12px;border:1px solid #0066cc;border-radius:6px;background:#0066cc;color:#fff;cursor:pointer;font-size:14px">Сегодня</button>
        </div>
      </div>`;

    if (isSupervisor) {
      html += `
      <div style="margin-bottom:16px">
        <button onclick="window._schedAddModal()" style="padding:8px 16px;border:none;border-radius:6px;background:#10b981;color:#fff;cursor:pointer;font-size:13px;font-weight:500">
          + Назначить дежурство
        </button>
      </div>`;
    }

    // Table
    const today = isoDate(new Date());
    html += `<div style="overflow-x:auto;border:1px solid #e5e7eb;border-radius:8px">
    <table style="width:100%;border-collapse:collapse;font-size:13px">
      <thead>
        <tr style="background:#f8fafc">
          <th style="padding:10px 12px;text-align:left;border-bottom:2px solid #e5e7eb;min-width:140px;position:sticky;left:0;background:#f8fafc;z-index:1">Станция</th>`;
    days.forEach(d => {
      const isToday = isoDate(d) === today;
      const bg = isToday ? 'background:#eff6ff;' : '';
      html += `<th style="padding:10px 8px;text-align:center;border-bottom:2px solid #e5e7eb;min-width:130px;${bg}">
        <div style="font-weight:600;${isToday ? 'color:#0066cc;' : ''}">${fmtDow(d)}</div>
        <div style="font-weight:400;font-size:12px;color:#6b7280">${fmtDate(d)}</div>
      </th>`;
    });
    html += `</tr></thead><tbody>`;

    const stationCodes = Object.keys(byStation).sort();
    if (stationCodes.length === 0) {
      html += `<tr><td colspan="${days.length + 1}" style="padding:40px;text-align:center;color:#9ca3af">Нет данных о станциях</td></tr>`;
    }
    stationCodes.forEach(code => {
      const entry = byStation[code];
      html += `<tr>
        <td style="padding:8px 12px;border-bottom:1px solid #f0f0f0;font-weight:500;position:sticky;left:0;background:#fff;z-index:1">
          <div>${entry.station.name}</div>
          <div style="font-size:11px;color:#9ca3af">${code}</div>
        </td>`;
      days.forEach(d => {
        const dayStr = isoDate(d);
        const isToday = dayStr === today;
        const bg = isToday ? 'background:#f0f7ff;' : '';
        const assignments = entry.days[dayStr] || [];
        let cellHtml = '';
        if (assignments.length > 0) {
          // Deduplicate by assignment id
          const seen = new Set();
          assignments.forEach(a => {
            if (seen.has(a.id)) return;
            seen.add(a.id);
            const colors = {
              'Наблюдатель': '#dbeafe;color:#1e40af',
              'Инженер-метеоролог': '#d1fae5;color:#065f46',
              'Техник': '#fef3c7;color:#92400e',
              'Старший наблюдатель': '#ede9fe;color:#5b21b6',
            };
            const style = colors[a.role_on_duty] || colors[a.position] || '#f3f4f6;color:#374151';
            cellHtml += `<div style="background:${style};padding:4px 6px;border-radius:4px;margin:2px 0;font-size:12px;line-height:1.3" title="${a.role_on_duty || a.position || ''}\n${fmtTime(a.shift_start)} — ${fmtTime(a.shift_end)}">
              <div style="font-weight:500">${a.full_name.split(' ').slice(0, 2).join(' ')}</div>
              <div style="font-size:10px;opacity:0.8">${fmtTime(a.shift_start)}–${fmtTime(a.shift_end)}</div>
            </div>`;
          });
        }
        html += `<td style="padding:4px 6px;border-bottom:1px solid #f0f0f0;vertical-align:top;${bg}">${cellHtml}</td>`;
      });
      html += '</tr>';
    });

    html += '</tbody></table></div>';

    // Today's on duty summary
    const todayAssignments = _schedule.filter(a => {
      const now = new Date();
      return new Date(a.shift_start) <= now && new Date(a.shift_end) >= now;
    });
    if (todayAssignments.length > 0) {
      html += `<div style="margin-top:20px;padding:16px;background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px">
        <h3 style="margin:0 0 10px;font-size:15px;font-weight:600;color:#166534">Сейчас на дежурстве</h3>`;
      const seen = new Set();
      todayAssignments.forEach(a => {
        if (seen.has(a.id)) return;
        seen.add(a.id);
        html += `<div style="display:inline-flex;align-items:center;gap:8px;padding:6px 12px;background:#fff;border-radius:6px;margin:3px;font-size:13px;border:1px solid #d1fae5">
          <span style="font-weight:500">${a.full_name}</span>
          <span style="color:#6b7280">${a.station_name} (${a.station_code})</span>
          <span style="font-size:11px;color:#9ca3af">${a.role_on_duty || a.position || ''}</span>
        </div>`;
      });
      html += '</div>';
    }

    html += '</div>';

    // Add modal
    html += `<div id="sched-modal" style="display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.5);z-index:1000;align-items:center;justify-content:center">
      <div style="background:#fff;border-radius:12px;padding:24px;max-width:440px;width:90%;margin:auto;position:relative;top:50%;transform:translateY(-50%)">
        <h3 style="margin:0 0 16px;font-size:16px;font-weight:600">Назначить дежурство</h3>
        <div style="display:flex;flex-direction:column;gap:12px">
          <label style="font-size:13px;font-weight:500">Станция
            <select id="sched-station" style="width:100%;padding:8px;border:1px solid #d1d5db;border-radius:6px;margin-top:4px;font-size:13px">
              ${_stations.map(s => '<option value="' + s.id + '">' + s.name + ' (' + s.code + ')</option>').join('')}
            </select>
          </label>
          <label style="font-size:13px;font-weight:500">Сотрудник
            <select id="sched-person" style="width:100%;padding:8px;border:1px solid #d1d5db;border-radius:6px;margin-top:4px;font-size:13px">
              ${_personnel.map(p => '<option value="' + p.id + '">' + p.full_name + ' — ' + (p.position || p.user_role) + '</option>').join('')}
            </select>
          </label>
          <label style="font-size:13px;font-weight:500">Начало смены
            <input type="datetime-local" id="sched-start" style="width:100%;padding:8px;border:1px solid #d1d5db;border-radius:6px;margin-top:4px;font-size:13px;box-sizing:border-box">
          </label>
          <label style="font-size:13px;font-weight:500">Конец смены
            <input type="datetime-local" id="sched-end" style="width:100%;padding:8px;border:1px solid #d1d5db;border-radius:6px;margin-top:4px;font-size:13px;box-sizing:border-box">
          </label>
          <label style="font-size:13px;font-weight:500">Роль на дежурстве
            <select id="sched-role" style="width:100%;padding:8px;border:1px solid #d1d5db;border-radius:6px;margin-top:4px;font-size:13px">
              <option>Наблюдатель</option>
              <option>Старший наблюдатель</option>
              <option>Инженер-метеоролог</option>
              <option>Техник</option>
            </select>
          </label>
          <div style="display:flex;gap:8px;margin-top:8px">
            <button onclick="window._schedSave()" style="flex:1;padding:10px;border:none;border-radius:6px;background:#0066cc;color:#fff;cursor:pointer;font-weight:500;font-size:14px">Сохранить</button>
            <button onclick="window._schedCloseModal()" style="flex:1;padding:10px;border:1px solid #d1d5db;border-radius:6px;background:#fff;cursor:pointer;font-size:14px">Отмена</button>
          </div>
        </div>
      </div>
    </div>`;

    el.innerHTML = html;
  }

  window._schedPrev = function () { _weekOffset--; showScheduleView(); };
  window._schedNext = function () { _weekOffset++; showScheduleView(); };
  window._schedToday = function () { _weekOffset = 0; showScheduleView(); };

  window._schedAddModal = function () {
    const modal = document.getElementById('sched-modal');
    if (modal) modal.style.display = 'flex';
    // Default to tomorrow 08:00 — 20:00
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    tomorrow.setHours(8, 0, 0, 0);
    const end = new Date(tomorrow);
    end.setHours(20);
    const startEl = document.getElementById('sched-start');
    const endEl = document.getElementById('sched-end');
    if (startEl) startEl.value = tomorrow.toISOString().slice(0, 16);
    if (endEl) endEl.value = end.toISOString().slice(0, 16);
  };

  window._schedCloseModal = function () {
    const modal = document.getElementById('sched-modal');
    if (modal) modal.style.display = 'none';
  };

  window._schedSave = async function () {
    const body = {
      station_id: parseInt(document.getElementById('sched-station').value),
      personnel_id: parseInt(document.getElementById('sched-person').value),
      shift_start: new Date(document.getElementById('sched-start').value).toISOString(),
      shift_end: new Date(document.getElementById('sched-end').value).toISOString(),
      role_on_duty: document.getElementById('sched-role').value,
    };
    const res = await fetch(API, { method: 'POST', headers: hdr(), body: JSON.stringify(body) });
    if (res.ok) {
      window._schedCloseModal();
      showScheduleView();
    } else {
      alert('Ошибка сохранения');
    }
  };

  async function showScheduleView() {
    await loadData();
    render();
  }

  window.showScheduleView = showScheduleView;
})();
