(function () {
    function parseLoginError(response, text) {
        if (!text || !String(text).trim()) {
            if (response.status === 401) return 'Identifiant ou mot de passe incorrect.';
            return 'Connexion impossible (' + response.status + ').';
        }
        try {
            var data = JSON.parse(text);
            var d = data.detail;
            if (typeof d === 'string' && d.trim()) return d;
            if (data.message) return String(data.message);
        } catch (e) { /* ignore */ }
        return 'Connexion impossible. Vérifiez vos identifiants.';
    }

    function setLoginLoading(btn, loading) {
        if (!btn) return;
        btn.disabled = !!loading;
        var span = btn.querySelector('.login-btn-label');
        if (span) span.textContent = loading ? 'Connexion…' : 'Se connecter';
    }

    document.addEventListener('DOMContentLoaded', function () {
        var path = (window.location.pathname || '').toLowerCase();
        var onLoginPage = path === '/' || path.endsWith('/index.html');
        if (onLoginPage && typeof TokenManager !== 'undefined' && TokenManager.isAuthenticated()) {
            fetch('/api/auth/me', { headers: { Authorization: 'Bearer ' + TokenManager.getToken() } })
                .then(function (r) { return r.ok ? r.json() : null; })
                .then(function () {
                    window.location.replace('/pages/enregistrements-relances.html');
                })
                .catch(function () {});
        }

        var loginForm = document.getElementById('loginForm');
        if (!loginForm) return;
        var errorMessage = document.getElementById('errorMessage');
        var passwordInput = document.getElementById('password');
        var togglePwd = document.getElementById('togglePasswordVisibility');
        if (togglePwd && passwordInput) {
            togglePwd.addEventListener('click', function () {
                var isHidden = passwordInput.getAttribute('type') === 'password';
                passwordInput.setAttribute('type', isHidden ? 'text' : 'password');
                togglePwd.textContent = isHidden ? '🙈' : '👁';
            });
        }

        loginForm.addEventListener('submit', async function (e) {
            e.preventDefault();
            var email = (document.getElementById('email') || {}).value || '';
            var password = (document.getElementById('password') || {}).value || '';
            var submitBtn = loginForm.querySelector('button[type="submit"]');
            if (errorMessage) { errorMessage.textContent = ''; errorMessage.classList.remove('show'); }
            setLoginLoading(submitBtn, true);
            try {
                var formData = new FormData();
                formData.append('username', email.trim());
                formData.append('password', password);
                var response = await fetch('/api/auth/login', { method: 'POST', body: formData });
                var text = await response.text();
                if (!response.ok) throw new Error(parseLoginError(response, text));
                var data = text ? JSON.parse(text) : {};
                if (!data.access_token) throw new Error('Réponse serveur incomplète.');
                TokenManager.setToken(data.access_token);
                window.location.href = '/pages/enregistrements-relances.html';
            } catch (error) {
                if (errorMessage) {
                    errorMessage.textContent = error.message || 'Erreur';
                    errorMessage.classList.add('show');
                }
            } finally {
                setLoginLoading(submitBtn, false);
            }
        });
    });
})();

window.logout = function () {
    TokenManager.removeToken();
    window.location.href = '/';
};
