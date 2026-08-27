"""Agrégats dashboard Réactivation Concentrix — à partir des tables audio locales (pas BQ)."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session, joinedload

from app.models_audio import AudioRecording
from app.services.reactivation_webhook_notify import list_reactivation_calls
from app.services.reactivation_webhook_service import count_reactivation_leads

CONV = {"Vente", "Pre-vente", "Refus", "Deja Orange", "Rappel perso", "Probleme fiche"}
VENTE_CODIFS = {"Vente"}


def _pc1(a: int, b: int) -> str:
    if not b:
        return "0"
    return f"{(a / b) * 100:.1f}".replace(".", ",")


def _nb(x: int | float) -> str:
    return f"{int(round(x)):,}".replace(",", " ")


def _week_of(d: str) -> Optional[str]:
    day = (d or "")[:10]
    if not day:
        return None
    try:
        dt = datetime.strptime(day, "%Y-%m-%d")
    except ValueError:
        return None
    # lundi ISO
    mon = dt.toordinal() - ((dt.weekday()) % 7)
    return datetime.fromordinal(mon).strftime("%Y-%m-%d")


def _week_label(monday: str, dmin: str, dmax: str) -> str:
    mois = {5: "mai", 6: "juin", 7: "juil.", 8: "août", 9: "sept.", 10: "oct.", 11: "nov.", 12: "déc.", 1: "janv.", 2: "févr.", 3: "mars", 4: "avr."}
    mon = datetime.strptime(monday, "%Y-%m-%d")
    s = max(mon, datetime.strptime(dmin, "%Y-%m-%d"))
    e = min(datetime.fromordinal(mon.toordinal() + 6), datetime.strptime(dmax, "%Y-%m-%d"))
    sm, em = s.month, e.month
    if sm == em:
        return f"{s.day} – {e.day} {mois.get(em, em)}"
    return f"{s.day} {mois.get(sm, sm)} – {e.day} {mois.get(em, em)}"


def build_dashboard_payload(db: Session, week: Optional[str] = None) -> dict[str, Any]:
    rows = (
        db.query(AudioRecording)
        .options(joinedload(AudioRecording.analysis))
        .order_by(AudioRecording.recorded_at.asc().nullslast())
        .all()
    )

    byday: dict[str, dict[str, int]] = defaultdict(lambda: {"liv": 0, "joi": 0, "ven": 0})
    ours_map: dict[str, dict[str, Any]] = {}
    recordings_meta: list[dict[str, Any]] = []
    criteres: list[dict[str, Any]] = []
    analyse_rows_map: dict[str, dict[str, Any]] = {}

    for r in rows:
        day = ""
        if r.recorded_at:
            day = r.recorded_at.astimezone().strftime("%Y-%m-%d") if r.recorded_at.tzinfo else r.recorded_at.strftime("%Y-%m-%d")
        phone = (r.phone or "").strip() or f"sid:{r.recording_sid}"
        a = r.analysis
        codif = (a.codification if a else None) or "?"
        duree = float(r.duration_sec or 0)

        recordings_meta.append(
            {
                "phone": phone,
                "date": day,
                "duration_sec": duree,
                "codif": codif,
                "deroule": a.deroule if a else None,
                "recording_id": r.id,
                "status": r.status,
            }
        )

        is_joint = False
        is_vente = False
        if a:
            if (a.codification or "") in CONV:
                is_joint = True
            if a.vente_conclue is True or (a.codification or "") in VENTE_CODIFS:
                is_vente = True
            crit = a.criteres_result if isinstance(a.criteres_result, dict) else {}
            if crit:
                criteres.append(
                    {
                        "date": day,
                        "posture_ok": crit.get("posture_ok"),
                        "offre_ok": crit.get("offre_ok"),
                        "champs_redemandes": crit.get("champs_redemandes"),
                    }
                )
        elif duree >= 20:
            # sans analyse : proxy durée (aligné MIN_CONV)
            is_joint = True

        # byday : 1 lead unique / jour pour liv ; joi/ven si joint/vente
        if day:
            # on compte les recordings comme activité ; liv = phones uniques via ours
            byday[day]["liv"] += 0  # rempli après

        o = ours_map.get(phone)
        if not o:
            o = {
                "ph": phone,
                "d": day,
                "jt": 0,
                "vcc": 0,
                "vap": 0,
                "p1": 0,
                "src": "welcome",
            }
            ours_map[phone] = o
        if day and (not o["d"] or day < o["d"]):
            o["d"] = day
        if is_joint:
            o["jt"] = 1
        if is_vente:
            o["vcc"] = 1
            o["vap"] = 1  # sans CRM : vente audio = vente attribuable

        ar = analyse_rows_map.get(phone)
        if not ar:
            ar = {
                "ph": phone,
                "vente_cc": False,
                "joint": False,
                "canal": "welcome",
                "date_1er": day,
                "nb_enreg": 0,
                "semaine": _week_of(day) or "",
                "derniere_codif_cc": "",
                "date_derniere_codif_cc": "",
                "derniere_codif_sc": codif,
                "date_dernier_appel": day,
                "hist_cc": "",
                "hist_sc": codif,
                "resume1": (a.deroule if a else "") or "",
                "resume2": "",
                "resume3": "",
            }
            analyse_rows_map[phone] = ar
        ar["nb_enreg"] += 1
        if day and (not ar["date_1er"] or day < ar["date_1er"]):
            ar["date_1er"] = day
            ar["semaine"] = _week_of(day) or ""
        if day and (not ar["date_dernier_appel"] or day >= ar["date_dernier_appel"]):
            ar["date_dernier_appel"] = day
            ar["derniere_codif_sc"] = codif
            if a and a.deroule:
                ar["resume1"] = a.deroule
        if is_joint:
            ar["joint"] = True
        if is_vente:
            ar["vente_cc"] = True
        hist = ar.get("hist_sc") or ""
        if codif and codif != "?" and codif not in hist.split(" | "):
            ar["hist_sc"] = (hist + " | " + codif).strip(" |") if hist else codif

    # byday depuis ours
    for o in ours_map.values():
        d = o["d"]
        if not d:
            continue
        byday[d]["liv"] += 1
        if o["jt"]:
            byday[d]["joi"] += 1
        if o["vcc"]:
            byday[d]["ven"] += 1

    byday_out = {k: dict(v) for k, v in sorted(byday.items())}
    ours = list(ours_map.values())
    analyse_rows = list(analyse_rows_map.values())

    days = sorted(byday_out.keys())
    weeks = []
    if days:
        keys = sorted({_week_of(d) for d in days if _week_of(d)})
        weeks = [{"key": k, "label": _week_label(k, days[0], days[-1])} for k in keys if k]

    leads_reactives = count_reactivation_leads(db)
    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "period": {"from": days[0] if days else "", "to": days[-1] if days else ""},
        "byday": byday_out,
        "ours": ours,
        "reactivation": {
            "fournisseur": "Concentrix",
            "survey_campaign_phones": 0,
            "survey_responses": 0,
            "welcome_envoyes": None,
            "leads_reactives": leads_reactives,
            "webhook_calls": list_reactivation_calls(db, limit=80),
            "recordings": recordings_meta,
            "criteres": criteres,
            "analyse_rows": analyse_rows,
        },
    }
    view = compute_reactivation(data, week)
    return {"data": data, "view": view, "weeks": weeks}


def compute_reactivation(data: dict[str, Any], week: Optional[str]) -> dict[str, Any]:
    def keep(d: str) -> bool:
        if not week or week == "all":
            return True
        return _week_of(d) == week

    rx = data["reactivation"]
    bydays = [(d, b) for d, b in data["byday"].items() if keep(d)]
    liv = joi = ven = 0
    for _, b in bydays:
        liv += b["liv"]
        joi += b["joi"]
        ven += b["ven"]

    ours = [o for o in data["ours"] if keep(o.get("d") or "")]
    call = {o["ph"] for o in ours}
    join = {o["ph"] for o in ours if o.get("jt") == 1}
    vcc = {o["ph"] for o in ours if o.get("vcc") == 1}
    vap = {o["ph"] for o in ours if o.get("vap") == 1}
    p1 = {o["ph"] for o in ours if o.get("p1") == 1}

    recs = [r for r in (rx.get("recordings") or []) if keep(r.get("date") or "")]
    phones300 = {r["phone"] for r in recs if (r.get("duration_sec") or 0) >= 300 and r.get("phone")}
    call300 = len([p for p in call if p in phones300])
    n300 = len([r for r in recs if (r.get("duration_sec") or 0) >= 300])

    crit = [c for c in (rx.get("criteres") or []) if keep(c.get("date") or "")]

    def rate(vals):
        defined = [v for v in vals if v is True or v is False]
        return sum(1 for v in defined if v), len(defined)

    po_ok, po_n = rate([c.get("posture_ok") for c in crit])
    of_ok, of_n = rate([c.get("offre_ok") for c in crit])
    ch_ok, ch_n = rate([c.get("champs_redemandes") for c in crit])

    f_r, f_j, f_v = len(call), len(join), len(vcc)
    f_np = f_r - f_j
    n_vap = len(vap)

    analyse_rows = [r for r in (rx.get("analyse_rows") or []) if keep(r.get("date_1er") or "")]

    return {
        "fournisseur": rx.get("fournisseur") or "Concentrix",
        "liv": liv,
        "joi": joi,
        "ven": ven,
        "joiPct": _pc1(joi, liv),
        "tvPct": _pc1(ven, liv),
        "called": f_r,
        "joints": f_j,
        "ventes": f_v,
        "nonPris": f_np,
        "joinPct": _pc1(f_j, f_r),
        "ventePct": _pc1(f_v, f_j),
        "incrJoi": _pc1(f_j, liv),
        "incrTv": _pc1(n_vap, liv),
        "vap": n_vap,
        "p1": len(p1),
        "call300": call300,
        "nRec": len(recs),
        "n300": n300,
        "surveySet": rx.get("survey_campaign_phones") or 0,
        "surveyResp": rx.get("survey_responses") or 0,
        "welcomeEnvoyes": rx.get("welcome_envoyes"),
        "surveyCalled": 0,
        "surveyCalledResp": 0,
        "surveyCalledNoResp": 0,
        "surveyVentes": 0,
        "surveyCalledRespVentes": 0,
        "surveyCalledNoRespVentes": 0,
        "welcomeCalled": f_r,
        "welcomeVentes": f_v,
        "leadsReactives": int(rx.get("leads_reactives") or 0),
        "webhookCalls": rx.get("webhook_calls") or [],
        "postureOk": po_ok,
        "postureN": po_n,
        "offreOk": of_ok,
        "offreN": of_n,
        "champsRedemandes": ch_ok,
        "champsN": ch_n,
        "analyseRows": analyse_rows,
        "isGlobalWeek": not week or week == "all",
        "_fmt": {"nb": True},
    }
