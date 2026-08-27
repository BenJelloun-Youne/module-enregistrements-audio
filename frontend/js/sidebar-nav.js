(function (global) {
    var ICONS = {
        mic: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" x2="12" y1="19" y2="22"/></svg>',
        sliders: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="4" x2="4" y1="21" y2="14"/><line x1="4" x2="4" y1="10" y2="3"/><line x1="12" x2="12" y1="21" y2="12"/><line x1="12" x2="12" y1="8" y2="3"/><line x1="20" x2="20" y1="21" y2="16"/><line x1="20" x2="20" y1="12" y2="3"/><line x1="2" x2="6" y1="14" y2="14"/><line x1="10" x2="14" y1="8" y2="8"/><line x1="18" x2="22" y1="16" y2="16"/></svg>',
        'log-out': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" x2="9" y1="12" y2="12"/></svg>',
        search: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>',
        'chevron-down': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m6 9 6 6 6-6"/></svg>'
    };

    function getRole(user) {
        var r = user && user.role;
        return String(typeof r === 'string' ? r : (r && r.value) || '').toLowerCase();
    }

    function esc(s) {
        if (s == null) return '';
        var d = document.createElement('div');
        d.textContent = String(s);
        return d.innerHTML;
    }

    function getDisplayName(user) {
        if (!user) return 'Admin';
        if (user.full_name && String(user.full_name).trim()) return user.full_name;
        var email = (user.email && String(user.email)) || '';
        return email.split('@')[0] || 'Admin';
    }

    function isActive(pathname, href) {
        try {
            var target = new URL(href, window.location.origin).pathname.toLowerCase();
            return pathname === target || (pathname.split('/').pop() === target.split('/').pop());
        } catch (e) {
            return false;
        }
    }

    function mount(user) {
        if (!document.body.classList.contains('app-page')) return;
        if (document.getElementById('appShell')) return;
        document.body.classList.add('has-app-sidebar');
        var oldHeader = document.querySelector('.app-header.nav');
        if (oldHeader) oldHeader.setAttribute('aria-hidden', 'true');

        var pathname = (window.location.pathname || '').toLowerCase();
        var items = [
            { id: 'navEnregistrements', label: 'Enregistrements et relances', icon: 'mic', href: '/pages/enregistrements-relances.html' },
            { id: 'navCriteresAudio', label: "Critères d'analyse audio", icon: 'sliders', href: '/pages/criteres-analyse-audio.html' }
        ];
        var nav = '';
        items.forEach(function (it) {
            var active = isActive(pathname, it.href) ? ' app-sidebar__link--active' : '';
            nav += '<a class="app-sidebar__link' + active + '" href="' + it.href + '" id="' + it.id + '" title="' + it.label + '">';
            nav += (ICONS[it.icon] || '') + '<span class="app-sidebar__label">' + it.label + '</span></a>';
        });

        var name = getDisplayName(user);
        var initials = name.slice(0, 2).toUpperCase();
        var email = (user && user.email) || '';

        var shell = document.createElement('div');
        shell.id = 'appShell';
        shell.className = 'app-shell';
        shell.innerHTML =
            '<aside class="app-sidebar" id="appSidebar" aria-label="Navigation">' +
            '<div class="app-sidebar__logo"><a href="/pages/enregistrements-relances.html" title="Accueil">' +
            '<span class="app-sidebar__logo-crop"><span class="app-sidebar__label" style="font-weight:800">SC Audio</span></span></a></div>' +
            '<div class="app-sidebar__body"><nav class="app-sidebar__nav">' +
            '<div class="app-sidebar__group"><p class="app-sidebar__group-title">Enregistrements</p>' +
            '<div class="app-sidebar__items">' + nav + '</div></div></nav></div>' +
            '<div class="app-sidebar__footer">' +
            '<button type="button" class="app-sidebar__link app-sidebar__logout" id="sidebarLogout" title="Déconnexion">' +
            ICONS['log-out'] + '<span class="app-sidebar__label">Déconnexion</span></button></div></aside>' +
            '<div class="app-shell__main">' +
            '<header class="app-topbar">' +
            '<div class="app-topbar__search"><span class="app-topbar__search-icon">' + ICONS.search + '</span>' +
            '<input type="search" placeholder="Rechercher..." aria-label="Rechercher" autocomplete="off" /></div>' +
            '<div class="app-topbar__actions"><div class="app-topbar__user-wrap">' +
            '<button type="button" class="app-topbar__user" id="topbarUserTrigger" aria-expanded="false">' +
            '<span class="app-topbar__avatar">' + esc(initials) + '</span>' +
            '<span class="app-topbar__user-text"><span class="app-topbar__user-name">' + esc(name) + '</span>' +
            '<span class="app-topbar__user-role">Administrateur</span></span>' +
            '<span class="app-topbar__chevron">' + ICONS['chevron-down'] + '</span></button>' +
            '<div class="app-topbar__user-menu" id="topbarUserMenu" hidden>' +
            '<span style="display:block;padding:8px 12px;font-size:12px;color:#64748b">' + esc(email) + '</span>' +
            '<button type="button" class="--danger" id="topbarLogout">Déconnexion</button></div></div></div></header>' +
            '<div class="app-shell__content" id="appShellContent"></div></div>';

        var content = shell.querySelector('#appShellContent');
        document.body.insertBefore(shell, document.body.firstChild);
        Array.from(document.querySelectorAll('body.app-page > main, body.app-page > .sc-reactivation')).forEach(function (node) {
            content.appendChild(node);
        });

        function doLogout() { if (typeof global.logout === 'function') global.logout(); }
        var sl = document.getElementById('sidebarLogout');
        if (sl) sl.addEventListener('click', doLogout);
        var tl = document.getElementById('topbarLogout');
        if (tl) tl.addEventListener('click', doLogout);
        var trigger = document.getElementById('topbarUserTrigger');
        var menu = document.getElementById('topbarUserMenu');
        if (trigger && menu) {
            trigger.addEventListener('click', function (e) {
                e.stopPropagation();
                var open = !menu.hasAttribute('hidden');
                if (open) menu.setAttribute('hidden', '');
                else menu.removeAttribute('hidden');
            });
            document.addEventListener('click', function () { menu.setAttribute('hidden', ''); });
        }
    }

    global.SidebarNav = { mount: mount };
})(window);
