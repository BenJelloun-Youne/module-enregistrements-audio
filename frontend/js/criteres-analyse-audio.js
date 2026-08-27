/**
 * Admin — Critères / prompts d'analyse audio (paramétrables).
 * Page : /pages/criteres-analyse-audio.html
 */
(function () {
    'use strict';

    function escapeHtml(s) {
        if (s == null || s === '') return '';
        return String(s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function flash(msg, isErr) {
        var el = document.getElementById('caFlash');
        if (!el) return;
        if (!msg) {
            el.classList.add('hidden');
            el.textContent = '';
            return;
        }
        el.classList.remove('hidden');
        el.textContent = msg;
        el.className =
            'rounded-xl border px-4 py-3 text-sm ' +
            (isErr
                ? 'border-red-200 bg-red-50 text-red-900'
                : 'border-emerald-200 bg-emerald-50 text-emerald-900');
    }

    function updateEmptyWarn(prompts) {
        var warn = document.getElementById('caEmptyWarn');
        if (!warn) return;
        var empty = (prompts || []).some(function (p) {
            return p.key === 'codif' && (!(p.system_prompt || '').trim() || !(p.user_prompt || '').trim());
        });
        warn.classList.toggle('hidden', !empty);
    }

    function renderPrompts(prompts) {
        var root = document.getElementById('caPrompts');
        if (!root) return;
        root.innerHTML = '<h2 class="text-sm font-bold text-slate-900 uppercase tracking-wide">Prompts LLM</h2>';
        (prompts || []).forEach(function (p) {
            var card = document.createElement('div');
            card.className = 'rounded-xl border border-slate-200 p-4 space-y-3';
            card.innerHTML =
                '<div class="flex flex-wrap items-center justify-between gap-2">' +
                '<div><p class="text-sm font-bold text-slate-900">' + escapeHtml(p.label) +
                ' <span class="font-mono text-xs text-slate-500">(' + escapeHtml(p.key) + ')</span></p>' +
                '<p class="text-xs text-slate-500 mt-0.5">' + escapeHtml(p.description || '') + '</p></div>' +
                '<label class="text-xs font-semibold text-slate-600 flex items-center gap-2">' +
                '<input type="checkbox" data-role="enabled" ' + (p.enabled ? 'checked' : '') + ' /> Actif</label></div>' +
                '<label class="block text-xs font-semibold text-slate-600">System prompt' +
                '<textarea data-role="system" rows="6" class="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-xs font-mono">' +
                escapeHtml(p.system_prompt || '') +
                '</textarea></label>' +
                '<label class="block text-xs font-semibold text-slate-600">User prompt' +
                '<textarea data-role="user" rows="8" class="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-xs font-mono">' +
                escapeHtml(p.user_prompt || '') +
                '</textarea></label>' +
                '<button type="button" data-id="' + p.id + '" class="ca-save-prompt rounded-lg bg-slate-900 px-3 py-2 text-xs font-semibold text-white hover:bg-slate-800">Enregistrer</button>';
            root.appendChild(card);
            card.querySelector('.ca-save-prompt').addEventListener('click', function () {
                var body = {
                    system_prompt: card.querySelector('[data-role="system"]').value,
                    user_prompt: card.querySelector('[data-role="user"]').value,
                    enabled: card.querySelector('[data-role="enabled"]').checked
                };
                API.put('/admin/enregistrements/config/prompts/' + p.id, body)
                    .then(function () {
                        flash('Prompt « ' + p.key + ' » enregistré');
                        return loadAll();
                    })
                    .catch(function (e) {
                        flash(e.message || 'Erreur', true);
                    });
            });
        });
        updateEmptyWarn(prompts);
    }

    function renderCriteria(rows) {
        var root = document.getElementById('caCriteriaList');
        if (!root) return;
        if (!rows || !rows.length) {
            root.innerHTML = '<p class="text-sm text-slate-500">Aucun critère</p>';
            return;
        }
        root.innerHTML = '';
        rows.forEach(function (c) {
            var card = document.createElement('div');
            card.className = 'rounded-xl border border-slate-200 p-4 space-y-3';
            card.innerHTML =
                '<div class="flex flex-wrap items-center justify-between gap-2">' +
                '<p class="text-sm font-bold text-slate-900">' + escapeHtml(c.label) +
                ' <span class="font-mono text-xs text-slate-500">(' + escapeHtml(c.key) + ')</span></p>' +
                '<label class="text-xs font-semibold text-slate-600 flex items-center gap-2">' +
                '<input type="checkbox" data-role="enabled" ' + (c.enabled ? 'checked' : '') + ' /> Actif</label></div>' +
                '<label class="block text-xs font-semibold text-slate-600">Libellé' +
                '<input data-role="label" type="text" class="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm" value="' +
                escapeHtml(c.label) +
                '" /></label>' +
                '<label class="block text-xs font-semibold text-slate-600">Règle d\'évaluation (injectée dans le prompt critères)' +
                '<textarea data-role="description" rows="3" class="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-xs">' +
                escapeHtml(c.description || '') +
                '</textarea></label>' +
                '<div class="flex flex-wrap gap-2">' +
                '<button type="button" class="ca-save-crit rounded-lg bg-slate-900 px-3 py-2 text-xs font-semibold text-white">Enregistrer</button>' +
                '<button type="button" class="ca-del-crit rounded-lg border border-red-200 px-3 py-2 text-xs font-semibold text-red-700 hover:bg-red-50">Supprimer</button>' +
                '</div>';
            root.appendChild(card);
            card.querySelector('.ca-save-crit').addEventListener('click', function () {
                API.put('/admin/enregistrements/config/criteria/' + c.id, {
                    label: card.querySelector('[data-role="label"]').value,
                    description: card.querySelector('[data-role="description"]').value,
                    enabled: card.querySelector('[data-role="enabled"]').checked
                })
                    .then(function () {
                        flash('Critère « ' + c.key + ' » enregistré');
                        return loadAll();
                    })
                    .catch(function (e) {
                        flash(e.message || 'Erreur', true);
                    });
            });
            card.querySelector('.ca-del-crit').addEventListener('click', function () {
                if (!confirm('Supprimer le critère « ' + c.key + ' » ?')) return;
                API.delete('/admin/enregistrements/config/criteria/' + c.id)
                    .then(function () {
                        flash('Critère supprimé');
                        return loadAll();
                    })
                    .catch(function (e) {
                        flash(e.message || 'Erreur', true);
                    });
            });
        });
    }

    function loadAll() {
        return Promise.all([
            API.get('/admin/enregistrements/config/prompts'),
            API.get('/admin/enregistrements/config/criteria')
        ]).then(function (res) {
            renderPrompts(res[0]);
            renderCriteria(res[1]);
        });
    }

    function bind() {
        var orangeBtn = document.getElementById('caLoadOrangeBtn');
        if (orangeBtn) {
            orangeBtn.addEventListener('click', function () {
                if (!confirm('Remplacer prompts et règles par le modèle Orange ?')) return;
                API.post('/admin/enregistrements/config/load-orange-defaults?overwrite=true', {})
                    .then(function () {
                        flash('Modèle Orange chargé — vous pouvez encore tout modifier');
                        return loadAll();
                    })
                    .catch(function (e) {
                        flash(e.message || 'Erreur', true);
                    });
            });
        }

        var addBtn = document.getElementById('caAddCriterionBtn');
        if (addBtn) {
            addBtn.addEventListener('click', function () {
                var key = prompt('Clé technique (ex. posture_ok) :');
                if (!key) return;
                var label = prompt('Libellé :', key) || key;
                API.post('/admin/enregistrements/config/criteria', {
                    key: key.trim(),
                    label: label.trim(),
                    description: '',
                    enabled: true,
                    sort_order: 100
                })
                    .then(function () {
                        flash('Critère ajouté (règle vide — à compléter)');
                        return loadAll();
                    })
                    .catch(function (e) {
                        flash(e.message || 'Erreur', true);
                    });
            });
        }
    }

    document.addEventListener('DOMContentLoaded', function () {
        if (typeof checkAuth === 'function') checkAuth();
        bind();
        loadAll().catch(function (e) {
            flash(e.message || 'Erreur chargement', true);
        });
    });
})();
