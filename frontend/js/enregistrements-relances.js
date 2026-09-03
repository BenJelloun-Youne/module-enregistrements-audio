/**
 * Dispositif de Réactivation Concentrix — UI portée depuis Tersea (KPI / funnel / tableaux).
 * Données : GET /api/admin/enregistrements/dashboard (Postgres local, pas BigQuery).
 */
(function () {
    'use strict';

    var state = { weeks: [], view: null, data: null };

    function nb(x) {
        return Math.round(Number(x) || 0).toLocaleString('fr-FR').replace(/\u202f/g, ' ');
    }
    function pc1(a, b) {
        if (!b) return '0';
        return ((a / b) * 100).toFixed(1).replace('.', ',');
    }
    function esc(s) {
        if (s == null || s === '') return '';
        return String(s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }
    function dash(v) {
        return v == null || v === '' ? '—' : v;
    }

    var ANALYSE_COLS = [
        'Date/heure dernière codification CC',
        'Date/heure dernière appel hipto',
        'Téléphone',
        'Nom',
        'Prénom',
        '# codification CC',
        '# appel numéro hipto',
        'dernière codification CC',
        'dernière codification hipto',
        'historique codification CC (avec date/heure)',
        'historique codification hipto (avec date/heure)',
        'Appel #1',
        'Résumé #1',
        'Appel #2',
        'Résumé #2'
    ];
    var ANALYSE_FIELDS = [
        'date_derniere_codif_cc',
        'date_dernier_appel',
        'ph',
        'nom',
        'prenom',
        'nb_codif_cc',
        'nb_enreg',
        'derniere_codif_cc',
        'derniere_codif_sc',
        'hist_cc',
        'hist_sc',
        'appel1',
        'resume1',
        'appel2',
        'resume2'
    ];

    function analyseCell(row, field) {
        var v = row[field];
        if (field === 'nb_codif_cc' || field === 'nb_enreg') return nb(v != null ? v : 0);
        if (field === 'ph') return '<td class="font-mono">' + esc(dash(v)) + '</td>';
        if (field === 'resume1' || field === 'resume2') return '<td>' + esc(dash(String(v || '').slice(0, 200))) + '</td>';
        return '<td>' + esc(dash(v)) + '</td>';
    }
    function flash(msg, isErr) {
        var el = document.getElementById('erFlash');
        if (!el) return;
        if (!msg) {
            el.classList.add('hidden');
            el.textContent = '';
            return;
        }
        el.classList.remove('hidden');
        el.textContent = msg;
        el.style.borderColor = isErr ? '#fecaca' : '#bbf7d0';
        el.style.background = isErr ? '#fef2f2' : '#effdf4';
        el.style.color = isErr ? '#991b1b' : '#166534';
    }

    function icoPeople() {
        return '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><circle cx="9" cy="8" r="3"/><path d="M3 20c0-3 3-5 6-5s6 2 6 5"/><path d="M16 6a3 3 0 0 1 0 6M20 20c0-2.5-1.5-4-3.5-4.5"/></svg>';
    }
    function icoPhone() {
        return '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h4l2 5-2 2a12 12 0 0 0 5 5l2-2 5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 2 6a2 2 0 0 1 2-2z"/></svg>';
    }
    function icoCart() {
        return '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><circle cx="9" cy="20" r="1.5"/><circle cx="18" cy="20" r="1.5"/><path d="M2 3h3l2.5 12h11l2-8H6"/></svg>';
    }
    function icoJoin() {
        return '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="#fff" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M8 12l3 3 5-6"/></svg>';
    }
    function icoPhoneOff() {
        return '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h4l2 5-2 2a12 12 0 0 0 5 5l2-2 5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 2 6a2 2 0 0 1 2-2z"/><line x1="2" y1="2" x2="22" y2="22"/></svg>';
    }
    function icoSms() {
        return '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="14" rx="2"/><path d="M7 8h10M7 12h6"/><path d="M8 18l-3 3v-3"/></svg>';
    }

    function sect(color, title, tail) {
        return (
            '<div class="sc-sect"><span class="sc-dot" style="background:' +
            (color || '#2E69FF') +
            '"></span><b>' +
            esc(title) +
            '</b>' +
            (tail ? '<span class="sc-sect-tail"> — ' + esc(tail) + '</span>' : '') +
            '</div>'
        );
    }

    function kpi(icon, bg, fg, label, big, sub) {
        return (
            '<div class="sc-card sc-kpi"><div class="sc-ico" style="background:' +
            bg +
            ';color:' +
            fg +
            '">' +
            icon +
            '</div><div class="sc-kpi-l">' +
            esc(label) +
            '</div><div class="sc-kpi-n">' +
            big +
            '</div><div class="sc-kpi-s">' +
            esc(sub) +
            '</div></div>'
        );
    }

    function cell(label, big, sub, color, barPct, barCol) {
        var w = Math.min(100, Math.max(0, barPct || 0));
        return (
            '<div class="sc-cell"><div class="sc-cell-l">' +
            esc(label) +
            '</div><div class="sc-cell-n" style="color:' +
            color +
            '">' +
            big +
            '</div><div class="sc-cell-s">' +
            esc(sub) +
            '</div><div class="sc-bar"><span style="width:' +
            w +
            '%;background:' +
            barCol +
            '"></span></div></div>'
        );
    }

    function crit(pct, color, title, desc) {
        return (
            '<div class="sc-card sc-crit"><div class="sc-crit-p" style="color:' +
            color +
            '">' +
            pct +
            '%</div><div class="sc-crit-t">' +
            esc(title) +
            '</div><div class="sc-crit-d">' +
            esc(desc) +
            '</div></div>'
        );
    }

    function prow(label, val, color, sub) {
        return (
            '<tr><td><div class="sc-pr-l">' +
            esc(label) +
            '</div>' +
            (sub ? '<div class="sc-pr-s">' + esc(sub) + '</div>' : '') +
            '</td><td class="sc-pr-v" style="color:' +
            color +
            '">' +
            val +
            '</td></tr>'
        );
    }

    function pcard(title, sub, rowsHtml) {
        return (
            '<div class="sc-card sc-pcard"><div class="sc-pc-h">' +
            esc(title) +
            '</div>' +
            (sub ? '<div class="sc-pc-s">' + esc(sub) + '</div>' : '') +
            '<table class="sc-ptable"><tbody>' +
            rowsHtml +
            '</tbody></table></div>'
        );
    }

    function funnelMetric(lab, pct, hint, pctClass) {
        var w = Math.min(100, Math.max(0, parseFloat(String(pct).replace(',', '.')) || 0));
        return (
            '<div class="sc-funnel-metric">' +
            '<div class="sc-funnel-metric__top">' +
            '<span class="sc-funnel-metric__lab">' + esc(lab) + '</span>' +
            '<span class="sc-funnel-metric__pct ' + (pctClass || '') + '">' + esc(pct) + '%</span>' +
            '</div>' +
            '<div class="sc-funnel-metric__bar"><span style="width:' + w + '%"></span></div>' +
            '<div class="sc-funnel-metric__hint">' + esc(hint) + '</div>' +
            '</div>'
        );
    }

    function funnelStep(icon, label, val) {
        return (
            '<div class="sc-funnel-step">' +
            '<div class="sc-funnel-trap">' +
            '<div class="sc-funnel-trap__ico">' + icon + '</div>' +
            '<div class="sc-funnel-trap__meta">' +
            '<div class="sc-funnel-trap__lab">' + esc(label) + '</div>' +
            '<div class="sc-funnel-trap__val">' + val + '</div>' +
            '</div></div></div>'
        );
    }

    function funnelBridge(rate) {
        return (
            '<div class="sc-funnel-bridge">' +
            '<div class="sc-funnel-bridge__flow" aria-hidden="true"><span></span><span></span><span></span></div>' +
            '<span class="sc-funnel-bridge__rate">' + esc(rate) + '%</span>' +
            '<span class="sc-funnel-bridge__chev">↓</span>' +
            '</div>'
        );
    }

    function renderFunnel(v) {
        var joinCls = Number(String(v.joinPct).replace(',', '.')) > 0 ? 'is-ok' : 'is-zero';
        var venteCls = Number(String(v.ventePct).replace(',', '.')) > 0 ? 'is-ok' : 'is-zero';
        var callPct = pc1(v.called, v.leadsReactives);
        var callCls = Number(String(callPct).replace(',', '.')) > 0 ? 'is-ok' : 'is-zero';
        return (
            '<div class="sc-card sc-funnel">' +
            '<div class="sc-funnel-head">' +
            '<div><h3 class="sc-funnel-title">Notre dispositif</h3></div>' +
            '<span class="sc-funnel-badge">' + nb(v.called) + ' numéros</span>' +
            '</div>' +
            '<div class="sc-funnel-viz">' +
            '<div class="sc-funnel-stack">' +
            funnelStep(icoSms(), 'Leads réactivés', nb(v.leadsReactives)) +
            funnelBridge(callPct) +
            funnelStep(icoPhone(), 'Ont rappelé', nb(v.called)) +
            funnelBridge(v.joinPct) +
            funnelStep(icoJoin(), 'Pris en charge', nb(v.joints)) +
            funnelBridge(v.ventePct) +
            funnelStep(icoCart(), 'Ventes', nb(v.ventes)) +
            '</div>' +
            '<div class="sc-funnel-side">' +
            funnelMetric('Leads réactivés', '100', nb(v.leadsReactives) + ' via webhook', v.leadsReactives ? 'is-ok' : 'is-zero') +
            funnelMetric('Leads qui ont rappelé', callPct, nb(v.called) + ' sur ' + nb(v.leadsReactives), callCls) +
            funnelMetric('Échange avec un agent', v.joinPct, nb(v.joints) + ' pris en charge', joinCls) +
            funnelMetric('Ventes confirmées', v.ventePct, nb(v.ventes) + ' ventes CC', venteCls) +
            '</div></div>' +
            '<div class="sc-nonpris"><div class="sc-np-ico">' + icoPhoneOff() + '</div>' +
            '<div><div class="sc-np-t">Leads non pris en charge</div>' +
            '<div class="sc-np-s">Ont rappelé sans échange abouti côté call center</div></div>' +
            '<div class="sc-np-n">' + nb(v.nonPris) + '</div></div>' +
            '</div>'
        );
    }

    function render(v) {
        var r = v.called || 1;
        var gap = '<span class="sc-gap">à brancher (CRM)</span>';
        var html = '';

        html += sect('#2E69FF', 'Campagne ' + v.fournisseur);
        html += '<div class="sc-kpis">';
        html += kpi(icoPeople(), 'rgba(46,105,255,0.15)', '#2E69FF', 'Leads traités', nb(v.liv), 'Avec enregistrement Concentrix');
        html += kpi(icoPhone(), 'rgba(14,165,233,0.12)', '#0284C7', 'Joignabilité', v.joiPct + '%', nb(v.joi) + ' leads pris en charge');
        html += kpi(icoCart(), 'rgba(22,163,74,0.12)', '#16a34a', 'Ventes', nb(v.ven), v.tvPct + '% taux de vente');
        html += '</div>';

        html += '<div class="sc-row2">';
        html += renderFunnel(v);
        html +=
            '<div class="sc-card sc-incr"><div class="sc-incr-h">Incrémentation campagne</div><div class="sc-incr-s">Points gagnés via Smart Convers × Concentrix</div>';
        html +=
            '<div class="sc-incr-box gr"><div class="sc-incr-l">↗ JOIGNABILITÉ</div><div class="sc-incr-n gr">+' +
            v.incrJoi +
            ' pt</div><div class="sc-incr-x">' +
            nb(v.joints) +
            ' pris en charge / ' +
            nb(v.liv) +
            ' traités</div></div>';
        html +=
            '<div class="sc-incr-box pu"><div class="sc-incr-l pu">◎ TAUX DE VENTE</div><div class="sc-incr-n pu">+' +
            v.incrTv +
            ' pt</div><div class="sc-incr-x">' +
            nb(v.vap) +
            ' ventes attribuables / ' +
            nb(v.liv) +
            ' traités</div></div></div>';
        html += '</div>';

        html += sect('#16a34a', 'Performance Call Center');
        html +=
            '<div class="sc-card sc-leads-banner"><span class="sc-leads-banner-title">Leads réactivés</span>' +
            '<span class="sc-leads-banner-sep">·</span>' +
            '<span class="sc-leads-banner-n">' +
            nb(v.leadsReactives) +
            '</span></div>';
        html +=
            '<div class="sc-card"><div class="sc-card-h">Répartition des ' +
            nb(v.nRec) +
            ' appels</div><div class="sc-card-s">De l\'appel entrant à la vente conclue</div><div class="sc-cells">';
        html += cell('APPELS', nb(v.nRec), 'chaque enregistrement = 1 appel', '#2E69FF', 100, '#2E69FF');
        html += cell(
            'NON PRIS EN CHARGE',
            pc1(v.nonPris, v.called) + '%',
            nb(v.nonPris) + ' leads',
            '#dc2626',
            r ? (v.nonPris / r) * 100 : 0,
            '#dc2626'
        );
        html += cell(
            'LEAD UNIQUE AYANT APPELÉ',
            nb(v.called),
            'numéros uniques',
            '#0891b2',
            v.nRec ? (v.called / v.nRec) * 100 : 0,
            '#0EA5E9'
        );
        html += cell(
            'CODIF ACCORD / VENTE',
            nb(v.ventes),
            'codifications accord vente',
            '#15803d',
            r ? (v.ventes / r) * 100 : 0,
            '#16a34a'
        );
        html += '</div></div>';

        html += '<div class="sc-sect-g">Critères clés (direction)</div>';
        html += '<div class="sc-crit-row">';
        html += crit(
            pc1(v.postureOk, v.postureN),
            '#16a34a',
            'Posture de réception',
            v.postureOk + '/' + v.postureN + " se présentent comme conseiller de l'opérateur, en posture d'appel entrant"
        );
        html += crit(
            pc1(v.offreOk, v.offreN),
            '#dc2626',
            "Accueil sans imposer l'offre",
            v.offreOk + '/' + v.offreN + " n'attaquent pas d'emblée avec l'offre low cost"
        );
        html += crit(
            pc1(v.champsRedemandes, v.champsN),
            '#d97706',
            'Champs du lead redemandés',
            v.champsRedemandes +
                '/' +
                v.champsN +
                ' redemandent des infos déjà connues (nom, CP, opérateur — vs CRM)'
        );
        html += crit(
            pc1(v.nonPris, v.called),
            '#dc2626',
            'Rebond mobile',
            nb(v.nonPris) + ' leads sur ' + nb(v.called) + ' ont rappelé sans échange abouti'
        );
        html += '</div>';

        html += sect('#2E69FF', 'Analyse des appels');
        html +=
            '<div class="sc-card"><div class="sc-card-h">Détail par numéro</div><div class="sc-card-s">Codification, dates, historiques et résumés</div>';
        html +=
            '<button type="button" class="sc-dl" id="erDlCsv">↓&nbsp; Télécharger Excel <span class="sc-dl-n">' +
            (v.analyseRows || []).length +
            ' numéros</span></button>';
        html += '<div class="sc-table-wrap"><table class="sc-data"><thead><tr>';
        ANALYSE_COLS.forEach(function (h) {
            html += '<th>' + h + '</th>';
        });
        html += '</tr></thead><tbody>';
        (v.analyseRows || []).slice(0, 100).forEach(function (row) {
            html += '<tr>';
            ANALYSE_FIELDS.forEach(function (field) {
                html += analyseCell(row, field);
            });
            html += '</tr>';
        });
        if (!(v.analyseRows || []).length) {
            html += '<tr><td colspan="' + ANALYSE_COLS.length + '" style="color:#9aa3b2;padding:16px;">Aucun enregistrement analysé pour cette période. Synchronisez Twilio puis configurez les critères.</td></tr>';
        }
        html += '</tbody></table></div>';
        html += '<div class="sc-card-foot">Source : Twilio + analyses locales Concentrix.</div></div>';

        html += sect('#2E69FF', 'Vue PROD');
        html += '<div class="sc-pgrid">';
        html += pcard(
            '① Réactivation — amont',
            '',
            prow('Leads traités (enregistrements)', nb(v.liv), '#334155') +
                prow('Welcome envoyés', v.welcomeEnvoyes != null ? nb(v.welcomeEnvoyes) : gap, '#94a3b8', 'Non branché CRM Concentrix') +
                (v.isGlobalWeek
                    ? prow('Campagnes survey de relance', nb(v.surveySet), '#0e7490') +
                      prow('Réponse survey', nb(v.surveyResp), '#15803d')
                    : '')
        );
        html += pcard(
            '② Appels & joignabilité',
            nb(v.called) + ' numéros · ' + nb(v.nRec) + ' enregistrements',
            prow('Enregistrements', nb(v.nRec), '#334155', '1 enregistrement = 1 appel capté') +
                prow('Enregistrements ≥ 300s', nb(v.n300), '#0e7490', pc1(v.n300, v.nRec) + ' % ≥ 5 min') +
                prow('Lead unique ayant appelé', nb(v.called), '#2E69FF', pc1(v.called, v.liv) + ' % des traités') +
                prow('dont pris en charge', nb(v.joints), '#15803d', pc1(v.joints, v.liv) + ' % des traités') +
                prow('Appelé ≥ 300s', nb(v.call300), '#0e7490', pc1(v.call300, v.called) + ' % des appelants') +
                prow('Vente CC — numéro unique', nb(v.ventes), '#15803d', pc1(v.ventes, v.called) + ' % appelants')
        );
        html += pcard(
            '③ 1er point de contact',
            nb(v.p1) + ' des ' + nb(v.ventes) + ' ventes',
            prow('Vente 1er contact', nb(v.p1), '#15803d') +
                prow('% sur appelants', pc1(v.p1, v.called) + ' %', '#2E69FF', v.p1 + ' / ' + v.called) +
                prow('% sur appelants ≥ 300s', pc1(v.p1, v.call300) + ' %', '#0e7490', v.p1 + ' / ' + v.call300)
        );
        html += pcard(
            '④ Réactivés via survey',
            '',
            prow('Répondu au SMS & appelé', gap, '#94a3b8') +
                prow('Pas répondu mais appelé', gap, '#94a3b8') +
                prow('Total via survey', gap, '#94a3b8')
        );
        html += pcard(
            '⑤ Activés via Welcome SMS',
            '',
            prow('Appelants (proxy enregistrements)', nb(v.welcomeCalled), '#0e7490', nb(v.welcomeVentes) + ' ventes') +
                prow('Vente — canal enregistrements', nb(v.welcomeVentes), '#15803d', 'sur ' + v.ventes + ' ventes')
        );
        html += '</div>';

        html += sect('#0EA5E9', 'Enregistrements bruts');
        html += '<div class="sc-card"><div class="sc-table-wrap"><table class="sc-data"><thead><tr>';
        ['Date', 'Téléphone', 'Durée', 'Statut pipeline', 'Codif'].forEach(function (h) {
            html += '<th>' + h + '</th>';
        });
        html += '</tr></thead><tbody id="erRecBody"></tbody></table></div></div>';

        html += sect('#7c3aed', 'Historique webhook réactivation');
        html +=
            '<div class="sc-card"><div class="sc-card-s">Chaque POST Databowl est journalisé. Alerte WhatsApp TextMeBot si OK ou échec.</div>';
        html += '<div class="sc-table-wrap"><table class="sc-data"><thead><tr>';
        ['Date', 'Résultat', 'HTTP', 'Lead', 'Campagne', 'Stockés', 'Erreur'].forEach(function (h) {
            html += '<th>' + h + '</th>';
        });
        html += '</tr></thead><tbody>';
        var calls = v.webhookCalls || [];
        if (!calls.length) {
            html +=
                '<tr><td colspan="7" style="color:#9aa3b2;padding:16px;">Aucun appel webhook pour l’instant.</td></tr>';
        } else {
            calls.forEach(function (c) {
                var when = c.received_at ? new Date(c.received_at).toLocaleString('fr-FR') : '—';
                var badge = c.ok
                    ? '<span style="color:#16a34a;font-weight:750;">OK</span>'
                    : '<span style="color:#dc2626;font-weight:750;">ÉCHEC</span>';
                html +=
                    '<tr><td>' +
                    esc(when) +
                    '</td><td>' +
                    badge +
                    '</td><td>' +
                    esc(c.http_status) +
                    '</td><td>' +
                    esc(c.lead_external_id != null ? c.lead_external_id : '—') +
                    '</td><td>' +
                    esc(c.campaign_external_id != null ? c.campaign_external_id : '—') +
                    '</td><td>' +
                    nb(c.stored) +
                    '</td><td>' +
                    esc(c.error || '—') +
                    '</td></tr>';
            });
        }
        html += '</tbody></table></div></div>';

        document.getElementById('erBody').classList.remove('sc-loading');
        document.getElementById('erBody').innerHTML = html;

        var recs = ((state.data || {}).reactivation || {}).recordings || [];
        var tbody = document.getElementById('erRecBody');
        if (tbody) {
            tbody.innerHTML = recs
                .slice()
                .reverse()
                .slice(0, 200)
                .map(function (r) {
                    return (
                        '<tr><td>' +
                        esc(r.date || '—') +
                        '</td><td class="font-mono">' +
                        esc(r.phone) +
                        '</td><td>' +
                        Math.round(r.duration_sec || 0) +
                        's</td><td>' +
                        esc(r.status || '') +
                        '</td><td>' +
                        esc(r.codif || '—') +
                        '</td></tr>'
                    );
                })
                .join('');
        }

        var dl = document.getElementById('erDlCsv');
        if (dl) {
            dl.addEventListener('click', function () {
                downloadCsv(v.analyseRows || []);
            });
        }
    }

    function downloadCsv(rows) {
        var lines = [ANALYSE_COLS.join(';')];
        rows.forEach(function (r) {
            lines.push(
                ANALYSE_FIELDS.map(function (field) {
                    var v = r[field];
                    if (v == null) return '';
                    return '"' + String(v).replace(/"/g, '""') + '"';
                }).join(';')
            );
        });
        var blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8' });
        var a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = 'analyse_appels_concentrix.csv';
        a.click();
    }

    function fillWeeks(weeks) {
        var sel = document.getElementById('erWeek');
        if (!sel) return;
        var cur = sel.value || 'all';
        sel.innerHTML = '<option value="all">Toutes les semaines</option>';
        (weeks || []).forEach(function (w) {
            var opt = document.createElement('option');
            opt.value = w.key;
            opt.textContent = w.label;
            sel.appendChild(opt);
        });
        if (cur && Array.prototype.some.call(sel.options, function (o) { return o.value === cur; })) {
            sel.value = cur;
        }
    }

    function loadDashboard() {
        var week = (document.getElementById('erWeek') || {}).value || 'all';
        var q = week && week !== 'all' ? '?week=' + encodeURIComponent(week) : '?week=all';
        return API.get('/admin/enregistrements/dashboard' + q).then(function (payload) {
            state.data = payload.data;
            state.view = payload.view;
            state.weeks = payload.weeks || [];
            fillWeeks(state.weeks);
            var p = (payload.data && payload.data.period) || {};
            var el = document.getElementById('erPeriod');
            if (el) {
                el.textContent =
                    (p.from && p.to ? p.from + ' → ' + p.to : 'Aucune donnée') +
                    (payload.data && payload.data.generated_at
                        ? ' · ' + new Date(payload.data.generated_at).toLocaleString('fr-FR')
                        : '');
            }
            render(payload.view);
        });
    }

    function bind() {
        var week = document.getElementById('erWeek');
        if (week) {
            week.addEventListener('change', function () {
                loadDashboard().catch(function (e) {
                    flash(e.message || 'Erreur', true);
                });
            });
        }
        var sync = document.getElementById('erSyncBtn');
        if (sync) {
            sync.addEventListener('click', function () {
                sync.disabled = true;
                API.post('/admin/enregistrements/sync?async=true', { process: true, limit: 50 })
                    .then(function () {
                        flash('Synchronisation Twilio lancée (analyse si prompts configurés)');
                        setTimeout(function () {
                            loadDashboard().catch(function () {});
                        }, 2500);
                    })
                    .catch(function (e) {
                        flash(e.message || 'Échec sync', true);
                    })
                    .finally(function () {
                        sync.disabled = false;
                    });
            });
        }
        var ref = document.getElementById('erRefreshBtn');
        if (ref) {
            ref.addEventListener('click', function () {
                loadDashboard().catch(function (e) {
                    flash(e.message || 'Erreur', true);
                });
            });
        }
    }

    document.addEventListener('DOMContentLoaded', function () {
        if (typeof checkAuth === 'function') checkAuth();
        bind();
        loadDashboard().catch(function (e) {
            document.getElementById('erBody').innerHTML =
                '<div class="sc-blank"><div class="b1">Impossible de charger le dashboard</div><div class="b2">' +
                esc(e.message || 'erreur') +
                '</div></div>';
        });
    });
})();
