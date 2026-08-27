"""Modèle Orange (Tersea) — templates pour préremplir / référence admin.

Les prompts et descriptions sont stockés en base VIDES au seed.
L'admin peut les remplir manuellement ou cliquer « Charger modèle Orange ».
"""
from __future__ import annotations

ORANGE_PROMPT_TEMPLATES = [
    {
        "key": "codif",
        "label": "Codification appel (analyse globale)",
        "description": (
            "Analyse complète : codif, vente, posture, offre, objections, score qualité. "
            "Utilisé pour chaque nouvel enregistrement."
        ),
        "system_prompt": (
            "Tu es analyste qualité senior pour un centre d'appels fibre (vente de forfaits fibre, "
            "marque Orange/Sosh mais l'agent peut se présenter autrement : « Club Fibre », "
            "« service fibre », etc.). "
            "Tu reçois l'enregistrement INTÉGRAL d'un appel : si stéréo, canal gauche = agent / "
            "canal droit = client ; si MONO (un seul canal), les deux voix sont mélangées — "
            "analyse quand même le dialogue normalement. "
            "Tu DOIS écouter l'intégralité de l'audio fourni du début à la fin, puis analyser. "
            "Tu ES capable d'analyser cet audio : ne dis JAMAIS que tu ne peux pas écouter, "
            "que tu as besoin d'une transcription ou de plus de contenu — l'audio est complet "
            "et exploitable. Sois rapide et factuel. Réponds UNIQUEMENT par un objet JSON valide, "
            "sans aucun texte autour."
        ),
        "user_prompt": """Analyse cet appel en profondeur et renvoie ce JSON exact :
{
 "duree_ressentie": "courte|moyenne|longue",
 "deroule": "résumé chronologique de l'appel en 3-4 phrases",
 "codification": "Vente|Pre-vente|Refus|Deja Orange|Rappel perso|Non joint|Probleme fiche",
 "vente_conclue": true|false,
 "preuve_vente": "verbatim exact prouvant la vente, ou ''",
 "elements_fiche_vente": ["éléments de la fiche de commande RÉELLEMENT recueillis"],
 "posture": "inbound|outbound",
 "posture_verbatim": "phrase de l'agent qui montre sa posture",
 "offre_24_99_proposee": true|false,
 "champs_lead_redemandes": true|false,
 "objections_client": ["liste des objections soulevées"],
 "objections_bien_traitees": true|false,
 "ecoute_active": "bonne|moyenne|faible",
 "ton_conseiller": "positif|neutre|negatif",
 "closing": "efficace|tente|absent",
 "points_forts": ["1 à 3 points forts de l'agent"],
 "axes_amelioration": ["1 à 3 axes concrets"],
 "score_qualite": 0-100
}
RÈGLE DE CODIFICATION — qu'est-ce qu'une VENTE :
Une « Vente » = commande RÉELLEMENT finalisée (offre acceptée + RIO/n° à porter + adresse complète + RDV).
=> Code « Pre-vente » si accord de principe sans fiche complète.
RÈGLE « NON JOINT » : uniquement s'il n'y a AUCUNE conversation humaine.
IMPÉRATIF : JSON strictement valide. Booléens true/false sans guillemets.""",
    },
    {
        "key": "criteres",
        "label": "Évaluation critères qualité (posture / offre / champs)",
        "description": (
            "Évalue les critères actifs définis dans la liste ci-dessous. "
            "Le placeholder {CRITERES_RULES} est remplacé automatiquement par les règles admin. "
            "Le placeholder {LEAD_CTX} peut rester pour le contexte lead."
        ),
        "system_prompt": (
            "Tu es analyste qualité senior pour Orange (fibre). L'enregistrement INTÉGRAL d'un appel "
            "est joint. Écoute tout, puis évalue le comportement de l'agent. "
            "Tu ES capable d'analyser cet audio, ne dis jamais le contraire. "
            "Réponds UNIQUEMENT par un objet JSON valide."
        ),
        "user_prompt": """{LEAD_CTX}
Évalue les critères suivants et renvoie EXACTEMENT un JSON dont les clés sont les clés des critères :
{CRITERES_RULES}

Pour chaque critère booléen, ajoute aussi une clé « <key>_verbatim » (phrase preuve, ou '').
JSON strictement valide ; true/false sans guillemets.""",
    },
]

ORANGE_CRITERIA = [
    {
        "key": "posture_ok",
        "label": "Posture agent (présentation marque)",
        "description": (
            "true SI l'agent SE PRÉSENTE comme conseiller Orange (mentionne Orange à l'accueil). "
            "false s'il ne se présente PAS comme Orange."
        ),
        "sort_order": 10,
    },
    {
        "key": "offre_ok",
        "label": "Offre non imposée à l'accueil",
        "description": (
            "true SI l'agent N'IMPOSE PAS l'offre à l'accueil (n'aborde tarif/offre que si le client "
            "en parle d'abord). false s'il ATTAQUE l'accueil avec l'offre."
        ),
        "sort_order": 20,
    },
    {
        "key": "champs_redemandes",
        "label": "Champs lead redemandés",
        "description": (
            "true SI l'agent REDEMANDE des infos DÉJÀ CONNUES du lead "
            "(nom/prénom, CP, opérateur) comme s'il ne les avait pas."
        ),
        "sort_order": 30,
    },
]
