from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import asyncio, html, json, re, time
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os, logging, uuid, random, secrets
import bcrypt, httpx
from jose import jwt, JWTError
from urllib.parse import urlencode, urlparse
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
from datetime import datetime, timezone, timedelta

try:
    from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionRequest
except ImportError:
    StripeCheckout = None
    CheckoutSessionRequest = None

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

DEFAULT_DB_NAME = "readyup_arena"


def _resolve_db_name(mongo_url: str) -> str:
    explicit_name = os.environ.get("DB_NAME", "").strip()
    if explicit_name:
        return explicit_name

    parsed = urlparse(mongo_url)
    uri_db_name = parsed.path.lstrip("/").strip()
    if uri_db_name:
        return uri_db_name

    return DEFAULT_DB_NAME


mongo_url = os.environ.get("MONGO_URL", "").strip()
if not mongo_url:
    raise RuntimeError("MONGO_URL is required. Add your MongoDB Atlas connection string in backend/.env or the deployment environment.")

db_name = _resolve_db_name(mongo_url)
client = AsyncIOMotorClient(mongo_url)
db = client[db_name]

import redis_state as rs
from seed_data import seed_all
from cs2 import build_cs2_router
from bracket import build_bracket_router
from email_service import send_email, reset_email_html

app = FastAPI(title="ReadyUp Arena API")
api_router = APIRouter(prefix="/api")

DEFAULT_FRONTEND_URL = "http://localhost:3000"
DEFAULT_CORS_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"
DEV_JWT_SECRET = "readyup-arena-dev-secret-change-in-prod"


def env_flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_text(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def parse_csv_env(name: str, default: str) -> list[str]:
    raw = os.environ.get(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]

# ============= AUTH =============
JWT_SECRET = os.environ.get("JWT_SECRET", DEV_JWT_SECRET)
JWT_ALGO = "HS256"
JWT_EXP_HOURS = 24 * 7
bearer = HTTPBearer(auto_error=False)

class RegisterReq(BaseModel):
    pseudo: str = Field(min_length=3, max_length=24)
    email: EmailStr
    password: str = Field(min_length=8)
    country: str = "FR"

class LoginReq(BaseModel):
    email: EmailStr
    password: str


class ProfileUpdateReq(BaseModel):
    pseudo: Optional[str] = Field(default=None, min_length=3, max_length=24)
    email: Optional[EmailStr] = None
    gender: Optional[str] = Field(default=None, max_length=32)
    age: Optional[int] = Field(default=None, ge=13, le=99)
    bio: Optional[str] = Field(default=None, max_length=280)
    custom_avatar_url: Optional[str] = Field(default=None, max_length=600)


class UserPublic(BaseModel):
    id: str
    pseudo: str
    email: str
    country: str
    gender: Optional[str] = None
    age: Optional[int] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    custom_avatar_url: Optional[str] = None
    steam_avatar_url: Optional[str] = None
    level: int
    xp: int
    elo: int
    platform_elo: int
    faceit_elo: Optional[int] = None
    premier_rating: Optional[int] = None
    premier_status: Optional[str] = None
    kills_30d: Optional[int] = None
    deaths_30d: Optional[int] = None
    kdr: Optional[float] = None
    rank_cs2: Optional[str] = None
    role: Optional[str] = None
    reliability: int = 50
    stats_last_sync_at: Optional[str] = None
    stats_provider: Optional[str] = None
    stats_profile_url: Optional[str] = None
    stats_sources: dict[str, Optional[str]] = Field(default_factory=dict)
    steam_profile_url: Optional[str] = None
    leetify_profile_url: Optional[str] = None
    faceit_profile_url: Optional[str] = None
    faceit_nickname: Optional[str] = None
    faceit_level: Optional[int] = None
    faceit_winrate: Optional[float] = None
    faceit_headshots: Optional[float] = None
    faceit_total_matches: Optional[int] = None
    faceit_kills_per_round: Optional[float] = None
    faceit_recent_matches: Optional[int] = None
    aim_rating: Optional[float] = None
    utility_rating: Optional[float] = None
    positioning_rating: Optional[float] = None
    opening_duels_rating: Optional[float] = None
    clutching_rating: Optional[float] = None
    steam_verified: bool
    created_at: str
    is_admin: bool = False
    team_id: Optional[str] = None
    team_role: Optional[str] = None

def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt(rounds=12)).decode()

def verify_password(pw: str, h: str) -> bool:
    try: return bcrypt.checkpw(pw.encode(), h.encode())
    except Exception: return False

def make_token(user_id: str, pseudo: str) -> str:
    payload = {"sub": user_id, "pseudo": pseudo,
               "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXP_HOURS),
               "iat": datetime.now(timezone.utc)}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)

async def journal(event_type: str, user_id: Optional[str], meta: dict = None):
    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()), "event_type": event_type, "user_id": user_id,
        "meta": meta or {}, "created_at": datetime.now(timezone.utc).isoformat()})

ADMIN_EMAILS = {e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()}
SEED_ADMIN_EMAIL = env_text("SEED_ADMIN_EMAIL").lower()
EFFECTIVE_ADMIN_EMAILS = ADMIN_EMAILS | ({SEED_ADMIN_EMAIL} if SEED_ADMIN_EMAIL else set())

def is_admin_email(email: str) -> bool:
    return (email or "").lower() in EFFECTIVE_ADMIN_EMAILS

def _compute_kdr(doc: dict) -> Optional[float]:
    kills = doc.get("kills_30d")
    deaths = doc.get("deaths_30d")
    if isinstance(kills, (int, float)) and isinstance(deaths, (int, float)) and deaths > 0:
        return round(float(kills) / float(deaths), 2)
    fallback = doc.get("kdr")
    if isinstance(fallback, (int, float)):
        return round(float(fallback), 2)
    return None


def _stats_sources(doc: dict) -> dict:
    provider = doc.get("stats_provider")
    return {
        "platform": "ReadyUp Arena",
        "faceit": (provider or "FACEIT") if doc.get("faceit_elo") is not None else None,
        "premier": (provider or "Valve Premier") if doc.get("premier_rating") is not None or doc.get("premier_status") else None,
        "kdr": (provider or "CS gameplay sample") if _compute_kdr(doc) is not None else None,
    }


def _public_stats_payload(doc: dict) -> dict:
    platform_elo = int(doc.get("platform_elo", doc.get("elo", 1000)))
    custom_avatar_url = doc.get("custom_avatar_url")
    steam_avatar_url = doc.get("steam_avatar_url")
    return {
        "elo": platform_elo,
        "platform_elo": platform_elo,
        "avatar_url": custom_avatar_url or steam_avatar_url,
        "custom_avatar_url": custom_avatar_url,
        "steam_avatar_url": steam_avatar_url,
        "faceit_elo": doc.get("faceit_elo"),
        "premier_rating": doc.get("premier_rating"),
        "premier_status": doc.get("premier_status"),
        "kills_30d": doc.get("kills_30d"),
        "deaths_30d": doc.get("deaths_30d"),
        "kdr": _compute_kdr(doc),
        "rank_cs2": doc.get("rank_cs2"),
        "role": doc.get("role"),
        "reliability": int(doc.get("reliability", 50)),
        "stats_last_sync_at": doc.get("stats_last_sync_at"),
        "stats_provider": doc.get("stats_provider"),
        "stats_profile_url": doc.get("stats_profile_url"),
        "steam_profile_url": doc.get("steam_profile_url"),
        "leetify_profile_url": doc.get("leetify_profile_url"),
        "faceit_profile_url": doc.get("faceit_profile_url"),
        "faceit_nickname": doc.get("faceit_nickname"),
        "faceit_level": doc.get("faceit_level"),
        "faceit_winrate": doc.get("faceit_winrate"),
        "faceit_headshots": doc.get("faceit_headshots"),
        "faceit_total_matches": doc.get("faceit_total_matches"),
        "faceit_kills_per_round": doc.get("faceit_kills_per_round"),
        "faceit_recent_matches": doc.get("faceit_recent_matches"),
        "aim_rating": doc.get("aim_rating"),
        "utility_rating": doc.get("utility_rating"),
        "positioning_rating": doc.get("positioning_rating"),
        "opening_duels_rating": doc.get("opening_duels_rating"),
        "clutching_rating": doc.get("clutching_rating"),
        "stats_sources": _stats_sources(doc),
    }


def user_to_public(u: dict) -> dict:
    return {"id": u["id"], "pseudo": u["pseudo"], "email": u["email"],
            "country": u.get("country","FR"), "level": u.get("level",1),
            "gender": u.get("gender"), "age": u.get("age"), "bio": u.get("bio"),
            "xp": u.get("xp",0), **_public_stats_payload(u),
            "steam_verified": u.get("steam_verified", False),
            "created_at": u["created_at"],
            "is_admin": is_admin_email(u.get("email")),
            "team_id": u.get("team_id"),
            "team_role": u.get("team_role")}

async def get_current_user(creds: HTTPAuthorizationCredentials = Depends(bearer)):
    if not creds: raise HTTPException(401, "Token requis")
    try: payload = jwt.decode(creds.credentials, JWT_SECRET, algorithms=[JWT_ALGO])
    except JWTError: raise HTTPException(401, "Token invalide ou expiré")
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
    if not user: raise HTTPException(401, "Utilisateur introuvable")
    return user

async def get_admin_user(user=Depends(get_current_user)):
    if not is_admin_email(user.get("email")):
        raise HTTPException(403, "Accès réservé aux administrateurs")
    return user

@api_router.post("/auth/register", response_model=UserPublic)
async def register(req: RegisterReq, request: Request):
    existing = await db.users.find_one({"$or": [{"email": req.email.lower()}, {"pseudo": req.pseudo}]})
    if existing: raise HTTPException(409, "Email ou pseudo déjà utilisé")
    user = {
        "id": str(uuid.uuid4()), "pseudo": req.pseudo, "email": req.email.lower(),
        "password_hash": hash_password(req.password), "country": req.country,
        "gender": None, "age": None, "bio": None,
        "custom_avatar_url": None, "steam_avatar_url": None,
        "level": 1, "xp": 0, "elo": 1000, "platform_elo": 1000,
        "faceit_elo": None, "premier_rating": None, "premier_status": None,
        "kills_30d": None, "deaths_30d": None, "kdr": None,
        "rank_cs2": None, "role": "Polyvalent", "reliability": 50,
        "stats_last_sync_at": None,
        "steam_verified": False, "steam_id": None,
        "team_id": None, "team_role": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "ip": request.client.host if request.client else None,
    }
    await db.users.insert_one(user)
    await journal("user_register", user["id"], {"pseudo": req.pseudo, "email": req.email.lower()})
    return user_to_public(user)

LOGIN_ATTEMPTS = {}  # ip -> [(timestamp, ...)]
LOGIN_MAX = 5
LOGIN_WINDOW_SEC = 900  # 15 min

def _rate_limit_login(ip: str):
    now = datetime.now(timezone.utc).timestamp()
    attempts = [t for t in LOGIN_ATTEMPTS.get(ip, []) if now - t < LOGIN_WINDOW_SEC]
    if len(attempts) >= LOGIN_MAX:
        oldest = min(attempts); wait = int(LOGIN_WINDOW_SEC - (now - oldest))
        raise HTTPException(429, f"Trop d'essais. Réessayez dans {wait}s.")
    attempts.append(now); LOGIN_ATTEMPTS[ip] = attempts

@api_router.post("/auth/login")
async def login(req: LoginReq, request: Request):
    ip = request.client.host if request.client else "unknown"
    _rate_limit_login(ip)
    user = await db.users.find_one({"email": req.email.lower()})
    if not user or not verify_password(req.password, user["password_hash"]):
        await journal("login_failed", None, {"email": req.email.lower(), "ip": ip})
        raise HTTPException(401, "Email ou mot de passe incorrect")
    LOGIN_ATTEMPTS.pop(ip, None)  # reset on success
    token = make_token(user["id"], user["pseudo"])
    await journal("login_success", user["id"], {"ip": ip})
    return {"token": token, "user": user_to_public(user)}

@api_router.get("/auth/me", response_model=UserPublic)
async def me(user=Depends(get_current_user)):
    return user_to_public(user)


@api_router.patch("/profile/me", response_model=UserPublic)
async def update_my_profile(req: ProfileUpdateReq, user=Depends(get_current_user)):
    updates = {}
    provided_fields = req.model_fields_set

    if "pseudo" in provided_fields and req.pseudo is not None and req.pseudo != user.get("pseudo"):
        existing = await db.users.find_one({"pseudo": req.pseudo, "id": {"$ne": user["id"]}}, {"_id": 0, "id": 1})
        if existing:
            raise HTTPException(409, "Pseudo déjà utilisé")
        updates["pseudo"] = req.pseudo

    if "email" in provided_fields and req.email is not None:
        email = req.email.lower()
        if email != user.get("email"):
            existing = await db.users.find_one({"email": email, "id": {"$ne": user["id"]}}, {"_id": 0, "id": 1})
            if existing:
                raise HTTPException(409, "Email déjà utilisé")
            updates["email"] = email

    if "gender" in provided_fields:
        updates["gender"] = req.gender.strip() if req.gender else None
    if "age" in provided_fields:
        updates["age"] = req.age
    if "bio" in provided_fields:
        updates["bio"] = req.bio.strip() if req.bio else None
    if "custom_avatar_url" in provided_fields:
        updates["custom_avatar_url"] = req.custom_avatar_url.strip() if req.custom_avatar_url else None

    if not updates:
        return user_to_public(user)

    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.users.update_one({"id": user["id"]}, {"$set": updates})
    updated_user = await db.users.find_one({"id": user["id"]}, {"_id": 0, "password_hash": 0})
    await journal("profile_updated", user["id"], {"fields": sorted(updates.keys())})
    return user_to_public(updated_user)


EXTERNAL_STATS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,fr;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

SYNC_MANAGED_FIELDS = (
    "faceit_elo",
    "premier_rating",
    "premier_status",
    "kills_30d",
    "deaths_30d",
    "kdr",
    "stats_provider",
    "stats_profile_url",
    "steam_profile_url",
    "leetify_profile_url",
    "faceit_profile_url",
    "faceit_nickname",
    "faceit_level",
    "faceit_winrate",
    "faceit_headshots",
    "faceit_total_matches",
    "faceit_kills_per_round",
    "faceit_recent_matches",
    "aim_rating",
    "utility_rating",
    "positioning_rating",
    "opening_duels_rating",
    "clutching_rating",
)


def _managed_stats_defaults() -> dict:
    return {field: None for field in SYNC_MANAGED_FIELDS}


def _coerce_int(value) -> Optional[int]:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(round(value))
    cleaned = re.sub(r"[^\d\-]", "", str(value))
    if cleaned in {"", "-"}:
        return None
    try:
        return int(cleaned)
    except ValueError:
        return None


def _coerce_float(value) -> Optional[float]:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    match = re.search(r"-?\d+(?:[.,]\d+)?", str(value))
    if not match:
        return None
    try:
        return round(float(match.group(0).replace(",", ".")), 2)
    except ValueError:
        return None


def _extract_cswat_object(raw_html: str, needle: str) -> Optional[dict]:
    idx = raw_html.find(needle)
    if idx == -1:
        return None
    start = raw_html.rfind("{", 0, idx)
    if start == -1:
        return None
    depth = 0
    for pos in range(start, len(raw_html)):
        char = raw_html[pos]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                snippet = html.unescape(raw_html[start:pos + 1]).replace('\\"', '"')
                try:
                    return json.loads(snippet)
                except json.JSONDecodeError:
                    return None
    return None


def _extract_cswat_premier_tile(raw_html: str) -> tuple[Optional[int], Optional[str]]:
    section_match = re.search(
        r'id="S:f"(?P<section>.*?)(?:id="S:d"|id="S:7"|id="S:10"|id="cswatch-skill-rating")',
        raw_html,
        re.IGNORECASE | re.DOTALL,
    )
    if not section_match:
        image_match = re.search(r'%2Fpremier_rating%2F(\d+)\.png', raw_html, re.IGNORECASE)
        status_match = re.search(r'alt="Unrated"', raw_html, re.IGNORECASE)
        dash_match = re.search(r'>\s*---\s*<', raw_html)
        if image_match and (status_match or dash_match):
            return _coerce_int(image_match.group(1)), "unrated"
        if status_match or dash_match:
            return None, "unrated"
        if image_match:
            return _coerce_int(image_match.group(1)), "rated"
        return None, None

    section = html.unescape(section_match.group("section"))
    rating_match = re.search(r'alt="Rating\s+([\d,]+)"', section, re.IGNORECASE)
    rating_value = _coerce_int(rating_match.group(1)) if rating_match else None
    if re.search(r'alt="Unrated"', section, re.IGNORECASE) or re.search(r">\s*---\s*<", section):
        return rating_value, "unrated"
    if rating_value is None:
        return None, None

    return rating_value, "rated"


def _parse_cswat_stats(raw_html: str, steam_id: str) -> dict:
    updates = _managed_stats_defaults()
    updates["stats_provider"] = "CSWAT"
    updates["stats_profile_url"] = f"https://cswat.ch/stats/{steam_id}"
    updates["leetify_profile_url"] = f"https://leetify.com/public/profile/{steam_id}"

    steam_wrapper = _extract_cswat_object(raw_html, "steamData")
    steam_data = (steam_wrapper or {}).get("steamData") or {}
    steam_name = str(steam_data.get("name") or "").strip()
    if steam_name:
        updates["_steam_display_name"] = steam_name[:24]
    steam_avatar_hash = str(steam_data.get("avatar") or "").strip()
    if steam_avatar_hash:
        updates["steam_avatar_url"] = f"https://avatars.steamstatic.com/{steam_avatar_hash}_full.jpg"
    if steam_data.get("profileurl"):
        updates["steam_profile_url"] = steam_data.get("profileurl")

    faceit_wrapper = _extract_cswat_object(raw_html, "faceitData")
    faceit_data = (faceit_wrapper or {}).get("faceitData") or {}
    if faceit_data.get("success"):
        cs2_game = ((faceit_data.get("game") or {}).get("cs2") or {})
        cs2_recent = ((faceit_data.get("recentStats") or {}).get("cs2") or {})
        nickname = faceit_data.get("nickname")
        recent_kdr = _coerce_float(cs2_recent.get("averageKDRatio"))
        all_time_kdr = _coerce_float(cs2_game.get("average_kd_ratio"))
        updates.update({
            "faceit_elo": _coerce_int(cs2_game.get("elo")),
            "faceit_nickname": nickname,
            "faceit_level": _coerce_int(cs2_game.get("level")),
            "faceit_profile_url": f"https://www.faceit.com/en/players/{nickname}" if nickname else None,
            "faceit_winrate": _coerce_float(cs2_recent.get("winrate")) or _coerce_float(cs2_game.get("win_rate")),
            "faceit_headshots": _coerce_float(cs2_recent.get("averageHeadshotPercent")) or _coerce_float(cs2_game.get("average_headshots")),
            "faceit_total_matches": _coerce_int(cs2_game.get("matches")) or _coerce_int(cs2_recent.get("totalMatches")),
            "faceit_kills_per_round": _coerce_float(cs2_recent.get("averageKRRatio")),
            "faceit_recent_matches": _coerce_int(cs2_recent.get("totalMatches")),
            "kdr": recent_kdr if recent_kdr is not None else all_time_kdr,
        })

    leetify_wrapper = _extract_cswat_object(raw_html, "leetifyProfile")
    leetify_data = (leetify_wrapper or {}).get("leetifyProfile") or {}
    leetify_ratings = (leetify_data.get("rating") or {})
    leetify_ranks = (leetify_data.get("ranks") or {})
    premier_tile_rating, premier_tile_status = _extract_cswat_premier_tile(raw_html)
    if leetify_data.get("success") and not leetify_data.get("error"):
        if updates.get("kdr") is None:
            updates["kdr"] = _coerce_float(leetify_data.get("kill_death_ratio"))
        updates.update({
            "premier_rating": _coerce_int((leetify_wrapper or {}).get("premierRank")) or _coerce_int(leetify_ranks.get("premier")),
            "aim_rating": _coerce_float(leetify_ratings.get("aim")),
            "utility_rating": _coerce_float(leetify_ratings.get("utility")),
            "positioning_rating": _coerce_float(leetify_ratings.get("positioning")),
            "opening_duels_rating": _coerce_float(leetify_ratings.get("opening")),
            "clutching_rating": _coerce_float(leetify_ratings.get("clutch")),
        })

    if updates.get("premier_rating") is None and premier_tile_rating is not None and premier_tile_status != "unrated":
        updates["premier_rating"] = premier_tile_rating
    if updates.get("premier_rating") is not None:
        updates["premier_status"] = "rated"
    elif premier_tile_status:
        updates["premier_status"] = premier_tile_status

    has_any_stats = any(
        updates.get(field) is not None
        for field in (
            "faceit_elo",
            "faceit_level",
            "kdr",
            "premier_rating",
            "premier_status",
            "aim_rating",
            "utility_rating",
            "positioning_rating",
            "opening_duels_rating",
            "clutching_rating",
            "steam_profile_url",
        )
    )
    if not has_any_stats:
        raise ValueError("Aucune statistique publique exploitable trouvée pour ce Steam ID.")

    return updates


def _extract_leetify_premier_rating(payload: dict) -> tuple[Optional[int], Optional[str]]:
    games = payload.get("games") or []
    premier_games = []
    for game in games:
        if not isinstance(game, dict):
            continue
        if not game.get("isCs2"):
            continue
        skill_level = _coerce_int(game.get("skillLevel"))
        if skill_level is None or skill_level <= 0:
            continue
        data_source = str(game.get("dataSource") or "").strip().lower()
        rank_type = _coerce_int(game.get("rankType"))
        if data_source == "matchmaking" or rank_type == 11:
            premier_games.append(game)

    if not premier_games:
        return None, None

    latest_game = max(premier_games, key=lambda game: str(game.get("gameFinishedAt") or ""))
    return _coerce_int(latest_game.get("skillLevel")), "rated"


async def _fetch_leetify_profile_stats(client_http: httpx.AsyncClient, steam_id: str) -> dict:
    response = await client_http.get(f"https://api.leetify.com/api/profile/id/{steam_id}")
    if response.status_code >= 400:
        return {}

    payload = response.json()
    if not isinstance(payload, dict):
        return {}

    updates = {}
    premier_rating, premier_status = _extract_leetify_premier_rating(payload)
    if premier_rating is not None:
        updates["premier_rating"] = premier_rating
    if premier_status:
        updates["premier_status"] = premier_status
    return updates


async def _fetch_external_stats_for_steam_id(steam_id: str) -> dict:
    profile_url = f"https://cswat.ch/stats/{steam_id}"
    async with httpx.AsyncClient(headers=EXTERNAL_STATS_HEADERS, follow_redirects=True, timeout=20) as client_http:
        response = await client_http.get(profile_url)
        leetify_updates = await _fetch_leetify_profile_stats(client_http, steam_id)
    if response.status_code >= 400:
        raise RuntimeError(f"CSWAT a répondu {response.status_code}")
    updates = _parse_cswat_stats(response.text, steam_id)
    if leetify_updates.get("premier_rating") is not None:
        updates["premier_rating"] = leetify_updates["premier_rating"]
    if leetify_updates.get("premier_status"):
        updates["premier_status"] = leetify_updates["premier_status"]
    return updates


@api_router.post("/stats/sync/me", response_model=UserPublic)
async def sync_my_stats(user=Depends(get_current_user)):
    steam_id = (user.get("steam_id") or "").strip()
    if not steam_id or not steam_id.isdigit():
        raise HTTPException(400, "Compte Steam non lié. Connectez-vous avec Steam avant la synchro.")

    try:
        updates = await _fetch_external_stats_for_steam_id(steam_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    except Exception as exc:
        logger.warning("external stats sync failed for steam_id=%s: %s", steam_id, exc)
        raise HTTPException(502, "Impossible de synchroniser les stats externes pour le moment.")

    steam_display_name = updates.pop("_steam_display_name", None)
    if steam_display_name and str(user.get("pseudo") or "").startswith("Steam_"):
        taken = await db.users.find_one(
            {"pseudo": steam_display_name, "id": {"$ne": user["id"]}},
            {"_id": 0, "id": 1},
        )
        updates["pseudo"] = steam_display_name if not taken else f"{steam_display_name[:19]}_{steam_id[-4:]}"
    updates["stats_last_sync_at"] = datetime.now(timezone.utc).isoformat()
    await db.users.update_one({"id": user["id"]}, {"$set": updates})
    updated_user = await db.users.find_one({"id": user["id"]}, {"_id": 0, "password_hash": 0})
    await journal("stats_sync", user["id"], {"steam_id": steam_id, "provider": updates.get("stats_provider")})
    return user_to_public(updated_user)

@api_router.post("/auth/logout")
async def logout(user=Depends(get_current_user)):
    await journal("logout", user["id"], {})
    return {"ok": True}

@api_router.get("/auth/audit", dependencies=[Depends(get_current_user)])
async def my_audit(user=Depends(get_current_user)):
    logs = await db.audit_logs.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(50)
    return logs

# ---------- Password reset (Resend email) ----------
class ForgotReq(BaseModel):
    email: EmailStr

class ResetReq(BaseModel):
    token: str
    new_password: str = Field(min_length=8)

@api_router.post("/auth/forgot-password")
async def forgot_password(req: ForgotReq):
    user = await db.users.find_one({"email": req.email.lower()})
    # Always return ok to avoid leaking which emails exist
    if user:
        token = secrets.token_urlsafe(32)
        await db.password_resets.insert_one({
            "id": token, "user_id": user["id"], "used": False,
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat()})
        reset_url = f"{_frontend_base()}/reset-password?token={token}"
        try:
            await send_email(user["email"], "ReadyUp Arena — Réinitialisation du mot de passe",
                             reset_email_html(user["pseudo"], reset_url))
        except Exception:
            pass
        await journal("password_reset_requested", user["id"], {})
    return {"ok": True, "message": "Si un compte existe, un email de réinitialisation a été envoyé."}

@api_router.post("/auth/reset-password")
async def reset_password(req: ResetReq):
    pr = await db.password_resets.find_one({"id": req.token})
    if not pr or pr.get("used"):
        raise HTTPException(400, "Lien de réinitialisation invalide ou déjà utilisé")
    if datetime.fromisoformat(pr["expires_at"]) < datetime.now(timezone.utc):
        raise HTTPException(400, "Lien de réinitialisation expiré")
    await db.users.update_one({"id": pr["user_id"]}, {"$set": {"password_hash": hash_password(req.new_password)}})
    await db.password_resets.update_one({"id": req.token}, {"$set": {"used": True, "used_at": datetime.now(timezone.utc).isoformat()}})
    await journal("password_reset_completed", pr["user_id"], {})
    return {"ok": True, "message": "Mot de passe réinitialisé. Vous pouvez vous connecter."}


# ---------- Feature flags / config ----------
@api_router.get("/config")
async def get_config():
    stripe_enabled = env_flag("FEATURE_STRIPE_DONATIONS", True) and bool(STRIPE_API_KEY)
    return {
        "app_name": "ReadyUp Arena",
        "tagline": "Formez votre équipe. Entrez dans l'arène. Devenez champion.",
        "feature_steam_auth": env_flag("FEATURE_STEAM_AUTH", True),
        "feature_twitch": env_flag("FEATURE_TWITCH", True),
        "feature_stripe": stripe_enabled,
        "feature_paypal": env_flag("FEATURE_PAYPAL", True),
        "feature_csstats": env_flag("FEATURE_CSSTATS", True),
        "twitch_channel": os.environ.get("TWITCH_CHANNEL", "esl_csgo"),
    }

@app.get("/health/live")
async def live_health():
    return {"status": "ok"}


@app.get("/health/ready")
async def ready_health():
    mongo_ok = True
    redis_ok = True

    try:
        await db.command("ping")
    except Exception:
        mongo_ok = False

    try:
        redis_ok = await rs.ping()
    except Exception:
        redis_ok = False

    healthy = mongo_ok and redis_ok
    payload = {
        "status": "ok" if healthy else "degraded",
        "services": {
            "mongo": "ok" if mongo_ok else "error",
            "redis": "ok" if redis_ok else "error",
        },
    }
    return JSONResponse(status_code=200 if healthy else 503, content=payload)


@app.get("/health")
async def health():
    return await ready_health()

# ---------- Catalogue data (MongoDB-backed) ----------
TOURNAMENT_STATES = ["open", "registering", "starting", "live", "closed"]
ALLOWED_TRANSITIONS = {
    "open": ["registering", "closed"],
    "registering": ["starting", "open", "closed"],
    "starting": ["live", "closed"],
    "live": ["closed"],
    "closed": [],
}

def _clean(doc: dict) -> dict:
    return {k: v for k, v in doc.items() if k != "_id"}


def _parse_iso_datetime(value: str, field_name: str) -> str:
    raw = (value or "").strip()
    if not raw:
        raise HTTPException(400, f"{field_name} est requis")
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(400, f"{field_name} doit être une date ISO valide")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _normalise_string_list(values: Optional[List[str]]) -> list[str]:
    if not values:
        return []
    return [item.strip() for item in values if item and item.strip()]


def _active_announcement(doc: dict, now_iso: str) -> bool:
    if not doc.get("is_active", True):
        return False
    starts_at = doc.get("starts_at")
    ends_at = doc.get("ends_at")
    if starts_at and starts_at > now_iso:
        return False
    if ends_at and ends_at < now_iso:
        return False
    return True


def _remaining_slots(max_entries: Optional[int], current_entries: int) -> Optional[int]:
    if max_entries is None or max_entries <= 0:
        return None
    return max(max_entries - current_entries, 0)


class TournamentAdminReq(BaseModel):
    name: str = Field(min_length=3, max_length=80)
    organizer: str = Field(min_length=2, max_length=64)
    format: str = Field(min_length=2, max_length=24)
    mode: str = Field(min_length=2, max_length=64)
    capacity: int = Field(ge=2, le=256)
    status: str = Field(default="open")
    starts_at: str
    prize: str = Field(default="Récompense à confirmer", max_length=120)
    region: str = Field(default="EU", min_length=2, max_length=24)
    level_min: int = Field(default=1, ge=0, le=100)
    image_color: str = Field(default="#FF4600", min_length=4, max_length=16)
    description: str = Field(default="", max_length=4000)
    maps: List[str] = Field(default_factory=list)
    rules: List[str] = Field(default_factory=list)


class NewsAdminReq(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    excerpt: str = Field(min_length=8, max_length=400)
    date: str
    body: str = Field(default="", max_length=4000)


class AnnouncementAdminReq(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    body: str = Field(min_length=8, max_length=4000)
    kind: str = Field(default="info", min_length=2, max_length=24)
    priority: int = Field(default=1, ge=1, le=5)
    is_active: bool = True
    cta_label: str = Field(default="", max_length=40)
    cta_url: str = Field(default="", max_length=400)
    starts_at: Optional[str] = None
    ends_at: Optional[str] = None


class ContestAdminReq(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    summary: str = Field(min_length=8, max_length=280)
    body: str = Field(min_length=8, max_length=4000)
    reward_label: str = Field(default="", max_length=120)
    max_entries: int = Field(default=250, ge=1, le=100000)
    is_active: bool = True
    banner_color: str = Field(default="#FF4600", min_length=4, max_length=16)
    cta_label: str = Field(default="Participer", max_length=40)
    cta_url: str = Field(default="/concours", max_length=400)
    starts_at: str
    ends_at: Optional[str] = None


class RewardAdminReq(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    summary: str = Field(min_length=8, max_length=280)
    description: str = Field(default="", max_length=4000)
    category: str = Field(default="badge", min_length=2, max_length=32)
    cost_tokens: int = Field(ge=10, le=100000)
    stock: int = Field(ge=0, le=100000)
    is_active: bool = True
    accent_color: str = Field(default="#00F0FF", min_length=4, max_length=16)
    delivery_notes: str = Field(default="", max_length=400)


class RewardRedemptionStatusReq(BaseModel):
    status: str = Field(pattern="^(pending|delivered|cancelled)$")


class TeamCreateReq(BaseModel):
    name: str = Field(min_length=3, max_length=48)
    tag: str = Field(min_length=2, max_length=6)
    country: str = Field(default="FR", min_length=2, max_length=24)
    description: str = Field(default="", max_length=500)
    language: str = Field(default="FR", min_length=2, max_length=24)
    discord_url: Optional[str] = Field(default=None, max_length=400)
    logo_color: str = Field(default="#FF4600", min_length=4, max_length=16)
    recruitment_status: str = Field(default="open", pattern="^(open|closed)$")
    members_limit: int = Field(default=7, ge=1, le=12)


class TeamUpdateReq(BaseModel):
    name: str = Field(min_length=3, max_length=48)
    tag: str = Field(min_length=2, max_length=6)
    country: str = Field(default="FR", min_length=2, max_length=24)
    description: str = Field(default="", max_length=500)
    language: str = Field(default="FR", min_length=2, max_length=24)
    discord_url: Optional[str] = Field(default=None, max_length=400)
    logo_color: str = Field(default="#FF4600", min_length=4, max_length=16)
    recruitment_status: str = Field(default="open", pattern="^(open|closed)$")
    members_limit: int = Field(default=7, ge=1, le=12)


class TeamApplicationReq(BaseModel):
    role: str = Field(default="Polyvalent", min_length=2, max_length=32)
    message: str = Field(default="", max_length=500)


async def _collect_team_members(team_id: str) -> list[dict]:
    user_members = await db.users.find(
        {"team_id": team_id},
        {
            "_id": 0,
            "id": 1,
            "pseudo": 1,
            "country": 1,
            "role": 1,
            "steam_verified": 1,
            "team_role": 1,
            "level": 1,
            "elo": 1,
            "platform_elo": 1,
            "faceit_elo": 1,
            "premier_rating": 1,
            "kdr": 1,
            "reliability": 1,
            "rank_cs2": 1,
            "custom_avatar_url": 1,
            "steam_avatar_url": 1,
            "online": 1,
        },
    ).to_list(30)
    player_members = await db.players.find(
        {"team_id": team_id},
        {
            "_id": 0,
            "id": 1,
            "pseudo": 1,
            "country": 1,
            "role": 1,
            "steam_verified": 1,
            "online": 1,
            "level": 1,
            "elo": 1,
            "platform_elo": 1,
            "faceit_elo": 1,
            "premier_rating": 1,
            "kdr": 1,
            "reliability": 1,
            "rank_cs2": 1,
            "custom_avatar_url": 1,
            "steam_avatar_url": 1,
        },
    ).to_list(30)

    members: list[dict] = []
    seen: set[str] = set()
    for doc in user_members:
        key = str(doc.get("id") or doc.get("pseudo") or uuid.uuid4())
        if key in seen:
            continue
        seen.add(key)
        members.append({
            "id": doc.get("id"),
            "pseudo": doc.get("pseudo"),
            "country": doc.get("country"),
            "role": doc.get("role") or "Polyvalent",
            "steam_verified": bool(doc.get("steam_verified")),
            "team_role": doc.get("team_role") or "member",
            "source": "user",
            "level": doc.get("level"),
            "elo": doc.get("platform_elo", doc.get("elo")),
            "faceit_elo": doc.get("faceit_elo"),
            "premier_rating": doc.get("premier_rating"),
            "kdr": _compute_kdr(doc),
            "reliability": doc.get("reliability"),
            "rank_cs2": doc.get("rank_cs2"),
            "avatar_url": doc.get("custom_avatar_url") or doc.get("steam_avatar_url"),
            "online": bool(doc.get("online", False)),
        })
    for doc in player_members:
        key = str(doc.get("id") or doc.get("pseudo") or uuid.uuid4())
        if key in seen:
            continue
        seen.add(key)
        members.append({
            "id": doc.get("id"),
            "pseudo": doc.get("pseudo"),
            "country": doc.get("country"),
            "role": doc.get("role") or "Polyvalent",
            "steam_verified": bool(doc.get("steam_verified")),
            "team_role": "seeded",
            "source": "seed",
            "level": doc.get("level"),
            "elo": doc.get("platform_elo", doc.get("elo")),
            "faceit_elo": doc.get("faceit_elo"),
            "premier_rating": doc.get("premier_rating"),
            "kdr": _compute_kdr(doc),
            "reliability": doc.get("reliability"),
            "rank_cs2": doc.get("rank_cs2"),
            "avatar_url": doc.get("custom_avatar_url") or doc.get("steam_avatar_url"),
            "online": bool(doc.get("online", False)),
        })
    return members


async def _team_public(team_doc: dict, include_members: bool = False) -> dict:
    members = await _collect_team_members(team_doc["id"])
    captain = next((member for member in members if member.get("team_role") == "captain"), None)
    return {
        **team_doc,
        "members_count": len(members),
        "members_limit": int(team_doc.get("members_limit", 7)),
        "captain_pseudo": team_doc.get("captain_pseudo") or (captain or {}).get("pseudo"),
        "recruitment_status": team_doc.get("recruitment_status", "open"),
        "description": team_doc.get("description", ""),
        "language": team_doc.get("language", "FR"),
        "discord_url": team_doc.get("discord_url"),
        "members": members if include_members else [],
        "pending_applications": await db.team_applications.count_documents({"team_id": team_doc["id"], "status": "pending"}),
    }


async def _get_team_or_404(team_id: str) -> dict:
    team = await db.teams.find_one({"id": team_id}, {"_id": 0})
    if not team:
        raise HTTPException(404, "Equipe introuvable")
    return team


def _is_team_captain(team: dict, user: dict) -> bool:
    return team.get("captain_user_id") == user["id"]


@api_router.get("/teams")
async def list_teams():
    docs = await db.teams.find({}, {"_id": 0}).sort("elo", -1).to_list(200)
    return [await _team_public(doc) for doc in docs]


@api_router.get("/teams/me", dependencies=[Depends(get_current_user)])
async def my_team(user=Depends(get_current_user)):
    team_id = user.get("team_id")
    if not team_id:
        return {"team": None}
    team = await db.teams.find_one({"id": team_id}, {"_id": 0})
    if not team:
        await db.users.update_one({"id": user["id"]}, {"$set": {"team_id": None, "team_role": None}})
        return {"team": None}
    return {"team": await _team_public(team, include_members=True)}


@api_router.get("/teams/{team_id}")
async def get_team(team_id: str):
    team = await _get_team_or_404(team_id)
    return await _team_public(team, include_members=True)


@api_router.post("/teams", dependencies=[Depends(get_current_user)])
async def create_team(req: TeamCreateReq, user=Depends(get_current_user)):
    if user.get("team_id"):
        raise HTTPException(409, "Vous faites deja partie d'une equipe")
    if await db.teams.find_one({"$or": [{"name": req.name.strip()}, {"tag": req.tag.strip().upper()}]}, {"_id": 0, "id": 1}):
        raise HTTPException(409, "Nom ou tag d'equipe deja utilise")

    now_iso = datetime.now(timezone.utc).isoformat()
    team = {
        "id": str(uuid.uuid4()),
        "name": req.name.strip(),
        "tag": req.tag.strip().upper(),
        "logo_color": req.logo_color.strip(),
        "country": req.country.strip().upper(),
        "level": 1,
        "elo": 1000,
        "wins": 0,
        "losses": 0,
        "trophies": 0,
        "reliability": 50,
        "description": req.description.strip(),
        "language": req.language.strip().upper(),
        "discord_url": req.discord_url.strip() if req.discord_url else None,
        "recruitment_status": req.recruitment_status,
        "members_limit": req.members_limit,
        "captain_user_id": user["id"],
        "captain_pseudo": user["pseudo"],
        "created_at": now_iso,
        "updated_at": now_iso,
        "created_by": user["id"],
    }
    await db.teams.insert_one(team)
    await db.users.update_one({"id": user["id"]}, {"$set": {"team_id": team["id"], "team_role": "captain"}})
    await journal("team_created", user["id"], {"team_id": team["id"], "name": team["name"]})
    return await _team_public(team, include_members=True)


@api_router.patch("/teams/{team_id}", dependencies=[Depends(get_current_user)])
async def update_team(team_id: str, req: TeamUpdateReq, user=Depends(get_current_user)):
    team = await _get_team_or_404(team_id)
    if not (_is_team_captain(team, user) or is_admin_email(user.get("email"))):
        raise HTTPException(403, "Seul le capitaine peut modifier cette equipe")

    if req.members_limit < 1:
        raise HTTPException(400, "Limite de membres invalide")
    members = await _collect_team_members(team_id)
    if req.members_limit < len(members):
        raise HTTPException(400, "La limite ne peut pas etre inferieure au nombre de membres")

    duplicate = await db.teams.find_one(
        {"id": {"$ne": team_id}, "$or": [{"name": req.name.strip()}, {"tag": req.tag.strip().upper()}]},
        {"_id": 0, "id": 1},
    )
    if duplicate:
        raise HTTPException(409, "Nom ou tag d'equipe deja utilise")

    updates = {
        "name": req.name.strip(),
        "tag": req.tag.strip().upper(),
        "logo_color": req.logo_color.strip(),
        "country": req.country.strip().upper(),
        "description": req.description.strip(),
        "language": req.language.strip().upper(),
        "discord_url": req.discord_url.strip() if req.discord_url else None,
        "recruitment_status": req.recruitment_status,
        "members_limit": req.members_limit,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.teams.update_one({"id": team_id}, {"$set": updates})
    await journal("team_updated", user["id"], {"team_id": team_id, "name": updates["name"]})
    updated = await db.teams.find_one({"id": team_id}, {"_id": 0})
    return await _team_public(updated, include_members=True)


@api_router.post("/teams/{team_id}/applications", dependencies=[Depends(get_current_user)])
async def apply_to_team(team_id: str, req: TeamApplicationReq, user=Depends(get_current_user)):
    team = await _get_team_or_404(team_id)
    if user.get("team_id"):
        raise HTTPException(409, "Vous etes deja rattache a une equipe")
    if team.get("recruitment_status", "open") != "open":
        raise HTTPException(400, "Cette equipe n'accepte pas de candidatures pour le moment")
    if await db.team_applications.find_one({"team_id": team_id, "user_id": user["id"], "status": "pending"}, {"_id": 0, "id": 1}):
        raise HTTPException(409, "Candidature deja envoyee")

    application = {
        "id": str(uuid.uuid4()),
        "team_id": team_id,
        "user_id": user["id"],
        "pseudo": user["pseudo"],
        "role": req.role.strip(),
        "message": req.message.strip(),
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.team_applications.insert_one(application)
    await journal("team_application_created", user["id"], {"team_id": team_id})
    return application


@api_router.get("/teams/{team_id}/applications", dependencies=[Depends(get_current_user)])
async def list_team_applications(team_id: str, user=Depends(get_current_user)):
    team = await _get_team_or_404(team_id)
    if not (_is_team_captain(team, user) or is_admin_email(user.get("email"))):
        raise HTTPException(403, "Acces reserve au capitaine de l'equipe")
    return await db.team_applications.find({"team_id": team_id}, {"_id": 0}).sort("created_at", -1).to_list(100)


@api_router.post("/teams/{team_id}/applications/{application_id}/approve", dependencies=[Depends(get_current_user)])
async def approve_team_application(team_id: str, application_id: str, user=Depends(get_current_user)):
    team = await _get_team_or_404(team_id)
    if not (_is_team_captain(team, user) or is_admin_email(user.get("email"))):
        raise HTTPException(403, "Acces reserve au capitaine de l'equipe")

    application = await db.team_applications.find_one({"id": application_id, "team_id": team_id}, {"_id": 0})
    if not application:
        raise HTTPException(404, "Candidature introuvable")
    if application.get("status") != "pending":
        raise HTTPException(400, "Cette candidature a deja ete traitee")

    applicant = await db.users.find_one({"id": application["user_id"]}, {"_id": 0})
    if not applicant:
        raise HTTPException(404, "Utilisateur introuvable")
    if applicant.get("team_id"):
        raise HTTPException(409, "Ce joueur a deja rejoint une autre equipe")

    members = await _collect_team_members(team_id)
    if len(members) >= int(team.get("members_limit", 7)):
        raise HTTPException(400, "Equipe complete")

    now_iso = datetime.now(timezone.utc).isoformat()
    await db.users.update_one({"id": applicant["id"]}, {"$set": {"team_id": team_id, "team_role": "member"}})
    await db.team_applications.update_one({"id": application_id}, {"$set": {"status": "approved", "updated_at": now_iso, "handled_by": user["id"]}})
    await journal("team_application_approved", user["id"], {"team_id": team_id, "application_id": application_id, "user_id": applicant["id"]})
    updated = await db.teams.find_one({"id": team_id}, {"_id": 0})
    return await _team_public(updated, include_members=True)


@api_router.post("/teams/{team_id}/applications/{application_id}/reject", dependencies=[Depends(get_current_user)])
async def reject_team_application(team_id: str, application_id: str, user=Depends(get_current_user)):
    team = await _get_team_or_404(team_id)
    if not (_is_team_captain(team, user) or is_admin_email(user.get("email"))):
        raise HTTPException(403, "Acces reserve au capitaine de l'equipe")
    application = await db.team_applications.find_one({"id": application_id, "team_id": team_id}, {"_id": 0})
    if not application:
        raise HTTPException(404, "Candidature introuvable")
    if application.get("status") != "pending":
        raise HTTPException(400, "Cette candidature a deja ete traitee")
    await db.team_applications.update_one(
        {"id": application_id},
        {"$set": {"status": "rejected", "updated_at": datetime.now(timezone.utc).isoformat(), "handled_by": user["id"]}},
    )
    await journal("team_application_rejected", user["id"], {"team_id": team_id, "application_id": application_id})
    return {"ok": True, "id": application_id, "status": "rejected"}


@api_router.post("/teams/{team_id}/leave", dependencies=[Depends(get_current_user)])
async def leave_team(team_id: str, user=Depends(get_current_user)):
    team = await _get_team_or_404(team_id)
    if user.get("team_id") != team_id:
        raise HTTPException(400, "Vous n'etes pas membre de cette equipe")

    if _is_team_captain(team, user):
        user_members = await db.users.find({"team_id": team_id}, {"_id": 0, "id": 1}).to_list(20)
        if len(user_members) > 1:
            raise HTTPException(400, "Transfert de capitanat requis avant de quitter l'equipe")
        await db.users.update_one({"id": user["id"]}, {"$set": {"team_id": None, "team_role": None}})
        await db.teams.delete_one({"id": team_id})
        await db.team_applications.delete_many({"team_id": team_id})
        await db.tournament_registrations.delete_many({"entity_type": "team", "entity_id": team_id})
        await journal("team_disbanded", user["id"], {"team_id": team_id, "name": team.get("name")})
        return {"ok": True, "disbanded": True}

    await db.users.update_one({"id": user["id"]}, {"$set": {"team_id": None, "team_role": None}})
    await journal("team_left", user["id"], {"team_id": team_id})
    return {"ok": True, "disbanded": False}

@api_router.get("/players")
async def list_players(available_only: bool = False):
    q = {"available": True} if available_only else {}
    docs = await db.players.find(q, {"_id": 0}).sort("elo", -1).to_list(200)
    return [{**doc, **_public_stats_payload(doc)} for doc in docs]

@api_router.get("/tournaments")
async def list_tournaments(status: Optional[str] = None):
    q = {"status": status} if status else {}
    return await db.tournaments.find(q, {"_id": 0}).sort("starts_at", 1).to_list(200)

@api_router.get("/tournaments/{tid}")
async def get_tournament(tid: str):
    t = await db.tournaments.find_one({"id": tid}, {"_id": 0})
    if not t:
        raise HTTPException(404, "Tournament not found")
    regs = await db.tournament_registrations.find({"tournament_id": tid}, {"_id": 0}).sort("created_at", 1).to_list(200)
    teams_in, solo_queue = [], []
    for r in regs:
        if r["entity_type"] == "team":
            td = await db.teams.find_one({"id": r.get("entity_id")}, {"_id": 0}) if r.get("entity_id") else None
            teams_in.append(td or {"id": r["id"], "name": r["entity_name"], "tag": r["entity_name"][:4].upper(), "elo": 0, "logo_color": "#6b7280"})
        else:
            pd = await db.players.find_one({"id": r.get("entity_id")}, {"_id": 0}) if r.get("entity_id") else None
            solo_queue.append(pd or {"id": r["id"], "pseudo": r["entity_name"], "role": "-", "online": True, "steam_verified": False})
    if not teams_in:
        teams_in = await db.teams.find({}, {"_id": 0}).sort("elo", -1).to_list(min(t.get("registered", 0) or 0, 8))
    if not solo_queue:
        solo_queue = await db.players.find({"available": True}, {"_id": 0}).limit(5).to_list(5)
    return {**t, "teams_in": teams_in, "solo_queue": solo_queue, "registrations_count": len(regs)}

@api_router.get("/news")
async def list_news():
    return await db.news.find({}, {"_id": 0}).sort("date", -1).to_list(50)


@api_router.get("/announcements")
async def list_announcements():
    docs = await db.announcements.find({}, {"_id": 0}).sort([("priority", -1), ("created_at", -1)]).to_list(50)
    now_iso = datetime.now(timezone.utc).isoformat()
    return [doc for doc in docs if _active_announcement(doc, now_iso)]


@api_router.get("/contests")
async def list_contests():
    docs = await db.contests.find({}, {"_id": 0}).sort([("starts_at", -1), ("created_at", -1)]).to_list(50)
    now_iso = datetime.now(timezone.utc).isoformat()
    items = []
    for doc in docs:
        if not _active_announcement(doc, now_iso):
            continue
        entry_count = await db.contest_entries.count_documents({"contest_id": doc["id"]})
        remaining_slots = _remaining_slots(doc.get("max_entries"), entry_count)
        items.append({
            **doc,
            "entries_count": entry_count,
            "remaining_slots": remaining_slots,
            "is_joinable": remaining_slots is None or remaining_slots > 0,
        })
    return items


@api_router.post("/contests/{contest_id}/join", dependencies=[Depends(get_current_user)])
async def join_contest(contest_id: str, user=Depends(get_current_user)):
    contest = await db.contests.find_one({"id": contest_id}, {"_id": 0})
    if not contest:
        raise HTTPException(404, "Concours introuvable")
    now_iso = datetime.now(timezone.utc).isoformat()
    if not _active_announcement(contest, now_iso):
        raise HTTPException(400, "Concours indisponible")
    if await db.contest_entries.find_one({"contest_id": contest_id, "user_id": user["id"]}, {"_id": 0}):
        raise HTTPException(409, "Participation deja enregistree")
    entry_count = await db.contest_entries.count_documents({"contest_id": contest_id})
    remaining_slots = _remaining_slots(contest.get("max_entries"), entry_count)
    if remaining_slots == 0:
        raise HTTPException(400, "Concours complet")
    entry = {
        "id": str(uuid.uuid4()),
        "contest_id": contest_id,
        "user_id": user["id"],
        "pseudo": user["pseudo"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.contest_entries.insert_one(entry)
    await journal("contest_joined", user["id"], {"contest_id": contest_id, "contest_title": contest.get("title")})
    return entry


@api_router.get("/rewards")
async def list_rewards():
    return await db.rewards.find({"is_active": True}, {"_id": 0}).sort([("cost_tokens", 1), ("created_at", -1)]).to_list(100)


@api_router.get("/rewards/redemptions/me", dependencies=[Depends(get_current_user)])
async def my_reward_redemptions(user=Depends(get_current_user)):
    docs = await db.reward_redemptions.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(100)
    reward_ids = [doc.get("reward_id") for doc in docs if doc.get("reward_id")]
    rewards = await db.rewards.find({"id": {"$in": reward_ids}}, {"_id": 0, "id": 1, "title": 1}).to_list(100) if reward_ids else []
    title_by_id = {reward["id"]: reward.get("title") for reward in rewards}
    return [{**doc, "reward_title": title_by_id.get(doc.get("reward_id"))} for doc in docs]


@api_router.post("/rewards/{reward_id}/redeem", dependencies=[Depends(get_current_user)])
async def redeem_reward(reward_id: str, user=Depends(get_current_user)):
    reward = await db.rewards.find_one({"id": reward_id, "is_active": True}, {"_id": 0})
    if not reward:
        raise HTTPException(404, "Reward introuvable")
    stock = reward.get("stock", 0)
    if stock <= 0:
        raise HTTPException(400, "Reward en rupture de stock")
    current_balance = await get_balance(user["id"])
    if current_balance < reward["cost_tokens"]:
        raise HTTPException(400, f"Solde insuffisant ({current_balance} jetons)")

    balance_update = await db.users.update_one(
        {"id": user["id"], "tokens": {"$gte": reward["cost_tokens"]}},
        {"$inc": {"tokens": -reward["cost_tokens"]}},
    )
    if balance_update.modified_count == 0:
        raise HTTPException(400, "Impossible de reserver les jetons")

    stock_update = await db.rewards.update_one(
        {"id": reward_id, "is_active": True, "stock": {"$gt": 0}},
        {"$inc": {"stock": -1}},
    )
    if stock_update.modified_count == 0:
        await db.users.update_one({"id": user["id"]}, {"$inc": {"tokens": reward["cost_tokens"]}})
        raise HTTPException(400, "Reward indisponible")

    redemption = {
        "id": str(uuid.uuid4()),
        "reward_id": reward_id,
        "reward_title": reward["title"],
        "user_id": user["id"],
        "pseudo": user["pseudo"],
        "cost_tokens": reward["cost_tokens"],
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.reward_redemptions.insert_one(redemption)
    await journal("reward_redeemed", user["id"], {"reward_id": reward_id, "reward_title": reward["title"], "cost_tokens": reward["cost_tokens"]})
    return redemption


@api_router.get("/admin/news", dependencies=[Depends(get_admin_user)])
async def admin_list_news():
    return await db.news.find({}, {"_id": 0}).sort("date", -1).to_list(100)


@api_router.post("/admin/news", dependencies=[Depends(get_admin_user)])
async def admin_create_news(req: NewsAdminReq, admin=Depends(get_admin_user)):
    doc = {
        "id": str(uuid.uuid4()),
        "title": req.title.strip(),
        "excerpt": req.excerpt.strip(),
        "body": req.body.strip(),
        "date": _parse_iso_datetime(req.date, "date"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": None,
        "created_by": admin["id"],
    }
    await db.news.insert_one(doc)
    await journal("news_created", admin["id"], {"news_id": doc["id"], "title": doc["title"]})
    return doc


@api_router.patch("/admin/news/{news_id}", dependencies=[Depends(get_admin_user)])
async def admin_update_news(news_id: str, req: NewsAdminReq, admin=Depends(get_admin_user)):
    existing = await db.news.find_one({"id": news_id}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "News introuvable")
    updates = {
        "title": req.title.strip(),
        "excerpt": req.excerpt.strip(),
        "body": req.body.strip(),
        "date": _parse_iso_datetime(req.date, "date"),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": admin["id"],
    }
    await db.news.update_one({"id": news_id}, {"$set": updates})
    await journal("news_updated", admin["id"], {"news_id": news_id, "title": updates["title"]})
    return {**existing, **updates}


@api_router.delete("/admin/news/{news_id}", dependencies=[Depends(get_admin_user)])
async def admin_delete_news(news_id: str, admin=Depends(get_admin_user)):
    deleted = await db.news.find_one_and_delete({"id": news_id}, projection={"_id": 0})
    if not deleted:
        raise HTTPException(404, "News introuvable")
    await journal("news_deleted", admin["id"], {"news_id": news_id, "title": deleted.get("title")})
    return {"ok": True, "id": news_id}


@api_router.get("/admin/announcements", dependencies=[Depends(get_admin_user)])
async def admin_list_announcements():
    return await db.announcements.find({}, {"_id": 0}).sort([("priority", -1), ("created_at", -1)]).to_list(100)


@api_router.post("/admin/announcements", dependencies=[Depends(get_admin_user)])
async def admin_create_announcement(req: AnnouncementAdminReq, admin=Depends(get_admin_user)):
    starts_at = _parse_iso_datetime(req.starts_at, "starts_at") if req.starts_at else None
    ends_at = _parse_iso_datetime(req.ends_at, "ends_at") if req.ends_at else None
    if starts_at and ends_at and starts_at > ends_at:
        raise HTTPException(400, "starts_at doit être antérieur à ends_at")
    doc = {
        "id": str(uuid.uuid4()),
        "title": req.title.strip(),
        "body": req.body.strip(),
        "kind": req.kind.strip().lower(),
        "priority": req.priority,
        "is_active": req.is_active,
        "cta_label": req.cta_label.strip(),
        "cta_url": req.cta_url.strip(),
        "starts_at": starts_at,
        "ends_at": ends_at,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": None,
        "created_by": admin["id"],
    }
    await db.announcements.insert_one(doc)
    await journal("announcement_created", admin["id"], {"announcement_id": doc["id"], "title": doc["title"]})
    return doc


@api_router.patch("/admin/announcements/{announcement_id}", dependencies=[Depends(get_admin_user)])
async def admin_update_announcement(announcement_id: str, req: AnnouncementAdminReq, admin=Depends(get_admin_user)):
    existing = await db.announcements.find_one({"id": announcement_id}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "Annonce introuvable")
    starts_at = _parse_iso_datetime(req.starts_at, "starts_at") if req.starts_at else None
    ends_at = _parse_iso_datetime(req.ends_at, "ends_at") if req.ends_at else None
    if starts_at and ends_at and starts_at > ends_at:
        raise HTTPException(400, "starts_at doit être antérieur à ends_at")
    updates = {
        "title": req.title.strip(),
        "body": req.body.strip(),
        "kind": req.kind.strip().lower(),
        "priority": req.priority,
        "is_active": req.is_active,
        "cta_label": req.cta_label.strip(),
        "cta_url": req.cta_url.strip(),
        "starts_at": starts_at,
        "ends_at": ends_at,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": admin["id"],
    }
    await db.announcements.update_one({"id": announcement_id}, {"$set": updates})
    await journal("announcement_updated", admin["id"], {"announcement_id": announcement_id, "title": updates["title"]})
    return {**existing, **updates}


@api_router.delete("/admin/announcements/{announcement_id}", dependencies=[Depends(get_admin_user)])
async def admin_delete_announcement(announcement_id: str, admin=Depends(get_admin_user)):
    deleted = await db.announcements.find_one_and_delete({"id": announcement_id}, projection={"_id": 0})
    if not deleted:
        raise HTTPException(404, "Annonce introuvable")
    await journal("announcement_deleted", admin["id"], {"announcement_id": announcement_id, "title": deleted.get("title")})
    return {"ok": True, "id": announcement_id}


@api_router.get("/admin/contests", dependencies=[Depends(get_admin_user)])
async def admin_list_contests():
    docs = await db.contests.find({}, {"_id": 0}).sort([("starts_at", -1), ("created_at", -1)]).to_list(100)
    items = []
    for doc in docs:
        entry_count = await db.contest_entries.count_documents({"contest_id": doc["id"]})
        items.append({**doc, "entries_count": entry_count, "remaining_slots": _remaining_slots(doc.get("max_entries"), entry_count)})
    return items


@api_router.get("/admin/contests/{contest_id}/entries", dependencies=[Depends(get_admin_user)])
async def admin_list_contest_entries(contest_id: str):
    return await db.contest_entries.find({"contest_id": contest_id}, {"_id": 0}).sort("created_at", -1).to_list(500)


@api_router.post("/admin/contests", dependencies=[Depends(get_admin_user)])
async def admin_create_contest(req: ContestAdminReq, admin=Depends(get_admin_user)):
    starts_at = _parse_iso_datetime(req.starts_at, "starts_at")
    ends_at = _parse_iso_datetime(req.ends_at, "ends_at") if req.ends_at else None
    if ends_at and starts_at > ends_at:
        raise HTTPException(400, "starts_at doit etre anterieur a ends_at")
    doc = {
        "id": str(uuid.uuid4()),
        "title": req.title.strip(),
        "summary": req.summary.strip(),
        "body": req.body.strip(),
        "reward_label": req.reward_label.strip(),
        "max_entries": req.max_entries,
        "is_active": req.is_active,
        "banner_color": req.banner_color.strip(),
        "cta_label": req.cta_label.strip(),
        "cta_url": req.cta_url.strip(),
        "starts_at": starts_at,
        "ends_at": ends_at,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": None,
        "created_by": admin["id"],
    }
    await db.contests.insert_one(doc)
    await journal("contest_created", admin["id"], {"contest_id": doc["id"], "title": doc["title"]})
    return doc


@api_router.patch("/admin/contests/{contest_id}", dependencies=[Depends(get_admin_user)])
async def admin_update_contest(contest_id: str, req: ContestAdminReq, admin=Depends(get_admin_user)):
    existing = await db.contests.find_one({"id": contest_id}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "Concours introuvable")
    starts_at = _parse_iso_datetime(req.starts_at, "starts_at")
    ends_at = _parse_iso_datetime(req.ends_at, "ends_at") if req.ends_at else None
    if ends_at and starts_at > ends_at:
        raise HTTPException(400, "starts_at doit etre anterieur a ends_at")
    updates = {
        "title": req.title.strip(),
        "summary": req.summary.strip(),
        "body": req.body.strip(),
        "reward_label": req.reward_label.strip(),
        "max_entries": req.max_entries,
        "is_active": req.is_active,
        "banner_color": req.banner_color.strip(),
        "cta_label": req.cta_label.strip(),
        "cta_url": req.cta_url.strip(),
        "starts_at": starts_at,
        "ends_at": ends_at,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": admin["id"],
    }
    await db.contests.update_one({"id": contest_id}, {"$set": updates})
    await journal("contest_updated", admin["id"], {"contest_id": contest_id, "title": updates["title"]})
    return {**existing, **updates}


@api_router.delete("/admin/contests/{contest_id}", dependencies=[Depends(get_admin_user)])
async def admin_delete_contest(contest_id: str, admin=Depends(get_admin_user)):
    if await db.contest_entries.count_documents({"contest_id": contest_id}) > 0:
        raise HTTPException(400, "Ce concours contient deja des participations. Desactivez-le plutot que le supprimer.")
    deleted = await db.contests.find_one_and_delete({"id": contest_id}, projection={"_id": 0})
    if not deleted:
        raise HTTPException(404, "Concours introuvable")
    await journal("contest_deleted", admin["id"], {"contest_id": contest_id, "title": deleted.get("title")})
    return {"ok": True, "id": contest_id}


@api_router.get("/admin/rewards", dependencies=[Depends(get_admin_user)])
async def admin_list_rewards():
    return await db.rewards.find({}, {"_id": 0}).sort([("is_active", -1), ("cost_tokens", 1), ("created_at", -1)]).to_list(100)


@api_router.get("/admin/rewards/redemptions", dependencies=[Depends(get_admin_user)])
async def admin_list_reward_redemptions():
    return await db.reward_redemptions.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)


@api_router.post("/admin/rewards", dependencies=[Depends(get_admin_user)])
async def admin_create_reward(req: RewardAdminReq, admin=Depends(get_admin_user)):
    doc = {
        "id": str(uuid.uuid4()),
        "title": req.title.strip(),
        "summary": req.summary.strip(),
        "description": req.description.strip(),
        "category": req.category.strip().lower(),
        "cost_tokens": req.cost_tokens,
        "stock": req.stock,
        "is_active": req.is_active,
        "accent_color": req.accent_color.strip(),
        "delivery_notes": req.delivery_notes.strip(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": None,
        "created_by": admin["id"],
    }
    await db.rewards.insert_one(doc)
    await journal("reward_created", admin["id"], {"reward_id": doc["id"], "title": doc["title"]})
    return doc


@api_router.patch("/admin/rewards/{reward_id}", dependencies=[Depends(get_admin_user)])
async def admin_update_reward(reward_id: str, req: RewardAdminReq, admin=Depends(get_admin_user)):
    existing = await db.rewards.find_one({"id": reward_id}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "Reward introuvable")
    updates = {
        "title": req.title.strip(),
        "summary": req.summary.strip(),
        "description": req.description.strip(),
        "category": req.category.strip().lower(),
        "cost_tokens": req.cost_tokens,
        "stock": req.stock,
        "is_active": req.is_active,
        "accent_color": req.accent_color.strip(),
        "delivery_notes": req.delivery_notes.strip(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": admin["id"],
    }
    await db.rewards.update_one({"id": reward_id}, {"$set": updates})
    await journal("reward_updated", admin["id"], {"reward_id": reward_id, "title": updates["title"]})
    return {**existing, **updates}


@api_router.patch("/admin/rewards/redemptions/{redemption_id}", dependencies=[Depends(get_admin_user)])
async def admin_update_reward_redemption(redemption_id: str, req: RewardRedemptionStatusReq, admin=Depends(get_admin_user)):
    existing = await db.reward_redemptions.find_one({"id": redemption_id}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "Redemption introuvable")
    current_status = existing.get("status", "pending")
    new_status = req.status
    if current_status == new_status:
        return existing
    allowed_transitions = {
        "pending": {"delivered", "cancelled"},
        "delivered": {"cancelled"},
        "cancelled": set(),
    }
    if new_status not in allowed_transitions.get(current_status, set()):
        raise HTTPException(400, f"Transition {current_status} -> {new_status} interdite")

    updates = {
        "status": new_status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": admin["id"],
    }

    if new_status == "cancelled":
        await db.users.update_one({"id": existing["user_id"]}, {"$inc": {"tokens": existing["cost_tokens"]}})
        await db.rewards.update_one({"id": existing["reward_id"]}, {"$inc": {"stock": 1}})
        updates["cancelled_at"] = datetime.now(timezone.utc).isoformat()
        updates["cancelled_by"] = admin["id"]
    elif new_status == "delivered":
        updates["delivered_at"] = datetime.now(timezone.utc).isoformat()
        updates["delivered_by"] = admin["id"]

    await db.reward_redemptions.update_one({"id": redemption_id}, {"$set": updates})
    await journal("reward_redemption_updated", admin["id"], {"redemption_id": redemption_id, "from": current_status, "to": new_status})
    return {**existing, **updates}


@api_router.delete("/admin/rewards/{reward_id}", dependencies=[Depends(get_admin_user)])
async def admin_delete_reward(reward_id: str, admin=Depends(get_admin_user)):
    if await db.reward_redemptions.count_documents({"reward_id": reward_id}) > 0:
        raise HTTPException(400, "Cette reward possede deja des redemptions. Desactivez-la plutot que la supprimer.")
    deleted = await db.rewards.find_one_and_delete({"id": reward_id}, projection={"_id": 0})
    if not deleted:
        raise HTTPException(404, "Reward introuvable")
    await journal("reward_deleted", admin["id"], {"reward_id": reward_id, "title": deleted.get("title")})
    return {"ok": True, "id": reward_id}


@api_router.post("/admin/tournaments", dependencies=[Depends(get_admin_user)])
async def admin_create_tournament(req: TournamentAdminReq, admin=Depends(get_admin_user)):
    status = req.status.strip()
    if status not in TOURNAMENT_STATES:
        raise HTTPException(400, f"Statut inconnu. Choix : {TOURNAMENT_STATES}")
    doc = {
        "id": str(uuid.uuid4()),
        "name": req.name.strip(),
        "organizer": req.organizer.strip(),
        "format": req.format.strip(),
        "mode": req.mode.strip(),
        "capacity": req.capacity,
        "registered": 0,
        "status": status,
        "starts_at": _parse_iso_datetime(req.starts_at, "starts_at"),
        "prize": req.prize.strip(),
        "region": req.region.strip(),
        "level_min": req.level_min,
        "image_color": req.image_color.strip(),
        "description": req.description.strip(),
        "maps": _normalise_string_list(req.maps),
        "rules": _normalise_string_list(req.rules),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": None,
        "created_by": admin["id"],
    }
    await db.tournaments.insert_one(doc)
    await journal("tournament_created", admin["id"], {"tournament_id": doc["id"], "name": doc["name"]})
    return doc


@api_router.patch("/admin/tournaments/{tid}", dependencies=[Depends(get_admin_user)])
async def admin_update_tournament(tid: str, req: TournamentAdminReq, admin=Depends(get_admin_user)):
    existing = await db.tournaments.find_one({"id": tid}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "Tournoi introuvable")
    status = req.status.strip()
    if status not in TOURNAMENT_STATES:
        raise HTTPException(400, f"Statut inconnu. Choix : {TOURNAMENT_STATES}")
    if req.capacity < existing.get("registered", 0):
        raise HTTPException(400, "La capacité ne peut pas être inférieure au nombre déjà inscrit")
    updates = {
        "name": req.name.strip(),
        "organizer": req.organizer.strip(),
        "format": req.format.strip(),
        "mode": req.mode.strip(),
        "capacity": req.capacity,
        "status": status,
        "starts_at": _parse_iso_datetime(req.starts_at, "starts_at"),
        "prize": req.prize.strip(),
        "region": req.region.strip(),
        "level_min": req.level_min,
        "image_color": req.image_color.strip(),
        "description": req.description.strip(),
        "maps": _normalise_string_list(req.maps),
        "rules": _normalise_string_list(req.rules),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": admin["id"],
    }
    await db.tournaments.update_one({"id": tid}, {"$set": updates})
    await journal("tournament_updated", admin["id"], {"tournament_id": tid, "name": updates["name"]})
    return {**existing, **updates}


@api_router.post("/admin/tournaments/{tid}/duplicate", dependencies=[Depends(get_admin_user)])
async def admin_duplicate_tournament(tid: str, admin=Depends(get_admin_user)):
    existing = await db.tournaments.find_one({"id": tid}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "Tournoi introuvable")
    duplicated = {
        **existing,
        "id": str(uuid.uuid4()),
        "name": f"{existing['name']} (copie)",
        "registered": 0,
        "status": "open",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": None,
        "created_by": admin["id"],
        "updated_by": None,
        "status_changed_at": None,
    }
    await db.tournaments.insert_one(duplicated)
    await journal("tournament_duplicated", admin["id"], {"source_tournament_id": tid, "tournament_id": duplicated["id"]})
    return duplicated


@api_router.delete("/admin/tournaments/{tid}", dependencies=[Depends(get_admin_user)])
async def admin_delete_tournament(tid: str, admin=Depends(get_admin_user)):
    deleted = await db.tournaments.find_one_and_delete({"id": tid}, projection={"_id": 0})
    if not deleted:
        raise HTTPException(404, "Tournoi introuvable")
    await db.tournament_registrations.delete_many({"tournament_id": tid})
    await db.brackets.delete_many({"tournament_id": tid})
    await journal("tournament_deleted", admin["id"], {"tournament_id": tid, "name": deleted.get("name")})
    return {"ok": True, "id": tid}

# ---------- Tournament registration + state machine (Iteration 5) ----------
class RegisterTournamentReq(BaseModel):
    entity_type: str = Field(pattern="^(team|solo)$")
    entity_name: str = Field(min_length=2, max_length=48)
    entity_id: Optional[str] = None

@api_router.post("/tournaments/{tid}/register", dependencies=[Depends(get_current_user)])
async def register_tournament(tid: str, req: RegisterTournamentReq, user=Depends(get_current_user)):
    t = await db.tournaments.find_one({"id": tid})
    if not t:
        raise HTTPException(404, "Tournoi introuvable")
    if t["status"] not in ("open", "registering"):
        raise HTTPException(400, f"Inscriptions fermées (statut : {t['status']})")
    if t.get("registered", 0) >= t.get("capacity", 0):
        raise HTTPException(400, "Tournoi complet")
    if await db.tournament_registrations.find_one({"tournament_id": tid, "user_id": user["id"]}):
        raise HTTPException(409, "Déjà inscrit à ce tournoi")

    entity_id = req.entity_id
    entity_name = req.entity_name
    if req.entity_type == "team":
        team_id = user.get("team_id")
        if not team_id:
            raise HTTPException(400, "Créez ou rejoignez une équipe avant l'inscription tournoi")
        team = await db.teams.find_one({"id": team_id}, {"_id": 0})
        if not team:
            raise HTTPException(404, "Equipe introuvable")
        if team.get("captain_user_id") != user["id"]:
            raise HTTPException(403, "Seul le capitaine peut inscrire l'equipe")
        if await db.tournament_registrations.find_one({"tournament_id": tid, "entity_type": "team", "entity_id": team_id}, {"_id": 0, "id": 1}):
            raise HTTPException(409, "Cette equipe est deja inscrite au tournoi")
        entity_id = team_id
        entity_name = team["name"]

    reg = {"id": str(uuid.uuid4()), "tournament_id": tid, "user_id": user["id"],
           "entity_type": req.entity_type, "entity_id": entity_id,
           "entity_name": entity_name, "created_at": datetime.now(timezone.utc).isoformat()}
    await db.tournament_registrations.insert_one(reg)
    new_status = "registering" if t["status"] == "open" else t["status"]
    await db.tournaments.update_one({"id": tid}, {"$inc": {"registered": 1}, "$set": {"status": new_status}})
    await journal("tournament_registered", user["id"], {"tournament_id": tid, "entity": req.entity_name})
    return _clean(reg)

@api_router.get("/tournaments/{tid}/registrations")
async def list_registrations(tid: str):
    return await db.tournament_registrations.find({"tournament_id": tid}, {"_id": 0}).sort("created_at", 1).to_list(200)

class TransitionReq(BaseModel):
    to: str

@api_router.post("/tournaments/{tid}/transition", dependencies=[Depends(get_admin_user)])
async def transition_tournament(tid: str, req: TransitionReq, user=Depends(get_admin_user)):
    t = await db.tournaments.find_one({"id": tid})
    if not t:
        raise HTTPException(404, "Tournoi introuvable")
    cur = t["status"]
    if req.to not in TOURNAMENT_STATES:
        raise HTTPException(400, f"État inconnu. Choix : {TOURNAMENT_STATES}")
    if req.to not in ALLOWED_TRANSITIONS.get(cur, []):
        raise HTTPException(409, f"Transition {cur} → {req.to} interdite")
    await db.tournaments.update_one({"id": tid}, {"$set": {"status": req.to, "status_changed_at": datetime.now(timezone.utc).isoformat()}})
    await journal("tournament_transition", user["id"], {"tournament_id": tid, "from": cur, "to": req.to})
    if req.to == "starting":
        # Auto-go-live 30s after seeding/starting via the Redis job queue
        await rs.schedule_job(time.time() + 30, {"type": "tournament_transition", "tournament_id": tid, "to": "live", "from": "starting"})
    return {"id": tid, "from": cur, "to": req.to, "allowed_next": ALLOWED_TRANSITIONS[req.to]}

@api_router.get("/stats/global")
async def global_stats():
    users_count = await db.users.count_documents({})
    cards_count = await db.cards.count_documents({"status": "active"})
    duels_count = await db.duels.count_documents({})
    donations_count = await db.payment_transactions.count_documents({"status": "paid"})
    return {
        "players": max(users_count, 12480),
        "teams": 1840,
        "tournaments_total": 312,
        "matches_played": 8420,
        "reinforcements_completed": duels_count + 1102,
        "online_now": users_count if users_count > 0 else 487,
        "active_cards": cards_count,
        "donations_received": donations_count,
    }


class MatchReportReq(BaseModel):
    kind: str = Field(pattern="^(technical|pause|behavior|absence|score|cheat|other)$")
    message: str = Field(min_length=3, max_length=500)
    round_label: Optional[str] = Field(default=None, max_length=40)


class MatchReportStatusReq(BaseModel):
    status: str = Field(pattern="^(open|acknowledged|resolved|rejected)$")
    resolution_note: Optional[str] = Field(default=None, max_length=500)

@api_router.get("/twitch/live")
async def twitch_live():
    ch = os.environ.get("TWITCH_CHANNEL", "esl_csgo")
    return {"channel": ch, "live": True, "title": "BLAST Major CS2 — Quarterfinals", "viewers": 84210, "game": "Counter-Strike 2"}

# Steam OpenID (REAL — validates signature against Steam servers)
STEAM_OPENID_URL = "https://steamcommunity.com/openid/login"

def _backend_base(request: Request) -> str:
    # External URL for OpenID realm/return_to
    return os.environ.get("BACKEND_PUBLIC_URL") or str(request.base_url).rstrip("/")

def _frontend_base() -> str:
    return env_text("FRONTEND_URL", DEFAULT_FRONTEND_URL).rstrip("/")

@api_router.get("/auth/steam/login")
async def steam_login_real(request: Request):
    backend = _backend_base(request)
    params = {
        "openid.ns": "http://specs.openid.net/auth/2.0",
        "openid.mode": "checkid_setup",
        "openid.return_to": f"{backend}/api/auth/steam/callback",
        "openid.realm": backend,
        "openid.identity": "http://specs.openid.net/auth/2.0/identifier_select",
        "openid.claimed_id": "http://specs.openid.net/auth/2.0/identifier_select",
    }
    return RedirectResponse(url=f"{STEAM_OPENID_URL}?{urlencode(params)}", status_code=302)

@api_router.get("/auth/steam/callback")
async def steam_callback(request: Request):
    qp = dict(request.query_params)
    if qp.get("openid.mode") != "id_res":
        return RedirectResponse(url=f"{_frontend_base()}/login?steam_error=cancelled", status_code=302)
    # Step 1: validate by sending back to Steam with mode=check_authentication
    verify = {**qp, "openid.mode": "check_authentication"}
    async with httpx.AsyncClient(timeout=10) as cx:
        r = await cx.post(STEAM_OPENID_URL, data=verify)
    if "is_valid:true" not in r.text:
        await journal("steam_verify_failed", None, {"raw": r.text[:200]})
        return RedirectResponse(url=f"{_frontend_base()}/login?steam_error=invalid", status_code=302)
    # Step 2: extract SteamID64 from claimed_id
    claimed = qp.get("openid.claimed_id", "")
    steam_id = claimed.rsplit("/", 1)[-1] if claimed else None
    if not steam_id or not steam_id.isdigit():
        return RedirectResponse(url=f"{_frontend_base()}/login?steam_error=no_id", status_code=302)
    # Step 3: link to existing user (via session) or create a "steam-only" user
    existing = await db.users.find_one({"steam_id": steam_id})
    if existing:
        user = existing
    else:
        # Create lightweight Steam-only account
        user = {
            "id": str(uuid.uuid4()), "pseudo": f"Steam_{steam_id[-6:]}",
            "email": f"steam_{steam_id}@readyup.local",
            "password_hash": hash_password(uuid.uuid4().hex), "country": "??",
            "gender": None, "age": None, "bio": None,
            "custom_avatar_url": None, "steam_avatar_url": None,
            "level": 1, "xp": 0, "elo": 1000, "platform_elo": 1000,
            "faceit_elo": None, "premier_rating": None, "premier_status": None,
            "kills_30d": None, "deaths_30d": None, "kdr": None,
            "rank_cs2": None, "role": "Polyvalent", "reliability": 55,
            "stats_last_sync_at": None,
            "steam_verified": True, "steam_id": steam_id,
            "team_id": None, "team_role": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.users.insert_one(user)
    await journal("steam_login", user["id"], {"steam_id": steam_id})
    token = make_token(user["id"], user["pseudo"])
    return RedirectResponse(url=f"{_frontend_base()}/auth/steam/complete?token={token}&steamId={steam_id}", status_code=302)

# ============ STRIPE — real Checkout via emergentintegrations =============
STRIPE_API_KEY = env_text("STRIPE_API_KEY")

DONATION_AMOUNTS = {1: 1.0, 2: 2.0, 3: 3.0, 4: 4.0, 5: 5.0, 10: 10.0, 20: 20.0, 50: 50.0}

class CheckoutReq(BaseModel):
    amount: int  # one of DONATION_AMOUNTS keys
    kind: str = "one_time"  # or "monthly"
    origin: str  # frontend origin

@api_router.post("/donations/checkout-session")
async def create_donation_session(req: CheckoutReq, request: Request):
    if not STRIPE_API_KEY:
        raise HTTPException(503, "Stripe n'est pas configuré sur cet environnement")
    if req.amount not in DONATION_AMOUNTS:
        raise HTTPException(400, f"Montant invalide. Choix: {list(DONATION_AMOUNTS.keys())}")
    amount = DONATION_AMOUNTS[req.amount]
    backend = _backend_base(request)
    webhook_url = f"{backend}/api/donations/webhook"
    sc = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)
    session_req = CheckoutSessionRequest(
        amount=amount, currency="eur",
        success_url=f"{req.origin}/donate?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{req.origin}/donate?cancelled=1",
        metadata={"kind": req.kind, "amount_eur": str(amount), "platform": "readyup-arena"},
    )
    resp = None
    try:
        resp = await sc.create_checkout_session(session_req)
    except Exception as e:
        raise HTTPException(502, f"Stripe error: {e}")
    if resp is None:
        raise HTTPException(502, "Stripe returned empty response")
    # Persist payment transaction (status=pending)
    tx = {
        "id": str(uuid.uuid4()), "session_id": resp.session_id, "amount_eur": amount,
        "kind": req.kind, "status": "pending", "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.payment_transactions.insert_one(tx)
    await journal("donation_session_created", None, {"session_id": resp.session_id, "amount": amount})
    return {"url": resp.url, "session_id": resp.session_id}

@api_router.get("/donations/status/{session_id}")
async def donation_status(session_id: str):
    if not STRIPE_API_KEY:
        raise HTTPException(503, "Stripe n'est pas configuré sur cet environnement")
    sc = StripeCheckout(api_key=STRIPE_API_KEY)
    st = None
    try:
        st = await sc.get_checkout_status(session_id)
    except Exception as e:
        raise HTTPException(502, str(e))
    if st is None:
        raise HTTPException(502, "Stripe returned empty status")
    # Update local tx idempotently
    await db.payment_transactions.update_one(
        {"session_id": session_id},
        {"$set": {"status": st.payment_status, "updated_at": datetime.now(timezone.utc).isoformat()}})
    return {"session_id": session_id, "payment_status": st.payment_status, "amount_total": st.amount_total, "currency": st.currency}

@api_router.post("/donations/webhook")
async def stripe_webhook(request: Request):
    if not STRIPE_API_KEY:
        raise HTTPException(503, "Stripe n'est pas configuré sur cet environnement")
    body = await request.body()
    sig = request.headers.get("stripe-signature", "")
    sc = StripeCheckout(api_key=STRIPE_API_KEY)
    try:
        evt = await sc.handle_webhook(body, sig)
    except Exception as e:
        raise HTTPException(400, f"Webhook invalid: {e}")
    # Idempotent update
    await db.payment_transactions.update_one(
        {"session_id": evt.session_id},
        {"$set": {"status": evt.payment_status, "webhook_event_id": evt.event_id, "webhook_type": evt.event_type,
                  "updated_at": datetime.now(timezone.utc).isoformat()}})
    await journal("stripe_webhook", None, {"event_id": evt.event_id, "type": evt.event_type, "session": evt.session_id})
    return {"received": True}

# Live waiting room snapshot (mock realtime)
@api_router.get("/tournaments/{tid}/waiting-room")
async def waiting_room(tid: str):
    return {
        "tournament_id": tid,
        "starts_in_seconds": secrets.choice([330, 295, 180, 120, 75, 30]),
        "teams_confirmed": 6, "teams_total": 8, "teams_missing": 2,
        "solo_queue_count": 7,
        "events": [
            {"time": "T-5:00", "type": "first_call", "msg": "Premier appel — confirmez votre équipe"},
            {"time": "T-4:32", "type": "team_ready", "msg": "Nova Strike est prêt"},
            {"time": "T-4:10", "type": "team_ready", "msg": "Pixel Reapers est prêt"},
            {"time": "T-3:45", "type": "solo_invited", "msg": "Halcyon invité comme renfort (Crimson Five)"},
            {"time": "T-3:12", "type": "solo_accepted", "msg": "Halcyon a accepté"},
            {"time": "T-2:00", "type": "last_call", "msg": "Dernier appel — départ dans 2 min"},
        ],
    }

# ============= WEBSOCKET — Waiting Room realtime + authoritative countdown =============
class WSHub:
    def __init__(self): self.rooms: dict[str, set[WebSocket]] = {}; self.presence: dict[str, dict[str, dict]] = {}
    async def join(self, tid, ws, user):
        self.rooms.setdefault(tid, set()).add(ws)
        self.presence.setdefault(tid, {})[user["id"]] = {"id": user["id"], "pseudo": user["pseudo"], "level": user.get("level",1), "joined_at": datetime.now(timezone.utc).isoformat()}
        await self.broadcast(tid, {"type": "presence", "users": list(self.presence[tid].values()), "count": len(self.presence[tid])})
        await self.broadcast(tid, {"type": "event", "time": datetime.now(timezone.utc).strftime("%H:%M:%S"), "msg": f"{user['pseudo']} a rejoint la salle"})
    async def leave(self, tid, ws, user):
        self.rooms.get(tid, set()).discard(ws)
        if user and tid in self.presence: self.presence[tid].pop(user["id"], None)
        await self.broadcast(tid, {"type": "presence", "users": list(self.presence.get(tid, {}).values()), "count": len(self.presence.get(tid, {}))})
    async def broadcast(self, tid, msg):
        dead = []
        for ws in self.rooms.get(tid, set()):
            try: await ws.send_json(msg)
            except Exception: dead.append(ws)
        for ws in dead: self.rooms[tid].discard(ws)

hub = WSHub()
# Authoritative countdowns are persisted in Redis (deadline timestamp) so they
# survive backend reboots. _running_countdowns guards against duplicate tasks.
_running_countdowns: set = set()

def _phase_for(seconds: int) -> str:
    return "countdown" if seconds <= 10 else "last_call" if seconds <= 120 else "first_call" if seconds <= 300 else "open"

async def countdown_task(tid: str):
    if tid in _running_countdowns:
        return
    # Redis lock: only one replica drives a given countdown
    if not await rs.acquire_cd_lock(tid):
        return
    _running_countdowns.add(tid)
    fired: set = set()
    try:
        while True:
            cd = await rs.get_countdown(tid)
            if not cd:
                return
            await rs.refresh_cd_lock(tid)
            remaining = int(round(float(cd["deadline"]) - time.time()))
            if remaining < 0:
                remaining = 0
            phase = _phase_for(remaining)
            await hub.broadcast(tid, {"type": "countdown", "seconds": remaining, "phase": phase, "server_time": datetime.now(timezone.utc).isoformat()})
            for mark, label, msg in ((300, "T-5:00", "Premier appel — confirmez votre équipe"), (120, "T-2:00", "Dernier appel — départ dans 2 min"), (10, "T-0:10", "DÉCOMPTE 10→0 LANCÉ")):
                if remaining == mark and mark not in fired:
                    await hub.broadcast(tid, {"type": "event", "time": label, "msg": msg})
                    fired.add(mark)
            if remaining <= 0:
                await hub.broadcast(tid, {"type": "go", "msg": "Le tournoi commence !"})
                await rs.del_countdown(tid)
                return
            await asyncio.sleep(1)
    finally:
        _running_countdowns.discard(tid)
        await rs.release_cd_lock(tid)

async def start_countdown(tid: str, seconds: int, started_by: str) -> bool:
    if await rs.get_countdown(tid):
        return False
    await rs.set_countdown(tid, time.time() + seconds, _phase_for(seconds), started_by)
    asyncio.create_task(countdown_task(tid))
    return True

@app.websocket("/api/ws/waiting-room/{tid}")
async def ws_waiting_room(ws: WebSocket, tid: str, token: str = Query(None)):
    user = None
    if token:
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
            u = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
            if u: user = u
        except Exception: pass
    if not user: user = {"id": "guest_" + uuid.uuid4().hex[:6], "pseudo": "Invité", "level": 1}
    await ws.accept()
    await hub.join(tid, ws, user)
    # send current countdown state if any (recomputed from persisted deadline)
    cd = await rs.get_countdown(tid)
    if cd:
        remaining = max(0, int(round(float(cd["deadline"]) - time.time())))
        await ws.send_json({"type": "countdown", "seconds": remaining, "phase": _phase_for(remaining), "server_time": datetime.now(timezone.utc).isoformat()})
    try:
        while True:
            data = await ws.receive_json()
            if data.get("action") == "start_countdown":
                started = await start_countdown(tid, int(data.get("from", 30)), user["pseudo"])
                if started:
                    await hub.broadcast(tid, {"type": "event", "time": datetime.now(timezone.utc).strftime("%H:%M:%S"), "msg": f"{user['pseudo']} a lancé le décompte"})
            elif data.get("action") == "ready":
                await hub.broadcast(tid, {"type": "event", "time": datetime.now(timezone.utc).strftime("%H:%M:%S"), "msg": f"{user['pseudo']} est prêt"})
            elif data.get("action") == "chat":
                await hub.broadcast(tid, {"type": "chat", "from": user["pseudo"], "msg": str(data.get("msg",""))[:200], "at": datetime.now(timezone.utc).strftime("%H:%M:%S")})
    except WebSocketDisconnect:
        await hub.leave(tid, ws, user)
    except Exception:
        await hub.leave(tid, ws, user)

@api_router.get("/donations/recent")
async def recent_donations(limit: int = 5):
    docs = await db.payment_transactions.find({"status": "paid"}, {"_id": 0}).sort("updated_at", -1).to_list(limit)
    return [{"amount_eur": d["amount_eur"], "kind": d["kind"], "at": d.get("updated_at", d["created_at"])} for d in docs]

# ============= LIVE MATCHES (derived from MatchZy events) =============
def _extract_score(p: dict) -> dict:
    t1 = p.get("team1") or {}
    t2 = p.get("team2") or {}
    return {
        "team1_name": t1.get("name") or p.get("team1_name") or "Team 1",
        "team2_name": t2.get("name") or p.get("team2_name") or "Team 2",
        "team1_score": t1.get("score", p.get("team1_score", 0)) or 0,
        "team2_score": t2.get("score", p.get("team2_score", 0)) or 0,
        "map_name": p.get("map_name") or p.get("map") or "—",
        "map_number": p.get("map_number", 0) or 0,
    }

_DEFAULTS = {None, 0, "—", "Team 1", "Team 2"}

def _merge_latest(acc: dict, sc: dict):
    for k, v in sc.items():
        if v not in _DEFAULTS:
            acc[k] = v
        else:
            acc.setdefault(k, v)

@api_router.get("/matches/live")
async def live_matches():
    events = await db.matchzy_events.find({"matchid": {"$ne": None}}, {"_id": 0}).sort("received_at", 1).to_list(2000)
    by_match: dict = {}
    for e in events:
        mid = str(e["matchid"])
        m = by_match.setdefault(mid, {"matchid": mid, "events": 0, "last_event": None, "ended": False, "updated_at": None})
        m["events"] += 1
        m["last_event"] = e["event"]
        m["updated_at"] = e["received_at"]
        _merge_latest(m, _extract_score(e.get("payload") or {}))
        if e["event"] == "series_end":
            m["ended"] = True
    live = [m for m in by_match.values() if not m["ended"]]
    for m in live:
        srv = await db.cs2_servers.find_one({"current_match_id": m["matchid"]}, {"_id": 0, "rcon_password": 0})
        m["server"] = srv["name"] if srv else None
    return sorted(live, key=lambda x: x["updated_at"] or "", reverse=True)

@api_router.get("/matches/{matchid}")
async def match_detail(matchid: str):
    events = await db.matchzy_events.find({"matchid": matchid}, {"_id": 0}).sort("received_at", 1).to_list(1000)
    if not events:
        allev = await db.matchzy_events.find({}, {"_id": 0}).sort("received_at", 1).to_list(2000)
        events = [e for e in allev if str(e.get("matchid")) == str(matchid)]
    if not events:
        raise HTTPException(404, "Match introuvable")
    latest: dict = {}
    for e in events:
        _merge_latest(latest, _extract_score(e.get("payload") or {}))
    server = await db.cs2_servers.find_one({"current_match_id": str(matchid)}, {"_id": 0, "rcon_password": 0})
    return {
        "matchid": str(matchid),
        "summary": latest,
        "ended": any(e["event"] == "series_end" for e in events),
        "timeline": events,
        "server": server,
    }


@api_router.get("/matches/{matchid}/reports", dependencies=[Depends(get_current_user)])
async def list_match_reports(matchid: str, user=Depends(get_current_user)):
    docs = await db.match_reports.find({"match_id": str(matchid)}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return docs


@api_router.post("/matches/{matchid}/reports", dependencies=[Depends(get_current_user)])
async def create_match_report(matchid: str, req: MatchReportReq, user=Depends(get_current_user)):
    exists = await db.matchzy_events.find_one({"matchid": str(matchid)}, {"_id": 1})
    if not exists:
        all_events = await db.matchzy_events.find({}, {"_id": 0, "matchid": 1}).limit(2000).to_list(2000)
        if not any(str(doc.get("matchid")) == str(matchid) for doc in all_events):
            raise HTTPException(404, "Match introuvable")

    now_iso = datetime.now(timezone.utc).isoformat()
    report = {
        "id": str(uuid.uuid4()),
        "match_id": str(matchid),
        "kind": req.kind,
        "message": req.message.strip(),
        "round_label": (req.round_label or "").strip() or None,
        "status": "open",
        "reporter_user_id": user["id"],
        "reporter_pseudo": user["pseudo"],
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    await db.match_reports.insert_one(report)
    await journal("match_report_created", user["id"], {"match_id": str(matchid), "kind": req.kind})
    return report


@api_router.get("/admin/matches/reports", dependencies=[Depends(get_admin_user)])
async def admin_list_match_reports(status_f: Optional[str] = None, limit: int = 100):
    query = {}
    if status_f:
        query["status"] = status_f
    safe_limit = max(1, min(limit, 300))
    return await db.match_reports.find(query, {"_id": 0}).sort("created_at", -1).to_list(safe_limit)


@api_router.patch("/admin/matches/reports/{report_id}", dependencies=[Depends(get_admin_user)])
async def admin_update_match_report(report_id: str, req: MatchReportStatusReq, admin=Depends(get_admin_user)):
    existing = await db.match_reports.find_one({"id": report_id}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "Signalement introuvable")

    updates = {
        "status": req.status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "handled_by": admin["id"],
        "handled_by_pseudo": admin["pseudo"],
    }
    if req.resolution_note is not None:
        updates["resolution_note"] = req.resolution_note.strip()
    await db.match_reports.update_one({"id": report_id}, {"$set": updates})
    await journal("match_report_updated", admin["id"], {"report_id": report_id, "status": req.status})
    return {"ok": True, "id": report_id, "status": req.status}

app.include_router(api_router)

# ============= ITÉRATION 7 — Cartons + Duels 1v1 (Mongo persistence) =============
cards_router = APIRouter(prefix="/api/cards")
duels_router = APIRouter(prefix="/api/duels")

class CardReq(BaseModel):
    target_user_id: str
    severity: str  # "yellow" or "red"
    reason: str = Field(min_length=3, max_length=500)
    match_id: Optional[str] = None

@cards_router.post("", dependencies=[Depends(get_current_user)])
async def issue_card(req: CardReq, issuer=Depends(get_current_user)):
    if req.severity not in ("yellow", "red"):
        raise HTTPException(400, "severity must be 'yellow' or 'red'")
    target = await db.users.find_one({"id": req.target_user_id}, {"_id": 0, "password_hash": 0})
    if not target: raise HTTPException(404, "Joueur cible introuvable")
    card = {
        "id": str(uuid.uuid4()), "target_user_id": req.target_user_id,
        "target_pseudo": target["pseudo"], "issuer_user_id": issuer["id"],
        "issuer_pseudo": issuer["pseudo"], "severity": req.severity,
        "reason": req.reason, "match_id": req.match_id,
        "status": "active", "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.cards.insert_one(card)
    await journal("card_issued", issuer["id"], {"target": req.target_user_id, "severity": req.severity, "reason": req.reason})
    # Auto-escalation: 3 yellow cards = 1 red card
    yellows = await db.cards.count_documents({"target_user_id": req.target_user_id, "severity": "yellow", "status": "active"})
    auto_red = None
    if req.severity == "yellow" and yellows >= 3:
        auto_red = {
            "id": str(uuid.uuid4()), "target_user_id": req.target_user_id,
            "target_pseudo": target["pseudo"], "issuer_user_id": "system",
            "issuer_pseudo": "Système", "severity": "red",
            "reason": f"Auto-escalation : {yellows} cartons jaunes cumulés",
            "match_id": None, "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(), "auto": True,
        }
        await db.cards.insert_one(auto_red)
        await journal("card_auto_escalated", None, {"target": req.target_user_id, "yellows": yellows})
    return {"card": {k: v for k, v in card.items() if k != "_id"}, "auto_red_triggered": auto_red is not None}

@cards_router.get("")
async def list_cards(target_user_id: Optional[str] = None, severity: Optional[str] = None, status_f: Optional[str] = None):
    q = {}
    if target_user_id: q["target_user_id"] = target_user_id
    if severity: q["severity"] = severity
    if status_f: q["status"] = status_f
    docs = await db.cards.find(q, {"_id": 0}).sort("created_at", -1).to_list(100)
    return docs

@cards_router.post("/{card_id}/revoke", dependencies=[Depends(get_current_user)])
async def revoke_card(card_id: str, mod=Depends(get_current_user)):
    r = await db.cards.update_one({"id": card_id, "status": "active"}, {"$set": {"status": "revoked", "revoked_by": mod["id"], "revoked_at": datetime.now(timezone.utc).isoformat()}})
    if r.modified_count == 0: raise HTTPException(404, "Carton introuvable ou déjà levé")
    await journal("card_revoked", mod["id"], {"card_id": card_id})
    return {"ok": True}

# ----- DUELS 1v1 (virtual tokens, no real value) -----
class DuelReq(BaseModel):
    map_: str = Field(alias="map", min_length=2, max_length=24)
    stake: int = Field(ge=10, le=5000)
    class Config: populate_by_name = True

async def get_balance(user_id: str) -> int:
    u = await db.users.find_one({"id": user_id}, {"tokens": 1})
    if not u: return 0
    if "tokens" not in u:
        await db.users.update_one({"id": user_id}, {"$set": {"tokens": 1000}})
        return 1000
    return u["tokens"]

@duels_router.get("/balance", dependencies=[Depends(get_current_user)])
async def my_balance(user=Depends(get_current_user)):
    return {"user_id": user["id"], "tokens": await get_balance(user["id"])}

@duels_router.post("/create", dependencies=[Depends(get_current_user)])
async def create_duel(req: DuelReq, user=Depends(get_current_user)):
    bal = await get_balance(user["id"])
    if bal < req.stake: raise HTTPException(400, f"Solde insuffisant ({bal} jetons)")
    # Reserve stake
    await db.users.update_one({"id": user["id"]}, {"$inc": {"tokens": -req.stake}})
    duel = {
        "id": str(uuid.uuid4()), "creator_id": user["id"], "creator_pseudo": user["pseudo"],
        "opponent_id": None, "opponent_pseudo": None,
        "map": req.map_, "stake": req.stake, "status": "open",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.duels.insert_one(duel)
    await journal("duel_created", user["id"], {"duel_id": duel["id"], "stake": req.stake, "map": req.map_})
    return {k: v for k, v in duel.items() if k != "_id"}

@duels_router.get("")
async def list_open_duels(status_f: str = "open"):
    docs = await db.duels.find({"status": status_f}, {"_id": 0}).sort("created_at", -1).to_list(50)
    return docs

@duels_router.post("/{duel_id}/accept", dependencies=[Depends(get_current_user)])
async def accept_duel(duel_id: str, user=Depends(get_current_user)):
    duel = await db.duels.find_one({"id": duel_id})
    if not duel: raise HTTPException(404, "Duel introuvable")
    if duel["status"] != "open": raise HTTPException(400, "Duel déjà accepté ou clos")
    if duel["creator_id"] == user["id"]: raise HTTPException(400, "Impossible d'accepter son propre duel")
    bal = await get_balance(user["id"])
    if bal < duel["stake"]: raise HTTPException(400, f"Solde insuffisant ({bal} jetons)")
    await db.users.update_one({"id": user["id"]}, {"$inc": {"tokens": -duel["stake"]}})
    await db.duels.update_one({"id": duel_id, "status": "open"},
        {"$set": {"opponent_id": user["id"], "opponent_pseudo": user["pseudo"],
                  "status": "in_progress", "started_at": datetime.now(timezone.utc).isoformat()}})
    await journal("duel_accepted", user["id"], {"duel_id": duel_id})
    return {"ok": True, "duel_id": duel_id}

class DuelResultReq(BaseModel):
    winner_id: str

@duels_router.post("/{duel_id}/result", dependencies=[Depends(get_current_user)])
async def report_result(duel_id: str, req: DuelResultReq, reporter=Depends(get_current_user)):
    duel = await db.duels.find_one({"id": duel_id})
    if not duel: raise HTTPException(404, "Duel introuvable")
    if duel["status"] != "in_progress": raise HTTPException(400, "Duel non en cours")
    if req.winner_id not in (duel["creator_id"], duel["opponent_id"]):
        raise HTTPException(400, "Le gagnant doit être l'un des 2 participants")
    pot = duel["stake"] * 2
    await db.users.update_one({"id": req.winner_id}, {"$inc": {"tokens": pot}})
    await db.duels.update_one({"id": duel_id, "status": "in_progress"},
        {"$set": {"status": "closed", "winner_id": req.winner_id, "closed_at": datetime.now(timezone.utc).isoformat()}})
    await journal("duel_closed", reporter["id"], {"duel_id": duel_id, "winner": req.winner_id, "pot": pot})
    return {"ok": True, "winner_id": req.winner_id, "pot_awarded": pot}

app.include_router(cards_router)
app.include_router(duels_router)
app.include_router(build_cs2_router(db, get_current_user, get_admin_user, journal))
app.include_router(build_bracket_router(db, get_admin_user, journal))

app.add_middleware(
    CORSMiddleware,
    allow_credentials=env_flag("CORS_ALLOW_CREDENTIALS", False),
    allow_origins=parse_csv_env("CORS_ORIGINS", DEFAULT_CORS_ORIGINS),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def _scheduler_loop():
    """Polls the Redis job queue every second and applies due tournament jobs."""
    while True:
        try:
            for job in await rs.pop_due_jobs(time.time()):
                if job.get("type") == "tournament_transition":
                    tid = job["tournament_id"]
                    t = await db.tournaments.find_one({"id": tid})
                    if t and t["status"] == job.get("from"):
                        await db.tournaments.update_one({"id": tid}, {"$set": {"status": job["to"], "status_changed_at": datetime.now(timezone.utc).isoformat()}})
                        await journal("tournament_auto_transition", None, {"tournament_id": tid, "to": job["to"]})
        except Exception as e:
            logger.warning(f"scheduler error: {e}")
        await asyncio.sleep(1)


async def _seed_admin_user():
    admin_email = env_text("SEED_ADMIN_EMAIL").lower()
    admin_password = env_text("SEED_ADMIN_PASSWORD")
    if not admin_email or not admin_password:
        logger.info("Admin seed skipped: set SEED_ADMIN_EMAIL and SEED_ADMIN_PASSWORD to create an initial account.")
        return

    if await db.users.find_one({"email": admin_email}):
        return

    await db.users.insert_one({
        "id": str(uuid.uuid4()),
        "pseudo": env_text("SEED_ADMIN_PSEUDO", "Admin"),
        "email": admin_email,
        "password_hash": hash_password(admin_password),
        "country": env_text("SEED_ADMIN_COUNTRY", "FR"),
        "gender": None,
        "age": None,
        "bio": None,
        "custom_avatar_url": None,
        "steam_avatar_url": None,
        "level": 1,
        "xp": 0,
        "elo": 1000,
        "platform_elo": 1000,
        "faceit_elo": None,
        "premier_rating": None,
        "premier_status": None,
        "steam_verified": False,
        "steam_id": None,
        "tokens": int(env_text("SEED_ADMIN_TOKENS", "1000")),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    logger.info("Seeded initial admin account from environment configuration")


async def _backfill_user_stats():
    async for user in db.users.find({}, {"_id": 0}):
        updates = {}
        if "platform_elo" not in user:
            updates["platform_elo"] = int(user.get("elo", 1000))
        if "role" not in user:
            updates["role"] = "Polyvalent"
        if "reliability" not in user:
            updates["reliability"] = 50
        if "stats_last_sync_at" not in user:
            updates["stats_last_sync_at"] = None
        if "premier_status" not in user:
            updates["premier_status"] = None
        for field in ("gender", "age", "bio", "custom_avatar_url", "steam_avatar_url"):
            if field not in user:
                updates[field] = None
        computed_kdr = _compute_kdr(user)
        if computed_kdr is not None and user.get("kdr") != computed_kdr:
            updates["kdr"] = computed_kdr
        if updates:
            await db.users.update_one({"id": user["id"]}, {"$set": updates})

@app.on_event("startup")
async def _startup():
    await seed_all(db)
    if JWT_SECRET == DEV_JWT_SECRET:
        logger.warning("JWT_SECRET is using the insecure development default. Set a strong production secret before deploying.")
    if not os.environ.get("RCON_ENC_KEY"):
        logger.warning("RCON_ENC_KEY is missing. RCON passwords will not be encrypted at rest.")
    if not STRIPE_API_KEY:
        logger.info("Stripe donations are disabled: STRIPE_API_KEY is not configured.")
    await _seed_admin_user()
    await _backfill_user_stats()
    # Resume any countdowns persisted in Redis (survive backend reboots)
    for tid in await rs.active_countdowns():
        asyncio.create_task(countdown_task(tid))
    asyncio.create_task(_scheduler_loop())
    logger.info("ReadyUp Arena startup: seed + countdown resume + scheduler ready")

@app.on_event("shutdown")
async def shutdown_db_client(): client.close()
