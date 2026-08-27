const API_BASE_URL = '/api';

const TokenManager = {
    getToken() { return localStorage.getItem('token'); },
    setToken(token) { localStorage.setItem('token', token); },
    removeToken() { localStorage.removeItem('token'); },
    isAuthenticated() { return !!this.getToken(); }
};

const API = {
    async request(endpoint, options = {}) {
        const token = TokenManager.getToken();
        const headers = { 'Content-Type': 'application/json', ...options.headers };
        if (token) headers.Authorization = 'Bearer ' + token;
        const response = await fetch(API_BASE_URL + endpoint, { ...options, headers });
        if (response.status === 401) {
            TokenManager.removeToken();
            const path = (window.location.pathname || '').toLowerCase();
            if (path !== '/' && !path.endsWith('/index.html')) window.location.href = '/';
            throw new Error('Session expirée (401)');
        }
        const text = await response.text();
        let data = null;
        if (text) {
            try { data = JSON.parse(text); } catch (e) { data = text; }
        }
        if (!response.ok) {
            let msg = 'Une erreur est survenue';
            if (data && data.detail) {
                msg = Array.isArray(data.detail)
                    ? data.detail.map(function (err) { return err.msg || JSON.stringify(err); }).join(', ')
                    : String(data.detail);
            } else if (data && data.message) {
                msg = String(data.message);
            } else if (text) {
                msg = String(text);
            }
            const error = new Error(msg);
            error.status = response.status;
            error.data = data;
            throw error;
        }
        return data;
    },
    get(endpoint) { return this.request(endpoint, { method: 'GET' }); },
    post(endpoint, data) { return this.request(endpoint, { method: 'POST', body: JSON.stringify(data || {}) }); },
    put(endpoint, data) { return this.request(endpoint, { method: 'PUT', body: JSON.stringify(data || {}) }); },
    delete(endpoint) { return this.request(endpoint, { method: 'DELETE' }); }
};

window.API = API;
window.TokenManager = TokenManager;

function getRoleValue(user) {
    var roleRaw = (typeof user?.role === 'string') ? user.role : (user?.role?.value || user?.role?.name || '');
    return String(roleRaw || '').toLowerCase();
}

function logout() {
    TokenManager.removeToken();
    window.location.href = '/';
}

function checkAuth() {
    var path = (window.location.pathname || '').toLowerCase();
    var onLogin = path === '/' || path.endsWith('/index.html');
    if (!TokenManager.isAuthenticated()) {
        if (!onLogin) window.location.href = '/';
        return;
    }
    API.get('/auth/me').then(function (user) {
        var role = getRoleValue(user);
        if (window.SidebarNav && typeof window.SidebarNav.mount === 'function') {
            window.SidebarNav.mount(user);
        } else {
            initAppSidebar(user);
        }
        if (role !== 'admin' && !onLogin) {
            window.location.href = '/';
        }
    }).catch(function () {
        TokenManager.removeToken();
        if (!onLogin) window.location.href = '/';
    });
}

function initAppSidebar(user) {
    if (!document.body.classList.contains('app-page')) return;
    function run() {
        if (window.SidebarNav && typeof window.SidebarNav.mount === 'function') {
            window.SidebarNav.mount(user);
        }
    }
    if (window.SidebarNav) { run(); return; }
    var s = document.createElement('script');
    s.src = '/js/sidebar-nav.js?v=1';
    s.onload = run;
    document.head.appendChild(s);
}

document.addEventListener('DOMContentLoaded', function () {
    checkAuth();
});
