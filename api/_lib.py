"""Shared library for the challenges API.

Used by both Vercel serverless handlers in this directory and by the local
dev server at the repo root.

Storage:
- Production: Upstash Redis REST API (env: KV_REST_API_URL/TOKEN or
  UPSTASH_REDIS_REST_URL/TOKEN)
- Local dev: data.json fallback at the repo root

Identity: anonymous session cookie (`sid`), one per device, lasts a year.
"""
import json
import os
import secrets
import urllib.request
import zoneinfo
from datetime import datetime, timedelta, date as Date
from http.cookies import SimpleCookie
from typing import Optional, Tuple

# ----- Domain -----
NYC = zoneinfo.ZoneInfo("America/New_York")
EPOCH = Date(2026, 1, 1)
LESSONS_PER_LEAGUE = 5

POOL = [
    {"id": "l1-a", "title": "Notice 3 thoughts your brain throws at you today", "mascot": "lesson-1-mascot.png"},
    {"id": "l1-b", "title": "Name your distractions out loud as they happen",   "mascot": "lesson-1-mascot.png"},
    {"id": "l2-a", "title": "Ask for support without apologizing",              "mascot": "lesson-2-mascot.png"},
    {"id": "l2-b", "title": "Say no to one request that doesn't serve you",     "mascot": "lesson-2-mascot.png"},
    {"id": "l3-a", "title": "List 3 things you did well this week",             "mascot": "lesson-3-mascot.png"},
    {"id": "l3-b", "title": "Use a strength to tackle a small task today",      "mascot": "lesson-3-mascot.png"},
    {"id": "l4-a", "title": "Pick one task and protect 25 focused minutes",     "mascot": "lesson-4-mascot.png"},
    {"id": "l4-b", "title": "Schedule a deep-work block for tomorrow",          "mascot": "lesson-4-mascot.png"},
    {"id": "l5-a", "title": "Spot one hidden focus thief today",                "mascot": "lesson-5-mascot.png"},
    {"id": "l5-b", "title": "Silence one notification that pulls you away",     "mascot": "lesson-5-mascot.png"},
    {"id": "l6-a", "title": "Take 5 deep breaths before your next task",        "mascot": "lesson-6-mascot.png"},
    {"id": "l6-b", "title": "Notice 3 things you can see, hear, and feel",      "mascot": "lesson-6-mascot.png"},
    {"id": "l7-a", "title": "Anchor a tiny habit to your morning coffee",       "mascot": "lesson-7-mascot.png"},
    {"id": "l7-b", "title": "Do the new habit for just 2 minutes today",        "mascot": "lesson-7-mascot.png"},
    {"id": "l8-a", "title": "Brain-dump every idea, then pick just one",        "mascot": "lesson-8-mascot.png"},
    {"id": "l8-b", "title": "Write a single sentence about your best idea",     "mascot": "lesson-8-mascot.png"},
    {"id": "l9-a", "title": "Ask 'why' three times for one decision today",     "mascot": "lesson-9-mascot.png"},
    {"id": "l9-b", "title": "Plan tomorrow's top 3 priorities tonight",         "mascot": "lesson-9-mascot.png"},
]


def nyc_today() -> Date:
    return datetime.now(NYC).date()


def challenge_for_date(d: Date) -> dict:
    return POOL[(d - EPOCH).days % len(POOL)]


def week_start(d: Date) -> Date:
    return d - timedelta(days=d.weekday())  # Monday


# ----- Sessions -----
COOKIE_NAME = "sid"


def parse_sid(cookie_header: Optional[str]) -> Optional[str]:
    if not cookie_header:
        return None
    c = SimpleCookie()
    try:
        c.load(cookie_header)
    except Exception:
        return None
    morsel = c.get(COOKIE_NAME)
    return morsel.value if morsel else None


def make_sid() -> str:
    return secrets.token_urlsafe(24)


def cookie_header_value(sid: str, secure: bool) -> str:
    parts = [
        f"{COOKIE_NAME}={sid}",
        "Path=/",
        "HttpOnly",
        "SameSite=Lax",
        "Max-Age=31536000",
    ]
    if secure:
        parts.append("Secure")
    return "; ".join(parts)


# ----- Storage -----
KV_URL = os.environ.get("KV_REST_API_URL") or os.environ.get("UPSTASH_REDIS_REST_URL")
KV_TOKEN = os.environ.get("KV_REST_API_TOKEN") or os.environ.get("UPSTASH_REDIS_REST_TOKEN")
LOCAL_DATA_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data.json",
)


def _has_kv() -> bool:
    return bool(KV_URL and KV_TOKEN)


def _kv_request(*command_parts) -> dict:
    """Run a Redis command via Upstash REST."""
    body = json.dumps(list(command_parts)).encode()
    req = urllib.request.Request(
        KV_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {KV_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


def _kv_key(sid: str) -> str:
    return f"sess:{sid}:completions"


def _load_local() -> dict:
    if not os.path.exists(LOCAL_DATA_FILE):
        return {"sessions": {}}
    try:
        with open(LOCAL_DATA_FILE) as f:
            return json.load(f)
    except Exception:
        return {"sessions": {}}


def _save_local(data: dict) -> None:
    tmp = LOCAL_DATA_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, LOCAL_DATA_FILE)


def get_completions(sid: str) -> dict:
    if _has_kv():
        try:
            res = _kv_request("GET", _kv_key(sid))
            raw = res.get("result")
            if not raw:
                return {}
            return json.loads(raw)
        except Exception:
            return {}
    data = _load_local()
    return data.get("sessions", {}).get(sid, {})


class StorageNotConfigured(RuntimeError):
    pass


def set_completion(sid: str, date_str: str, completed: bool) -> None:
    comps = get_completions(sid)
    if completed:
        comps[date_str] = True
    else:
        comps.pop(date_str, None)
    if _has_kv():
        _kv_request("SET", _kv_key(sid), json.dumps(comps))
        return
    if os.environ.get("VERCEL"):
        # File fallback can't work on Vercel's read-only filesystem.
        raise StorageNotConfigured(
            "KV is not configured. Connect Upstash KV under Storage in the "
            "Vercel dashboard and redeploy."
        )
    data = _load_local()
    sessions = data.setdefault("sessions", {})
    if comps:
        sessions[sid] = comps
    else:
        sessions.pop(sid, None)
    _save_local(data)


# ----- State -----
def compute_state(sid: str) -> dict:
    completions = get_completions(sid)
    today = nyc_today()
    today_str = today.isoformat()
    today_ch = challenge_for_date(today)
    completed_today = bool(completions.get(today_str))

    start = week_start(today)
    week = []
    d = start
    while d <= today:
        ds = d.isoformat()
        if completions.get(ds):
            ch = challenge_for_date(d)
            week.append({"date": ds, "title": ch["title"], "mascot": ch["mascot"]})
        d += timedelta(days=1)
    week.reverse()

    total = sum(1 for v in completions.values() if v)
    league = total // LESSONS_PER_LEAGUE + 1
    progress = total % LESSONS_PER_LEAGUE

    return {
        "today": today_str,
        "todayChallenge": today_ch,
        "completedToday": completed_today,
        "completedThisWeek": week,
        "league": league,
        "progress": progress,
        "total": total,
    }


# ----- HTTP helpers -----
def is_https(handler) -> bool:
    proto = (handler.headers.get("x-forwarded-proto") or "").lower()
    return proto == "https"


def get_or_create_sid(handler) -> Tuple[str, bool]:
    sid = parse_sid(handler.headers.get("Cookie"))
    if sid:
        return sid, False
    return make_sid(), True


def respond_json(handler, payload, *, sid: Optional[str] = None, set_sid: bool = False, status: int = 200) -> None:
    body = json.dumps(payload).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    if set_sid and sid:
        handler.send_header("Set-Cookie", cookie_header_value(sid, secure=is_https(handler)))
    handler.end_headers()
    handler.wfile.write(body)


def handle_state(handler) -> None:
    sid, is_new = get_or_create_sid(handler)
    state = compute_state(sid)
    respond_json(handler, state, sid=sid, set_sid=is_new)


def handle_toggle(handler, completed: bool) -> None:
    sid, is_new = get_or_create_sid(handler)
    try:
        set_completion(sid, nyc_today().isoformat(), completed)
    except StorageNotConfigured as e:
        respond_json(handler, {"error": str(e)}, sid=sid, set_sid=is_new, status=503)
        return
    state = compute_state(sid)
    respond_json(handler, state, sid=sid, set_sid=is_new)
