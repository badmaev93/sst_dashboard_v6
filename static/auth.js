/* SST Dashboard v5 — auth.js: Authentication UI and token management */
"use strict";

(function() {
    let _currentUser = null;

    // ── Auth Fetch Wrapper ──────────────────────
    window.authFetch = async function(url, options = {}) {
        const token = localStorage.getItem('access_token');
        if (token) {
            options.headers = options.headers || {};
            options.headers['Authorization'] = 'Bearer ' + token;
        }
        const resp = await fetch(url, options);
        if (resp.status === 401) {
            const refreshed = await refreshToken();
            if (refreshed) {
                // Reset header with new token
                options.headers = options.headers || {};
                options.headers['Authorization'] = 'Bearer ' + localStorage.getItem('access_token');
                return fetch(url, options);
            }
            showLoginForm();
            throw new Error('Unauthorized');
        }
        return resp;
    };

    // ── Refresh Token ───────────────────────────
    async function refreshToken() {
        const rt = localStorage.getItem('refresh_token');
        if (!rt) return false;
        try {
            const resp = await fetch('/api/auth/refresh', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ refresh_token: rt })
            });
            if (!resp.ok) return false;
            const data = await resp.json();
            localStorage.setItem('access_token', data.access_token);
            if (data.refresh_token) localStorage.setItem('refresh_token', data.refresh_token);
            return true;
        } catch (e) {
            return false;
        }
    }

    // ── Get Current User ────────────────────────
    window.getCurrentUser = async function() {
        if (_currentUser) return _currentUser;
        try {
            const resp = await authFetch('/api/auth/me');
            if (!resp.ok) return null;
            _currentUser = await resp.json();
            return _currentUser;
        } catch (e) {
            return null;
        }
    };

    // ── Role Labels & Colors ────────────────────
    const ROLE_MAP = {
        supervisor:    { label: 'Руководитель', color: '#7c3aed', bg: '#ede9fe' },
        data_analyst:  { label: 'Аналитик',     color: '#2563eb', bg: '#dbeafe' },
        observer:      { label: 'Наблюдатель',  color: '#059669', bg: '#d1fae5' },
        engineer:      { label: 'Инженер',      color: '#d97706', bg: '#fef3c7' }
    };
    window.ROLE_MAP = ROLE_MAP;

    function roleBadge(role) {
        const r = ROLE_MAP[role] || { label: role, color: '#6b7280', bg: '#f3f4f6' };
        return '<span style="display:inline-block;padding:2px 10px;border-radius:12px;font-size:11px;' +
               'font-weight:600;color:' + r.color + ';background:' + r.bg + '">' + r.label + '</span>';
    }
    window.roleBadge = roleBadge;

    // ── Login Form ──────────────────────────────
    function showLoginForm() {
        if (document.getElementById('auth-overlay')) return;

        const overlay = document.createElement('div');
        overlay.id = 'auth-overlay';
        Object.assign(overlay.style, {
            position: 'fixed', inset: '0', zIndex: '10000',
            background: 'rgba(15,23,42,0.55)', backdropFilter: 'blur(6px)',
            display: 'flex', alignItems: 'center', justifyContent: 'center'
        });

        // Close overlay on click outside the card
        overlay.addEventListener('click', function(e) {
            if (e.target === overlay) overlay.remove();
        });

        overlay.innerHTML = `
            <div role="dialog" aria-modal="true" aria-label="Вход в систему" tabindex="-1"
                 style="background:#fff;border-radius:14px;padding:36px 32px 28px;width:370px;
                        box-shadow:0 20px 60px rgba(0,0,0,0.18);font-family:inherit;position:relative">
                <button id="auth-close" aria-label="Закрыть" style="position:absolute;top:12px;right:12px;width:32px;height:32px;
                        border:none;background:#f3f4f6;border-radius:8px;font-size:18px;color:#6b7280;
                        cursor:pointer;display:flex;align-items:center;justify-content:center;
                        transition:background .15s"
                        onmouseover="this.style.background='#e5e7eb'"
                        onmouseout="this.style.background='#f3f4f6'">&#215;</button>
                <h2 style="margin:0 0 6px;font-size:20px;font-weight:700;color:#1a2030">
                    Вход в систему
                </h2>
                <p style="margin:0 0 22px;font-size:13px;color:#64748b">
                    SST Dashboard — мониторинг и управление
                </p>
                <div id="auth-error" style="display:none;margin-bottom:14px;padding:10px 14px;
                     border-radius:8px;background:#fef2f2;color:#dc2626;font-size:12px"></div>
                <label style="display:block;margin-bottom:14px">
                    <span style="display:block;font-size:12px;font-weight:600;color:#475569;margin-bottom:4px">
                        Логин
                    </span>
                    <input id="auth-username" type="text" autocomplete="username"
                           style="width:100%;padding:9px 12px;border:1px solid #d1d5db;border-radius:8px;
                                  font-size:13px;outline:none;transition:border-color .15s"
                           onfocus="this.style.borderColor='#3b82f6'"
                           onblur="this.style.borderColor='#d1d5db'" />
                </label>
                <label style="display:block;margin-bottom:20px">
                    <span style="display:block;font-size:12px;font-weight:600;color:#475569;margin-bottom:4px">
                        Пароль
                    </span>
                    <input id="auth-password" type="password" autocomplete="current-password"
                           style="width:100%;padding:9px 12px;border:1px solid #d1d5db;border-radius:8px;
                                  font-size:13px;outline:none;transition:border-color .15s"
                           onfocus="this.style.borderColor='#3b82f6'"
                           onblur="this.style.borderColor='#d1d5db'" />
                </label>
                <button id="auth-submit" style="width:100%;padding:10px;background:#2563eb;color:#fff;
                        border:none;border-radius:8px;font-size:14px;font-weight:600;cursor:pointer;
                        transition:background .15s"
                        onmouseover="this.style.background='#1d4ed8'"
                        onmouseout="this.style.background='#2563eb'">
                    Войти
                </button>
            </div>
        `;

        document.body.appendChild(overlay);

        const usernameInput = document.getElementById('auth-username');
        const passwordInput = document.getElementById('auth-password');
        const submitBtn = document.getElementById('auth-submit');

        async function doLogin() {
            const errEl = document.getElementById('auth-error');
            errEl.style.display = 'none';
            submitBtn.disabled = true;
            submitBtn.textContent = 'Вход...';

            try {
                const resp = await fetch('/api/auth/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        username: usernameInput.value.trim(),
                        password: passwordInput.value
                    })
                });

                if (!resp.ok) {
                    const d = await resp.json().catch(() => ({}));
                    throw new Error(d.detail || 'Неверный логин или пароль');
                }

                const data = await resp.json();
                localStorage.setItem('access_token', data.access_token);
                if (data.refresh_token) localStorage.setItem('refresh_token', data.refresh_token);
                overlay.remove();
                _currentUser = null;
                window.location.reload();
            } catch (e) {
                errEl.textContent = e.message;
                errEl.style.display = 'block';
                submitBtn.disabled = false;
                submitBtn.textContent = 'Войти';
            }
        }

        submitBtn.addEventListener('click', doLogin);
        passwordInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') doLogin();
        });
        usernameInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') passwordInput.focus();
        });

        // Close on Escape key
        overlay.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') overlay.remove();
        });

        // Close button
        var closeBtn = document.getElementById('auth-close');
        if (closeBtn) closeBtn.addEventListener('click', function() { overlay.remove(); });

        setTimeout(function() { usernameInput.focus(); }, 100);
    }
    window.showLoginForm = showLoginForm;

    // ── User Menu (top-right) ───────────────────
    function showUserMenu(user) {
        let menu = document.getElementById('user-menu');
        if (menu) menu.remove();

        const r = ROLE_MAP[user.role] || { label: user.role, color: '#6b7280', bg: '#f3f4f6' };

        menu = document.createElement('div');
        menu.id = 'user-menu';
        Object.assign(menu.style, {
            position: 'fixed', top: '12px', right: '12px', zIndex: '9500',
            background: '#fff', borderRadius: '50%', padding: '0',
            boxShadow: '0 2px 12px rgba(0,0,0,0.12)', fontFamily: 'inherit',
            overflow: 'hidden', transition: 'border-radius .2s, min-width .2s'
        });

        const initials = (user.full_name || user.username || '?').split(' ').map(w => w[0]).join('').substring(0, 2).toUpperCase();
        menu.innerHTML = `
            <div id="user-menu-toggle" role="button" tabindex="0" aria-label="Меню пользователя"
                 aria-haspopup="true" aria-expanded="false" style="display:flex;align-items:center;gap:0;padding:0;
                 cursor:pointer;user-select:none;width:40px;height:40px;justify-content:center">
                <div style="width:36px;height:36px;border-radius:50%;background:${r.bg};
                     display:flex;align-items:center;justify-content:center;
                     font-weight:700;font-size:13px;color:${r.color};
                     border:2px solid ${r.color}30;transition:box-shadow .2s">
                    ${initials}
                </div>
            </div>
            <div id="user-menu-dropdown" style="display:none;border-top:1px solid #f1f5f9">
                <div style="padding:10px 14px;border-bottom:1px solid #f1f5f9">
                    <div style="font-size:13px;font-weight:600;color:#1a2030">${user.full_name || user.username}</div>
                    <div style="font-size:11px;color:${r.color};font-weight:500">${r.label}</div>
                </div>
                <button class="um-btn" data-action="cabinet"
                        style="width:100%;text-align:left;padding:10px 14px;border:none;background:none;
                        font-size:13px;color:#334155;cursor:pointer;font-family:inherit"
                        onmouseover="this.style.background='#f8fafc'"
                        onmouseout="this.style.background='none'">
                    Личный кабинет
                </button>
                <button class="um-btn" data-action="logout"
                        style="width:100%;text-align:left;padding:10px 14px;border:none;background:none;
                        font-size:13px;color:#dc2626;cursor:pointer;font-family:inherit;
                        border-top:1px solid #f1f5f9"
                        onmouseover="this.style.background='#fef2f2'"
                        onmouseout="this.style.background='none'">
                    Выйти
                </button>
            </div>
        `;

        document.body.appendChild(menu);

        const toggle = document.getElementById('user-menu-toggle');
        const dropdown = document.getElementById('user-menu-dropdown');
        let open = false;

        function toggleMenu() {
            open = !open;
            dropdown.style.display = open ? 'block' : 'none';
            menu.style.borderRadius = open ? '10px' : '50%';
            menu.style.minWidth = open ? '200px' : '';
            toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
        }

        toggle.addEventListener('click', toggleMenu);
        toggle.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                toggleMenu();
            } else if (e.key === 'Escape' && open) {
                open = false;
                dropdown.style.display = 'none';
                menu.style.borderRadius = '50%';
                menu.style.minWidth = '';
                toggle.setAttribute('aria-expanded', 'false');
                toggle.focus();
            }
        });

        menu.querySelectorAll('.um-btn').forEach(function(btn) {
            btn.addEventListener('click', function() {
                const action = btn.dataset.action;
                if (action === 'logout') logout();
                if (action === 'cabinet' && window.showCabinetView) window.showCabinetView();
                dropdown.style.display = 'none';
                open = false;
                toggle.setAttribute('aria-expanded', 'false');
            });
        });

        document.addEventListener('click', function(e) {
            if (!menu.contains(e.target)) {
                dropdown.style.display = 'none';
                open = false;
                menu.style.borderRadius = '50%';
                menu.style.minWidth = '';
                toggle.setAttribute('aria-expanded', 'false');
            }
        });
    }
    window.showUserMenu = showUserMenu;

    // ── Logout ──────────────────────────────────
    function logout() {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        _currentUser = null;
        const menu = document.getElementById('user-menu');
        if (menu) menu.remove();
        window.location.reload();
    }
    window.logout = logout;

    // ── Check Auth on Load ──────────────────────
    window.checkAuth = async function() {
        const token = localStorage.getItem('access_token');
        if (!token) return;
        try {
            const user = await getCurrentUser();
            if (user) {
                showUserMenu(user);
                var loginBtn = document.getElementById('login-btn');
                if (loginBtn) loginBtn.style.display = 'none';
            }
        } catch (e) {
            // Token invalid — SST map works without auth
        }
    };

    // Auto-check on load
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() { checkAuth(); });
    } else {
        checkAuth();
    }
})();
