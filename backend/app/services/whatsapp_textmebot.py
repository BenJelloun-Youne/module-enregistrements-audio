"""Envoi WhatsApp via TextMeBot (usage perso / ton numéro).

Docs: https://textmebot.com/
Privé : ``send.php?recipient=+E164&apikey=...&text=...``
Groupe : ``send.php?group_info=INVITE_CODE&json=yes`` puis
         ``send.php?recipient=GROUPID@g.us&apikey=...&text=...&json=yes``

``TEXTMEBOT_ALLOWED_KINDS`` : ``*`` / vide = toutes les alertes.
Sinon liste (ex. cap,rafale,retry).

Le mode groupe s'ajoute au privé, il ne le remplace pas.
Si ``group_info`` échoue, l'erreur TextMeBot est loguée telle quelle :
pas de bascule silencieuse vers le privé.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional, Set, Tuple

logger = logging.getLogger(__name__)

ENABLED = os.getenv("TEXTMEBOT_ENABLED", "0").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
API_KEY = (os.getenv("TEXTMEBOT_APIKEY") or "").strip()
# Destinataire privé. Format international, ex. +33612345678
RECIPIENT = (os.getenv("TEXTMEBOT_RECIPIENT") or "").strip()
SEND_URL = (os.getenv("TEXTMEBOT_SEND_URL") or "https://api.textmebot.com/send.php").strip()
TIMEOUT_SECONDS = max(5, int(os.getenv("TEXTMEBOT_TIMEOUT_SECONDS", "20")))
# Limite taille message WhatsApp ~4096 ; on coupe proprement.
MAX_TEXT_LEN = max(500, int(os.getenv("TEXTMEBOT_MAX_TEXT_LEN", "3500")))
# kinds autorisés (virgules). *, all, vide = tout passer.
_KINDS_RAW = (os.getenv("TEXTMEBOT_ALLOWED_KINDS") or "*").strip().lower()
if _KINDS_RAW in ("", "*", "all", "any"):
    ALLOWED_KINDS: Set[str] = set()
else:
    ALLOWED_KINDS = {k.strip().lower() for k in _KINDS_RAW.split(",") if k.strip()}

GROUP_INVITE = (os.getenv("TEXTMEBOT_GROUP_INVITE") or "").strip()
GROUP_ID_CONFIG = (os.getenv("TEXTMEBOT_GROUP_ID") or "").strip()
_GROUP_ENABLED_RAW = (os.getenv("TEXTMEBOT_GROUP_ENABLED") or "").strip().lower()
if _GROUP_ENABLED_RAW in ("0", "false", "no", "off"):
    GROUP_ENABLED = False
elif _GROUP_ENABLED_RAW in ("1", "true", "yes", "on"):
    GROUP_ENABLED = True
else:
    GROUP_ENABLED = bool(GROUP_INVITE or GROUP_ID_CONFIG)

# Kinds autorisés pour le canal groupe uniquement (privé inchangé).
# Défaut : cap + rafale seulement.
_GROUP_KINDS_RAW = (os.getenv("TEXTMEBOT_GROUP_ALLOWED_KINDS") or "cap,rafale").strip().lower()
if _GROUP_KINDS_RAW in ("*", "all", "any"):
    GROUP_ALLOWED_KINDS: Optional[Set[str]] = None  # tous les kinds
elif not _GROUP_KINDS_RAW:
    GROUP_ALLOWED_KINDS = set()  # aucun → groupe désactivé côté kinds
else:
    GROUP_ALLOWED_KINDS = {
        k.strip().lower() for k in _GROUP_KINDS_RAW.split(",") if k.strip()
    }

_INVITE_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?chat\.whatsapp\.com/(?:invite/)?([A-Za-z0-9_-]{10,})",
    re.I,
)
_GROUP_JID_RE = re.compile(r"(\d+(?:-\d+)?)@g\.us", re.I)

_group_lock = threading.Lock()
# Sérialise TOUS les envois TextMeBot (privé + groupe, tous threads) :
# l'API impose ~8s entre deux messages ; sans ce lock, 2 CAP simultanés
# font échouer le groupe après un seul retry (« 8 sec. Delay needed »).
_send_lock = threading.Lock()
_group_id_cache: Optional[str] = None
_MAX_DELAY_RETRIES = max(1, int(os.getenv("TEXTMEBOT_MAX_DELAY_RETRIES", "5")))
# Lock fichier inter-processus (cron App + QC + RPC en parallèle).
_LOCK_PATH = (os.getenv("TEXTMEBOT_LOCK_PATH") or "/tmp/textmebot-send.lock").strip()


class _FileSendLock:
    """fcntl flock pour sérialiser les envois entre processus."""

    def __init__(self, path: str) -> None:
        self._path = path
        self._fh = None

    def __enter__(self):
        import fcntl

        self._fh = open(self._path, "a+", encoding="utf-8")
        fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        import fcntl

        try:
            if self._fh is not None:
                fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
                self._fh.close()
        except Exception:
            pass
        self._fh = None



def is_configured() -> bool:
    return bool(ENABLED and API_KEY and RECIPIENT)


def is_group_configured() -> bool:
    return bool(ENABLED and API_KEY and GROUP_ENABLED and (GROUP_INVITE or GROUP_ID_CONFIG))


def _kind_allowed(kind: Optional[str]) -> bool:
    if not ALLOWED_KINDS:
        return True
    return (kind or "").strip().lower() in ALLOWED_KINDS


def _group_kind_allowed(kind: Optional[str]) -> bool:
    """True si ce kind peut partir dans le groupe WhatsApp."""
    if GROUP_ALLOWED_KINDS is None:
        return True
    if not GROUP_ALLOWED_KINDS:
        return False
    return (kind or "").strip().lower() in GROUP_ALLOWED_KINDS


def extract_invite_code(raw: Optional[str]) -> str:
    """Extrait le code d'invitation WhatsApp (XXXX) depuis un lien ou un code nu."""
    s = (raw or "").strip()
    if not s:
        return ""
    m = _INVITE_URL_RE.search(s)
    if m:
        return m.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{10,}", s):
        return s
    return s.split("?")[0].rstrip("/").split("/")[-1].strip()


def _normalize_group_id(value: Optional[str]) -> str:
    s = (value or "").strip()
    if not s:
        return ""
    m = _GROUP_JID_RE.search(s)
    if m:
        return m.group(0)
    if re.fullmatch(r"\d+(?:-\d+)?", s):
        return f"{s}@g.us"
    return ""


def _safe_query(params: Dict[str, str]) -> str:
    shown = {k: ("***" if k.lower() == "apikey" else v) for k, v in params.items()}
    return urllib.parse.urlencode(shown)


def _http_get(params: Dict[str, str]) -> Tuple[int, str]:
    url = f"{SEND_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return int(getattr(resp, "status", 200) or 200), raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace") if e.fp else ""
        return int(e.code), raw
    except Exception as exc:
        logger.exception("[textmebot] HTTP GET échoué: %s", type(exc).__name__)
        return 0, f"{type(exc).__name__}: {exc}"


def _parse_json_body(raw: str) -> Optional[Any]:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return None
    return None


def _walk_group_id(obj: Any) -> str:
    if isinstance(obj, str):
        return _normalize_group_id(obj)
    if isinstance(obj, dict):
        for key in (
            "groupid",
            "groupId",
            "group_id",
            "GroupID",
            "id",
            "jid",
            "recipient",
            "comment",
            "data",
        ):
            found = _walk_group_id(obj.get(key))
            if found:
                return found
        for val in obj.values():
            found = _walk_group_id(val)
            if found:
                return found
    elif isinstance(obj, (list, tuple)):
        for val in obj:
            found = _walk_group_id(val)
            if found:
                return found
    return ""


def _delay_seconds(raw: str) -> int:
    m = re.search(r"(\d+)\s*sec", raw or "", flags=re.I)
    if m and "delay" in (raw or "").lower():
        return max(8, int(m.group(1)))
    return 0


def resolve_group_id() -> Optional[str]:
    """Convertit le lien/code d'invitation en Group ID WhatsApp via group_info.

    Ne tombe jamais en privé : en cas d'échec, logue la réponse brute et retourne None.
    """
    global _group_id_cache
    if _group_id_cache:
        logger.info("[textmebot] group_info cache Group ID=%s", _group_id_cache)
        return _group_id_cache

    configured = _normalize_group_id(GROUP_ID_CONFIG)
    if configured:
        logger.info(
            "[textmebot] group_info ignoré (TEXTMEBOT_GROUP_ID déjà fourni) Group ID=%s",
            configured,
        )
        _group_id_cache = configured
        return configured

    invite_code = extract_invite_code(GROUP_INVITE)
    logger.info(
        "[textmebot] group_info invite_raw=%s invite_code=%s",
        GROUP_INVITE,
        invite_code,
    )
    if not invite_code:
        logger.error(
            "[textmebot] group_info échec: aucun invite code (TEXTMEBOT_GROUP_INVITE vide)"
        )
        return None

    # TextMeBot attend le code (ou l'URL) DANS le paramètre group_info :
    #   send.php?group_info=HA1f6t…&apikey=…&json=yes
    # PAS group_info=yes&invite=… (ça renvoie "Wrong Invitation Link").
    params = {
        "apikey": API_KEY,
        "json": "yes",
        "group_info": invite_code,
    }
    logger.info(
        "[textmebot] group_info appel GET %s?%s",
        SEND_URL,
        _safe_query(params),
    )
    status, raw = _http_get(params)
    logger.info(
        "[textmebot] group_info réponse HTTP=%s body=%s",
        status,
        (raw or "").strip()[:2000],
    )

    wait = _delay_seconds(raw)
    if wait:
        logger.warning("[textmebot] group_info délai TextMeBot %ss — nouvel essai", wait)
        time.sleep(wait + 1)
        logger.info(
            "[textmebot] group_info retry GET %s?%s",
            SEND_URL,
            _safe_query(params),
        )
        status, raw = _http_get(params)
        logger.info(
            "[textmebot] group_info retry réponse HTTP=%s body=%s",
            status,
            (raw or "").strip()[:2000],
        )

    parsed = _parse_json_body(raw)
    if isinstance(parsed, dict):
        st = parsed.get("status")
        st_err = str(st).lower() == "error" or st is False
        if st_err:
            logger.error(
                "[textmebot] group_info échec TextMeBot HTTP=%s status=%s comment=%s body=%s",
                status,
                parsed.get("status"),
                parsed.get("comment") or parsed.get("msg"),
                (raw or "").strip()[:2000],
            )
            return None

    group_id = ""
    if isinstance(parsed, dict):
        group_id = _normalize_group_id(
            str(parsed.get("group_id") or parsed.get("groupid") or "")
        )
    if not group_id and parsed is not None:
        group_id = _walk_group_id(parsed)
    if not group_id:
        group_id = _normalize_group_id(raw)
    if not group_id:
        logger.error(
            "[textmebot] group_info échec: pas de Group ID @g.us dans la réponse "
            "HTTP=%s body=%s",
            status,
            (raw or "").strip()[:2000],
        )
        return None

    logger.info("[textmebot] group_info Group ID obtenu=%s", group_id)
    _group_id_cache = group_id
    return group_id


def _send_one(
    recipient: str,
    body: str,
    *,
    kind: Optional[str],
    channel: str,
    json_mode: bool,
) -> bool:
    params: Dict[str, str] = {
        "recipient": recipient,
        "apikey": API_KEY,
        "text": body,
    }
    if json_mode:
        params["json"] = "yes"

    # Appelé sous _send_lock (voir send_whatsapp_text).
    status, raw = 0, ""
    for attempt in range(1, _MAX_DELAY_RETRIES + 1):
        logger.info(
            "[textmebot] tentative d'envoi channel=%s kind=%s attempt=%s/%s recipient=%s GET %s?%s",
            channel,
            kind or "none",
            attempt,
            _MAX_DELAY_RETRIES,
            recipient,
            SEND_URL,
            _safe_query(params),
        )
        status, raw = _http_get(params)
        logger.info(
            "[textmebot] réponse TextMeBot channel=%s HTTP=%s body=%s",
            channel,
            status,
            (raw or "").strip()[:2000],
        )
        wait = _delay_seconds(raw)
        if wait and attempt < _MAX_DELAY_RETRIES:
            logger.warning(
                "[textmebot] délai TextMeBot %ss channel=%s — nouvel essai %s/%s",
                wait,
                channel,
                attempt + 1,
                _MAX_DELAY_RETRIES,
            )
            time.sleep(wait + 1)
            continue
        break

    parsed = _parse_json_body(raw)
    if isinstance(parsed, dict):
        st = str(parsed.get("status") or "").lower()
        if st == "error":
            logger.error(
                "[textmebot] envoi %s échoué status=%s comment=%s",
                channel,
                parsed.get("status"),
                parsed.get("comment"),
            )
            return False
        if st == "success":
            logger.info(
                "[textmebot] WhatsApp OK channel=%s kind=%s recipient=%s",
                channel,
                kind or "none",
                recipient,
            )
            return True

    ok = 200 <= status < 300
    if ok:
        logger.info(
            "[textmebot] WhatsApp OK channel=%s kind=%s recipient=%s",
            channel,
            kind or "none",
            recipient,
        )
    else:
        logger.warning(
            "[textmebot] WhatsApp HTTP non-OK channel=%s: %s %s",
            channel,
            status,
            (raw or "")[:300],
        )
    return ok


def _send_group(body: str, *, kind: Optional[str]) -> bool:
    with _group_lock:
        group_id = resolve_group_id()
        if not group_id:
            logger.error(
                "[textmebot] envoi groupe annulé: pas de Group ID "
                "(pas de bascule automatique vers le privé)"
            )
            return False
        return _send_one(
            group_id,
            body,
            kind=kind,
            channel="group",
            json_mode=True,
        )


def _private_wanted(kind: Optional[str]) -> bool:
    """Privé uniquement si le kind est autorisé ET ne part pas déjà au groupe."""
    if not is_configured() or not _kind_allowed(kind):
        return False
    if is_group_configured() and _group_kind_allowed(kind):
        return False
    return True


def _group_wanted(kind: Optional[str]) -> bool:
    return is_group_configured() and _group_kind_allowed(kind)


def _dispatch_body(body: str, *, kind: Optional[str]) -> bool:
    """Envoi immédiat (privé et/ou groupe). À appeler sous flock."""
    want_private = _private_wanted(kind)
    want_group = _group_wanted(kind)
    if not want_private and not want_group:
        return False
    private_ok = False
    if want_private:
        private_ok = _send_one(
            RECIPIENT,
            body,
            kind=kind,
            channel="private",
            json_mode=False,
        )
    elif is_configured() and _kind_allowed(kind) and want_group:
        logger.info(
            "[textmebot] skip privé kind=%s (déjà envoyé au groupe)",
            kind or "none",
        )
    if want_group:
        return _send_group(body, kind=kind) or private_ok
    return private_ok


# ---------------------------------------------------------------------------
# File d'attente simple (partagée App / QC / RPC) + worker + retry
# ---------------------------------------------------------------------------
import uuid
from pathlib import Path

QUEUE_DIR = Path(
    (os.getenv("TEXTMEBOT_QUEUE_DIR") or "/tmp/textmebot-queue").strip()
)
MIN_GAP_SECONDS = max(8, int(os.getenv("TEXTMEBOT_MIN_GAP_SECONDS", "9")))
QUEUE_MAX_ATTEMPTS = max(1, int(os.getenv("TEXTMEBOT_QUEUE_MAX_ATTEMPTS", "20")))

_worker_lock = threading.Lock()
_worker_started = False


def _queue_dirs() -> tuple[Path, Path, Path]:
    pending = QUEUE_DIR / "pending"
    failed = QUEUE_DIR / "failed"
    pending.mkdir(parents=True, exist_ok=True)
    failed.mkdir(parents=True, exist_ok=True)
    return pending, QUEUE_DIR / "sending", failed


def _normalize_body(text: str, prefix: Optional[str]) -> str:
    body = (prefix + "\n" if prefix else "") + (text or "").strip()
    if len(body) > MAX_TEXT_LEN:
        body = body[: MAX_TEXT_LEN - 20] + "\n…(tronqué)"
    return body


def enqueue_whatsapp_text(
    text: str,
    *,
    prefix: Optional[str] = None,
    kind: Optional[str] = None,
) -> bool:
    """Ajoute un message à la file d'attente et réveille le worker."""
    if not _private_wanted(kind) and not _group_wanted(kind):
        logger.info(
            "[textmebot] skip kind=%s (privé=%s groupe=%s)",
            (kind or "none"),
            _kind_allowed(kind),
            _group_kind_allowed(kind) if is_group_configured() else False,
        )
        return False
    body = _normalize_body(text, prefix)
    if not body:
        return False

    pending, _, _ = _queue_dirs()
    job_id = f"{time.time():.6f}-{uuid.uuid4().hex[:10]}"
    path = pending / f"{job_id}.json"
    tmp = pending / f".{job_id}.tmp"
    payload = {
        "id": job_id,
        "text": body,
        "kind": kind,
        "attempts": 0,
        "created_at": time.time(),
    }
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
    logger.info(
        "[textmebot] queue +1 id=%s kind=%s pending≈%s",
        job_id,
        kind or "none",
        len(list(pending.glob("*.json"))),
    )
    _ensure_queue_worker()
    return True


def _pop_oldest_job() -> Optional[tuple[Path, dict]]:
    pending, sending_dir, _ = _queue_dirs()
    sending_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(pending.glob("*.json"), key=lambda p: p.name)
    if not files:
        return None
    src = files[0]
    dst = sending_dir / src.name
    try:
        src.replace(dst)
    except FileNotFoundError:
        return None
    try:
        data = json.loads(dst.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("[textmebot] job illisible %s", dst)
        try:
            dst.unlink(missing_ok=True)
        except Exception:
            pass
        return None
    return dst, data


def _requeue_job(sending_path: Path, data: dict, *, failed: bool = False) -> None:
    pending, _, failed_dir = _queue_dirs()
    name = sending_path.name
    target = (failed_dir if failed else pending) / name
    try:
        sending_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        sending_path.replace(target)
    except Exception:
        logger.exception("[textmebot] requeue échoué %s", name)


def _process_one_job() -> bool:
    """Prend 1 job, envoie, retry/requeue. True s'il y avait un job."""
    with _FileSendLock(_LOCK_PATH), _send_lock:
        popped = _pop_oldest_job()
        if not popped:
            return False
        sending_path, data = popped
        kind = data.get("kind")
        body = data.get("text") or ""
        attempts = int(data.get("attempts") or 0) + 1
        data["attempts"] = attempts
        logger.info(
            "[textmebot] queue send id=%s kind=%s attempt=%s/%s",
            data.get("id"),
            kind or "none",
            attempts,
            QUEUE_MAX_ATTEMPTS,
        )
        ok = False
        try:
            ok = _dispatch_body(body, kind=kind)
        except Exception:
            logger.exception("[textmebot] queue dispatch crash")
            ok = False

        if ok:
            try:
                sending_path.unlink(missing_ok=True)
            except Exception:
                pass
            logger.info("[textmebot] queue OK id=%s", data.get("id"))
        elif attempts >= QUEUE_MAX_ATTEMPTS:
            _requeue_job(sending_path, data, failed=True)
            logger.error(
                "[textmebot] queue ABANDON id=%s après %s essais",
                data.get("id"),
                attempts,
            )
        else:
            _requeue_job(sending_path, data, failed=False)
            logger.warning(
                "[textmebot] queue RETRY plus tard id=%s attempt=%s",
                data.get("id"),
                attempts,
            )
        # Respecte le rythme TextMeBot entre deux messages
        time.sleep(MIN_GAP_SECONDS)
        return True


def _queue_worker_loop() -> None:
    logger.info("[textmebot] worker file d'attente démarré dir=%s", QUEUE_DIR)
    idle_rounds = 0
    while True:
        try:
            had = _process_one_job()
        except Exception:
            logger.exception("[textmebot] worker erreur")
            had = False
            time.sleep(MIN_GAP_SECONDS)
        if had:
            idle_rounds = 0
            continue
        idle_rounds += 1
        # S'arrête après ~30s sans job (le prochain enqueue relance)
        if idle_rounds >= 6:
            break
        time.sleep(5)


def _ensure_queue_worker() -> None:
    global _worker_started
    with _worker_lock:
        if _worker_started:
            return
        _worker_started = True
        threading.Thread(
            target=_queue_worker_main, daemon=True, name="textmebot-queue"
        ).start()


def _queue_worker_main() -> None:
    global _worker_started
    try:
        _queue_worker_loop()
    finally:
        with _worker_lock:
            _worker_started = False


def flush_textmebot_queue(*, max_seconds: float = 900.0) -> int:
    """Vide la file (utile en fin de cron silence). Retourne le nb de jobs traités."""
    _ensure_queue_worker()
    deadline = time.time() + max(1.0, max_seconds)
    processed = 0
    pending, _, _ = _queue_dirs()
    while time.time() < deadline:
        n = len(list(pending.glob("*.json")))
        sending = QUEUE_DIR / "sending"
        n_send = len(list(sending.glob("*.json"))) if sending.exists() else 0
        if n == 0 and n_send == 0:
            break
        # Aide au drain dans ce process (en plus du worker)
        if _process_one_job():
            processed += 1
        else:
            time.sleep(1)
    return processed


def send_whatsapp_text(
    text: str,
    *,
    prefix: Optional[str] = None,
    kind: Optional[str] = None,
) -> bool:
    """Met en file d'attente (envoi dès que TextMeBot est libre)."""
    return enqueue_whatsapp_text(text, prefix=prefix, kind=kind)


def send_whatsapp_text_async(
    text: str,
    *,
    prefix: Optional[str] = None,
    kind: Optional[str] = None,
) -> bool:
    """Alias file d'attente (non bloquant)."""
    return enqueue_whatsapp_text(text, prefix=prefix, kind=kind)
