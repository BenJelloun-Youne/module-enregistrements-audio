/**
 * Client API minimal requis par les 2 pages (si le SaaS n'a pas déjà app.js).
 *
 * Contrat attendu par :
 *   - frontend/js/enregistrements-relances.js
 *   - frontend/js/criteres-analyse-audio.js
 *
 * Si le SaaS a déjà `window.API`, `checkAuth`, `logout` → NE PAS charger ce fichier.
 */
(function () {
    'use strict';

    if (window.API) return;

    var API_BASE_URL = '/api';

    var TokenManager = {
        getToken: function () { return localStorage.getItem('token'); },
        setToken: function (t) { localStorage.setItem('token', t); },
        removeToken: function () { localStorage.removeItem('token'); },
        isAuthenticated: function () { return !!this.getToken(); }
    };

    var API = {
        request: function (endpoint, options) {
            options = options || {};
            var headers = Object.assign({ 'Content-Type': 'application/json' }, options.headers || {});
            var token = TokenManager.getToken();
            if (token) headers.Authorization = 'Bearer ' + token;
            return fetch(API_BASE_URL + endpoint, Object.assign({}, options, { headers: headers }))
                .then(function (response) {
                    if (response.status === 401) {
                        TokenManager.removeToken();
                        var path = (window.location.pathname || '').toLowerCase();
                        if (path !== '/' && !path.endsWith('/index.html')) {
                            window.location.href = '/';
                        }
                        throw new Error('Session expirée (401)');
                    }
                    return response.text().then(function (text) {
                        var data = text ? (function () { try { return JSON.parse(text); } catch (e) { return text; } })() : null;
                        if (!response.ok) {
                            var msg = (data && data.detail) ? String(data.detail) : (text || ('Erreur HTTP ' + response.status));
                            var err = new Error(msg);
                            err.status = response.status;
                            err.data = data;
                            throw err;
                        }
                        return data;
                    });
                });
        },
        get: function (ep) { return this.request(ep, { method: 'GET' }); },
        post: function (ep, data) { return this.request(ep, { method: 'POST', body: JSON.stringify(data || {}) }); },
        put: function (ep, data) { return this.request(ep, { method: 'PUT', body: JSON.stringify(data || {}) }); },
        delete: function (ep) { return this.request(ep, { method: 'DELETE' }); }
    };

    function checkAuth() {
        if (!TokenManager.isAuthenticated()) {
            var path = window.location.pathname || '';
            if (path !== '/' && path.indexOf('index.html') === -1) {
                window.location.href = '/';
            }
        }
    }

    function logout() {
        TokenManager.removeToken();
        window.location.href = '/';
    }

    window.API = API;
    window.TokenManager = TokenManager;
    window.checkAuth = checkAuth;
    window.logout = logout;
})();
