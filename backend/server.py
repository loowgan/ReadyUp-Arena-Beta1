from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, WebSocket, WebSocketDisconnect, Query, Header
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import asyncio, html, json, re, time
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os, logging, uuid, random, secrets, hashlib
import bcrypt, httpx
from jose import jwt, JWTError
from urllib.parse import urlencode, urlparse
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import Any, List, Optional
from datetime import datetime, timezone, timedelta
from pymongo import ReturnDocument

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
from cs2 import (
    backend_public_base,
    build_live_matches_snapshot,
    build_cs2_router,
    build_duel_matchzy_config,
    build_server_connect_url,
    configure_matchzy_remote_log,
    matchzy_config_header,
    matchzy_load_url_command,
    public_server_payload,
    run_server_command,
)
from bracket import build_bracket_router
from email_service import send_email, reset_email_html
from fun_matches import FUN_MATCH_PLAYER_CAP, summarize_fun_match

app = FastAPI(title="ReadyUp Arena API")
api_router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)

DEFAULT_FRONTEND_URL = "http://localhost:3000"
DEFAULT_CORS_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"
DEV_JWT_SECRET = "readyup-arena-dev-secret-change-in-prod"
TWITCH_TOKEN_URL = "https://id.twitch.tv/oauth2/token"
TWITCH_HELIX_BASE_URL = "https://api.twitch.tv/helix"
_twitch_app_token: Optional[str] = None
_twitch_app_token_expires_at: float = 0.0


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


def _twitch_fallback_payload(channel: str, configured: bool, message: str, source: str) -> dict[str, Any]:
    return {
        "channel": channel,
        "display_name": channel,
        "live": False,
        "configured": configured,
        "source": source,
        "title": None,
        "viewers": None,
        "game": "Counter-Strike 2",
        "started_at": None,
        "thumbnail_url": None,
        "avatar_url": None,
        "url": f"https://twitch.tv/{channel}",
        "status_message": message,
    }


async def _get_twitch_app_access_token(client_http: httpx.AsyncClient) -> Optional[str]:
    global _twitch_app_token, _twitch_app_token_expires_at

    if _twitch_app_token and time.time() < (_twitch_app_token_expires_at - 60):
        return _twitch_app_token

    client_id = env_text("TWITCH_CLIENT_ID")
    client_secret = env_text("TWITCH_CLIENT_SECRET")
    if not client_id or not client_secret:
        return None

    response = await client_http.post(
        TWITCH_TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "client_credentials",
        },
    )
    response.raise_for_status()
    payload = response.json()
    token = str(payload.get("access_token") or "").strip()
    if not token:
        return None

    _twitch_app_token = token
    _twitch_app_token_expires_at = time.time() + int(payload.get("expires_in") or 0)
    return token


async def _fetch_twitch_live_snapshot() -> dict[str, Any]:
    channel = env_text("TWITCH_CHANNEL", "esl_csgo")
    if not env_flag("FEATURE_TWITCH", True):
        return _twitch_fallback_payload(channel, False, "Integration Twitch desactivee.", "disabled")

    client_id = env_text("TWITCH_CLIENT_ID")
    client_secret = env_text("TWITCH_CLIENT_SECRET")
    if not client_id or not client_secret:
        return _twitch_fallback_payload(
            channel,
            False,
            "Ajoute TWITCH_CLIENT_ID et TWITCH_CLIENT_SECRET pour obtenir l'etat live reel.",
            "unconfigured",
        )

    async with httpx.AsyncClient(timeout=10) as client_http:
        token = await _get_twitch_app_access_token(client_http)
        if not token:
            return _twitch_fallback_payload(channel, False, "Impossible d'obtenir un token Twitch.", "auth_error")

        headers = {"Client-Id": client_id, "Authorization": f"Bearer {token}"}
        stream_response, user_response = await asyncio.gather(
            client_http.get(f"{TWITCH_HELIX_BASE_URL}/streams", headers=headers, params={"user_login": channel}),
            client_http.get(f"{TWITCH_HELIX_BASE_URL}/users", headers=headers, params={"login": channel}),
        )
        stream_response.raise_for_status()
        user_response.raise_for_status()

    stream = (stream_response.json().get("data") or [None])[0]
    user = (user_response.json().get("data") or [None])[0]
    display_name = (user or {}).get("display_name") or channel
    avatar_url = (user or {}).get("profile_image_url")
    channel_url = f"https://twitch.tv/{channel}"

    if not stream:
        return {
            "channel": channel,
            "display_name": display_name,
            "live": False,
            "configured": True,
            "source": "twitch_api",
            "title": None,
            "viewers": None,
            "game": "Counter-Strike 2",
            "started_at": None,
            "thumbnail_url": None,
            "avatar_url": avatar_url,
            "url": channel_url,
            "status_message": "Chaine hors ligne actuellement.",
        }

    thumbnail_url = stream.get("thumbnail_url")
    if isinstance(thumbnail_url, str):
        thumbnail_url = thumbnail_url.replace("{width}", "1280").replace("{height}", "720")

    return {
        "channel": stream.get("user_login") or channel,
        "display_name": stream.get("user_name") or display_name,
        "live": True,
        "configured": True,
        "source": "twitch_api",
        "title": stream.get("title"),
        "viewers": stream.get("viewer_count"),
        "game": stream.get("game_name") or "Counter-Strike 2",
        "started_at": stream.get("started_at"),
        "thumbnail_url": thumbnail_url,
        "avatar_url": avatar_url,
        "url": channel_url,
        "status_message": "Live detecte via Twitch API.",
    }

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


class SteamMergeConfirmReq(BaseModel):
    token: str = Field(min_length=16, max_length=2048)
    strategy: str = Field(pattern="^(keep_current|keep_other_progression)$")


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


def make_steam_link_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "kind": "steam_link",
        "exp": now + timedelta(minutes=10),
        "iat": now,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def make_steam_merge_token(current_user_id: str, other_user_id: str, steam_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": current_user_id,
        "other_user_id": other_user_id,
        "steam_id": steam_id,
        "kind": "steam_merge",
        "exp": now + timedelta(minutes=10),
        "iat": now,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


class SteamMergeRequired(Exception):
    def __init__(self, merge_token: str):
        self.merge_token = merge_token
        super().__init__("steam_merge_required")

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
    twitch_enabled = env_flag("FEATURE_TWITCH", True)
    twitch_ready = bool(env_text("TWITCH_CLIENT_ID") and env_text("TWITCH_CLIENT_SECRET"))
    backend_public_url = env_text("BACKEND_PUBLIC_URL")
    matchzy_webhook_ready = bool(env_text("MATCHZY_WEBHOOK_SECRET"))
    matchzy_config_ready = bool(env_text("MATCHZY_CONFIG_TOKEN"))
    email_ready = bool(env_text("RESEND_API_KEY") and env_text("SENDER_EMAIL"))
    return {
        "app_name": "ReadyUp Arena",
        "tagline": "Formez votre équipe. Entrez dans l'arène. Devenez champion.",
        "feature_steam_auth": env_flag("FEATURE_STEAM_AUTH", True),
        "feature_twitch": twitch_enabled,
        "feature_stripe": stripe_enabled,
        "feature_paypal": env_flag("FEATURE_PAYPAL", True),
        "feature_csstats": env_flag("FEATURE_CSSTATS", True),
        "twitch_channel": os.environ.get("TWITCH_CHANNEL", "esl_csgo"),
        "integrations": {
            "twitch": {
                "enabled": twitch_enabled,
                "configured": twitch_ready,
                "channel": os.environ.get("TWITCH_CHANNEL", "esl_csgo"),
            },
            "matchzy": {
                "public_base_configured": bool(backend_public_url),
                "webhook_secret_configured": matchzy_webhook_ready,
                "config_token_configured": matchzy_config_ready,
            },
            "email": {
                "configured": email_ready,
            },
        },
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


AUTO_TEAM_SIZE = 5
AUTO_TEAM_MIN_TEAMS = 2
AUTO_TEAM_COLORS = ["#FF4600", "#00F0FF", "#FF003C", "#10B981", "#8B5CF6", "#FFB800"]


def _auto_solo_team_count(solo_count: int, slots_remaining: int) -> int:
    if slots_remaining <= 0:
        return 0
    possible_teams = min(max(int(solo_count or 0), 0) // AUTO_TEAM_SIZE, slots_remaining)
    return possible_teams if possible_teams >= AUTO_TEAM_MIN_TEAMS else 0


def _summarize_tournament_registration_counts(capacity: int, manual_team_count: int, solo_count: int) -> dict:
    manual_team_count = max(int(manual_team_count or 0), 0)
    solo_count = max(int(solo_count or 0), 0)
    capacity = max(int(capacity or 0), 0)
    slots_remaining_from_manual = max(capacity - manual_team_count, 0)
    auto_generated_teams_count = _auto_solo_team_count(solo_count, slots_remaining_from_manual)
    registered_effective = manual_team_count + auto_generated_teams_count
    solo_waiting_count = max(solo_count - (auto_generated_teams_count * AUTO_TEAM_SIZE), 0)
    max_solo_players = slots_remaining_from_manual * AUTO_TEAM_SIZE if slots_remaining_from_manual >= AUTO_TEAM_MIN_TEAMS else 0
    return {
        "manual_teams_count": manual_team_count,
        "solo_queue_original_count": solo_count,
        "slots_remaining_from_manual": slots_remaining_from_manual,
        "auto_generated_teams_count": auto_generated_teams_count,
        "registered_effective": registered_effective,
        "solo_waiting_count": solo_waiting_count,
        "team_slots_remaining": max(capacity - registered_effective, 0),
        "solo_slots_remaining": max(max_solo_players - solo_count, 0),
        "max_solo_players": max_solo_players,
    }


def _build_auto_solo_teams(solo_entries: list[dict], slots_remaining: int) -> tuple[list[dict], list[dict]]:
    auto_team_count = _auto_solo_team_count(len(solo_entries), slots_remaining)
    if auto_team_count <= 0:
        return [], solo_entries

    teams: list[dict] = []
    consumed = auto_team_count * AUTO_TEAM_SIZE
    for index in range(auto_team_count):
        chunk = solo_entries[index * AUTO_TEAM_SIZE:(index + 1) * AUTO_TEAM_SIZE]
        if len(chunk) < AUTO_TEAM_SIZE:
            break
        avg_elo = round(sum(float(player.get("elo") or 0) for player in chunk) / len(chunk))
        avg_level = round(sum(float(player.get("level") or 1) for player in chunk) / len(chunk))
        avg_reliability = round(sum(float(player.get("reliability") or 50) for player in chunk) / len(chunk))
        team_name = f"Escouade solo {index + 1}"
        color = AUTO_TEAM_COLORS[index % len(AUTO_TEAM_COLORS)]
        teams.append({
            "id": f"auto-solo-{index + 1}",
            "name": team_name,
            "tag": f"S{index + 1:02d}",
            "logo_color": color,
            "country": chunk[0].get("country") or "EU",
            "level": avg_level,
            "elo": avg_elo,
            "wins": 0,
            "losses": 0,
            "trophies": 0,
            "reliability": avg_reliability,
            "members_count": len(chunk),
            "members_limit": AUTO_TEAM_SIZE,
            "captain_pseudo": chunk[0].get("pseudo"),
            "description": "Equipe auto-composee a partir de la file solo du tournoi.",
            "language": "MULTI",
            "discord_url": None,
            "recruitment_status": "closed",
            "members": chunk,
            "generated_from_solos": True,
        })
    return teams, solo_entries[consumed:]


async def _build_tournament_registration_snapshot(tournament_doc: dict) -> dict:
    tid = tournament_doc["id"]
    regs = await db.tournament_registrations.find({"tournament_id": tid}, {"_id": 0}).sort("created_at", 1).to_list(300)

    team_entries: list[dict] = []
    solo_entries: list[dict] = []

    for reg in regs:
        if reg["entity_type"] == "team":
            team_doc = await db.teams.find_one({"id": reg.get("entity_id")}, {"_id": 0}) if reg.get("entity_id") else None
            team_entries.append(team_doc or {
                "id": reg["id"],
                "name": reg["entity_name"],
                "tag": reg["entity_name"][:4].upper(),
                "elo": 0,
                "logo_color": "#6b7280",
                "country": "EU",
                "level": 1,
                "wins": 0,
                "losses": 0,
                "trophies": 0,
                "reliability": 50,
                "members_count": AUTO_TEAM_SIZE,
                "members_limit": AUTO_TEAM_SIZE,
                "captain_pseudo": None,
                "generated_from_solos": False,
            })
            continue

        user_doc = await db.users.find_one({"id": reg.get("user_id")}, {"_id": 0, "password_hash": 0})
        player_doc = None
        if not user_doc and reg.get("entity_id"):
            player_doc = await db.players.find_one({"id": reg.get("entity_id")}, {"_id": 0})
        source_doc = user_doc or player_doc or {}
        solo_entries.append({
            "id": source_doc.get("id") or reg["id"],
            "pseudo": source_doc.get("pseudo") or reg["entity_name"],
            "role": source_doc.get("role") or "Polyvalent",
            "online": bool(source_doc.get("online", True)),
            "steam_verified": bool(source_doc.get("steam_verified", False)),
            "country": source_doc.get("country") or "EU",
            "level": source_doc.get("level") or 1,
            "elo": source_doc.get("platform_elo", source_doc.get("elo", 1000)),
            "faceit_elo": source_doc.get("faceit_elo"),
            "premier_rating": source_doc.get("premier_rating"),
            "kdr": _compute_kdr(source_doc) if source_doc else None,
            "reliability": source_doc.get("reliability", 50),
            "rank_cs2": source_doc.get("rank_cs2"),
            "avatar_url": source_doc.get("custom_avatar_url") or source_doc.get("steam_avatar_url"),
            "source": "solo_registration",
        })

    summary = _summarize_tournament_registration_counts(
        int(tournament_doc.get("capacity", 0) or 0),
        len(team_entries),
        len(solo_entries),
    )
    slots_remaining = summary["slots_remaining_from_manual"]
    auto_teams, remaining_solos = _build_auto_solo_teams(solo_entries, slots_remaining)

    return {
        "registrations": regs,
        "teams_in": [*team_entries, *auto_teams],
        "auto_generated_teams": auto_teams,
        "solo_queue": remaining_solos,
        "manual_teams_count": summary["manual_teams_count"],
        "auto_generated_teams_count": summary["auto_generated_teams_count"],
        "solo_queue_original_count": summary["solo_queue_original_count"],
        "solo_waiting_count": len(remaining_solos),
        "registered_effective": summary["registered_effective"],
        "team_slots_remaining": summary["team_slots_remaining"],
        "solo_slots_remaining": summary["solo_slots_remaining"],
        "max_solo_players": summary["max_solo_players"],
        "registrations_count": len(regs),
    }


async def _build_tournament_registration_summary(tournament_doc: dict) -> dict:
    regs = await db.tournament_registrations.find(
        {"tournament_id": tournament_doc["id"]},
        {"_id": 0, "entity_type": 1},
    ).to_list(300)
    manual_team_count = sum(1 for reg in regs if reg.get("entity_type") == "team")
    solo_count = len(regs) - manual_team_count
    return {
        **_summarize_tournament_registration_counts(
            int(tournament_doc.get("capacity", 0) or 0),
            manual_team_count,
            solo_count,
        ),
        "registrations_count": len(regs),
    }


def _tournament_response_payload(tournament_doc: dict, snapshot: dict, include_lists: bool = False) -> dict:
    registration_open = tournament_doc.get("status") in ("open", "registering")
    payload = {
        **tournament_doc,
        "registered": snapshot["registered_effective"],
        "registered_effective": snapshot["registered_effective"],
        "registrations_count": snapshot["registrations_count"],
        "manual_teams_count": snapshot["manual_teams_count"],
        "auto_generated_teams_count": snapshot["auto_generated_teams_count"],
        "solo_queue_original_count": snapshot["solo_queue_original_count"],
        "solo_waiting_count": snapshot["solo_waiting_count"],
        "team_slots_remaining": snapshot["team_slots_remaining"],
        "solo_slots_remaining": snapshot["solo_slots_remaining"],
        "can_register_team": registration_open and snapshot["team_slots_remaining"] > 0,
        "can_register_solo": registration_open and snapshot["solo_slots_remaining"] > 0,
    }
    if include_lists:
        payload["teams_in"] = snapshot["teams_in"]
        payload["solo_queue"] = snapshot["solo_queue"]
        payload["auto_generated_teams"] = snapshot["auto_generated_teams"]
    return payload


def _seconds_until_iso(value: Optional[str]) -> int:
    target = _parse_iso_or_min(value)
    if target == datetime.min.replace(tzinfo=timezone.utc):
        return 0
    return max(int(round((target - datetime.now(timezone.utc)).total_seconds())), 0)


def _countdown_label(seconds: int) -> str:
    clipped = max(int(seconds or 0), 0)
    minutes, remaining_seconds = divmod(clipped, 60)
    return f"T-{minutes}:{remaining_seconds:02d}"


def _build_waiting_room_events(snapshot: dict, starts_in_seconds: int) -> list[dict]:
    events: list[dict] = []
    if starts_in_seconds > 0 and starts_in_seconds <= 300:
        events.append({
            "time": _countdown_label(starts_in_seconds),
            "type": "countdown",
            "msg": "Compte a rebours actif avant lancement.",
        })
    if snapshot["manual_teams_count"] > 0:
        events.append({
            "time": "LIVE",
            "type": "teams_registered",
            "msg": f"{snapshot['manual_teams_count']} equipe(s) complete(s) deja validee(s).",
        })
    if snapshot["auto_generated_teams_count"] > 0:
        events.append({
            "time": "LIVE",
            "type": "solo_teams_ready",
            "msg": f"{snapshot['auto_generated_teams_count']} equipe(s) auto-composee(s) depuis la file solo.",
        })
    if snapshot["solo_waiting_count"] > 0:
        events.append({
            "time": "LIVE",
            "type": "solo_waiting",
            "msg": f"{snapshot['solo_waiting_count']} joueur(s) attend(ent) encore une escouade complete.",
        })
    if not events:
        events.append({
            "time": "LIVE",
            "type": "idle",
            "msg": "Salle d'attente ouverte. En attente des prochaines inscriptions.",
        })
    return events[:6]


async def _resolve_available_pseudo(base_pseudo: str, user_id: Optional[str] = None, fallback_suffix: Optional[str] = None) -> str:
    candidate = (base_pseudo or "").strip()[:24]
    if not candidate:
        candidate = f"Steam_{(fallback_suffix or uuid.uuid4().hex[-6:])[-6:]}"
    query = {"pseudo": candidate}
    if user_id:
        query["id"] = {"$ne": user_id}
    taken = await db.users.find_one(query, {"_id": 0, "id": 1})
    if not taken:
        return candidate
    suffix = (fallback_suffix or uuid.uuid4().hex[-4:])[-4:]
    return f"{candidate[:19]}_{suffix}"


def _build_steam_user_doc(steam_id: str, request: Request) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "pseudo": f"Steam_{steam_id[-6:]}",
        "email": f"steam_{steam_id}@readyup.local",
        "password_hash": hash_password(uuid.uuid4().hex),
        "country": "??",
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
        "kills_30d": None,
        "deaths_30d": None,
        "kdr": None,
        "rank_cs2": None,
        "role": "Polyvalent",
        "reliability": 55,
        "stats_last_sync_at": None,
        "steam_verified": True,
        "steam_id": steam_id,
        "team_id": None,
        "team_role": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "ip": request.client.host if request.client else None,
    }


def _looks_placeholder_email(email: Optional[str]) -> bool:
    value = (email or "").strip().lower()
    return not value or value.endswith("@readyup.local")


def _looks_placeholder_pseudo(pseudo: Optional[str]) -> bool:
    value = (pseudo or "").strip()
    return not value or value.startswith("Steam_")


def _meaningful_text(value: Optional[str], invalid_values: Optional[set[str]] = None) -> bool:
    text = (value or "").strip()
    if not text:
        return False
    if invalid_values and text in invalid_values:
        return False
    return True


def _parse_iso_or_min(value: Optional[str]) -> datetime:
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


def _steam_stats_preferred_doc(primary: dict, secondary: dict) -> dict:
    primary_sync = _parse_iso_or_min(primary.get("stats_last_sync_at"))
    secondary_sync = _parse_iso_or_min(secondary.get("stats_last_sync_at"))
    return secondary if secondary_sync > primary_sync else primary


async def _load_user_from_steam_link_token(link_token: Optional[str]) -> Optional[dict]:
    if not link_token:
        return None
    try:
        payload = jwt.decode(link_token, JWT_SECRET, algorithms=[JWT_ALGO])
    except JWTError:
        raise HTTPException(401, "steam_link_invalid")
    if payload.get("kind") != "steam_link":
        raise HTTPException(401, "steam_link_invalid")
    user = await db.users.find_one({"id": payload.get("sub")}, {"_id": 0})
    if not user:
        raise HTTPException(401, "steam_link_invalid")
    return user


async def _load_steam_merge_token(merge_token: str, expected_user_id: Optional[str] = None) -> dict:
    try:
        payload = jwt.decode(merge_token, JWT_SECRET, algorithms=[JWT_ALGO])
    except JWTError:
        raise HTTPException(401, "steam_merge_invalid")
    if payload.get("kind") != "steam_merge":
        raise HTTPException(401, "steam_merge_invalid")
    if expected_user_id and payload.get("sub") != expected_user_id:
        raise HTTPException(403, "steam_merge_forbidden")
    return payload


def _progression_score(doc: dict) -> float:
    return (
        float(doc.get("level") or 0) * 100000
        + float(doc.get("xp") or 0) * 10
        + float(doc.get("platform_elo", doc.get("elo", 0)) or 0) * 25
        + float(doc.get("faceit_elo") or 0) * 15
        + float(doc.get("premier_rating") or 0) * 2
        + float(doc.get("tokens") or 0)
        + (float(doc.get("kdr") or 0) * 1000)
    )


def _select_progression_candidate(users: list[dict]) -> dict:
    return sorted(
        users,
        key=lambda doc: (_progression_score(doc), _parse_iso_or_min(doc.get("created_at"))),
        reverse=True,
    )[0]


def _steam_merge_preview_summary(doc: dict) -> dict:
    return {
        "id": doc["id"],
        "pseudo": doc.get("pseudo"),
        "email": doc.get("email"),
        "created_at": doc.get("created_at"),
        "country": doc.get("country"),
        "level": int(doc.get("level", 1) or 1),
        "xp": int(doc.get("xp", 0) or 0),
        "platform_elo": int(doc.get("platform_elo", doc.get("elo", 1000)) or 1000),
        "faceit_elo": doc.get("faceit_elo"),
        "premier_rating": doc.get("premier_rating"),
        "kdr": _compute_kdr(doc),
        "tokens": int(doc.get("tokens", 0) or 0),
        "rank_cs2": doc.get("rank_cs2"),
        "role": doc.get("role"),
        "team_id": doc.get("team_id"),
        "team_role": doc.get("team_role"),
        "avatar_url": doc.get("custom_avatar_url") or doc.get("steam_avatar_url"),
        "steam_verified": bool(doc.get("steam_verified")),
        "stats_last_sync_at": doc.get("stats_last_sync_at"),
        "progression_score": round(_progression_score(doc), 2),
    }


def _select_primary_steam_user(users: list[dict]) -> dict:
    return sorted(
        users,
        key=lambda doc: (
            0 if not _looks_placeholder_email(doc.get("email")) else 1,
            0 if not _looks_placeholder_pseudo(doc.get("pseudo")) else 1,
            _parse_iso_or_min(doc.get("created_at")),
        ),
    )[0]


async def _dedupe_contest_entries_for_user(user_id: str):
    entries = await db.contest_entries.find({"user_id": user_id}, {"_id": 0}).sort("created_at", 1).to_list(500)
    seen: set[str] = set()
    for entry in entries:
        contest_id = entry.get("contest_id")
        if not contest_id:
            continue
        if contest_id in seen:
            await db.contest_entries.delete_one({"id": entry["id"]})
            continue
        seen.add(contest_id)


async def _dedupe_tournament_registrations_for_user(user_id: str):
    regs = await db.tournament_registrations.find({"user_id": user_id}, {"_id": 0}).sort("created_at", 1).to_list(500)
    grouped: dict[str, list[dict]] = {}
    for reg in regs:
        grouped.setdefault(reg.get("tournament_id") or "", []).append(reg)

    for tournament_id, items in grouped.items():
        if not tournament_id or len(items) < 2:
            continue
        keep = sorted(items, key=lambda reg: (0 if reg.get("entity_type") == "team" else 1, reg.get("created_at") or ""))[0]
        for reg in items:
            if reg["id"] == keep["id"]:
                continue
            await db.tournament_registrations.delete_one({"id": reg["id"]})


async def _dedupe_team_applications_for_user(user_id: str):
    apps = await db.team_applications.find({"user_id": user_id}, {"_id": 0}).sort("created_at", 1).to_list(500)
    grouped: dict[str, list[dict]] = {}
    for app in apps:
        grouped.setdefault(app.get("team_id") or "", []).append(app)

    priority = {"approved": 0, "pending": 1, "rejected": 2}
    for team_id, items in grouped.items():
        if not team_id or len(items) < 2:
            continue
        keep = sorted(items, key=lambda app: (priority.get(app.get("status"), 9), app.get("created_at") or ""))[0]
        for app in items:
            if app["id"] == keep["id"]:
                continue
            await db.team_applications.delete_one({"id": app["id"]})


async def _merge_user_accounts(primary: dict, secondary: dict, reason: str, strategy: str = "smart") -> dict:
    if not secondary or primary["id"] == secondary["id"]:
        return primary

    stats_doc = _steam_stats_preferred_doc(primary, secondary)
    fallback_doc = secondary if stats_doc["id"] == primary["id"] else primary
    stats_fields = set(SYNC_MANAGED_FIELDS) | {
        "steam_avatar_url",
        "rank_cs2",
        "faceit_level",
        "faceit_recent_matches",
        "faceit_winrate",
        "faceit_headshots",
        "faceit_total_matches",
        "faceit_kills_per_round",
        "aim_rating",
        "utility_rating",
        "positioning_rating",
        "opening_duels_rating",
        "clutching_rating",
    }
    progression_fields = ("level", "xp", "elo", "platform_elo", "reliability", "tokens")
    final_steam_id = (primary.get("steam_id") or secondary.get("steam_id") or "").strip() or None
    updates = {
        "steam_id": final_steam_id,
        "steam_verified": bool(primary.get("steam_verified") or secondary.get("steam_verified") or final_steam_id),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    if _looks_placeholder_email(primary.get("email")) and not _looks_placeholder_email(secondary.get("email")):
        replacement_email = secondary.get("email", "").strip().lower()
        existing = await db.users.find_one(
            {"email": replacement_email, "id": {"$nin": [primary["id"], secondary["id"]]}},
            {"_id": 0, "id": 1},
        )
        if replacement_email and not existing:
            updates["email"] = replacement_email

    if _looks_placeholder_pseudo(primary.get("pseudo")) and not _looks_placeholder_pseudo(secondary.get("pseudo")):
        updates["pseudo"] = await _resolve_available_pseudo(secondary.get("pseudo"), primary["id"], (final_steam_id or primary["id"])[-4:])

    if not _meaningful_text(primary.get("country"), {"??"}) and _meaningful_text(secondary.get("country"), {"??"}):
        updates["country"] = secondary.get("country")

    for field in ("gender", "age", "bio", "custom_avatar_url", "steam_profile_url", "faceit_profile_url", "leetify_profile_url", "stats_profile_url", "role"):
        primary_value = primary.get(field)
        secondary_value = secondary.get(field)
        if primary_value in (None, "", []) and secondary_value not in (None, "", []):
            updates[field] = secondary_value

    if not primary.get("custom_avatar_url") and secondary.get("custom_avatar_url"):
        updates["custom_avatar_url"] = secondary.get("custom_avatar_url")
    if not primary.get("steam_avatar_url") and secondary.get("steam_avatar_url"):
        updates["steam_avatar_url"] = secondary.get("steam_avatar_url")

    if strategy == "keep_other_progression":
        for field in progression_fields:
            secondary_value = secondary.get(field)
            if secondary_value not in (None, "", []):
                updates[field] = secondary_value
        for field in stats_fields:
            secondary_value = secondary.get(field)
            if secondary_value not in (None, "", []):
                updates[field] = secondary_value
    elif strategy == "keep_current":
        for field in stats_fields:
            if field in updates:
                continue
            primary_value = primary.get(field)
            if primary_value not in (None, "", []):
                updates[field] = primary_value
    else:
        for numeric_field in ("level", "xp", "elo", "platform_elo", "reliability"):
            primary_value = primary.get(numeric_field)
            secondary_value = secondary.get(numeric_field)
            values = [value for value in (primary_value, secondary_value) if isinstance(value, (int, float))]
            if values:
                updates[numeric_field] = int(max(values))

        token_values = [value for value in (primary.get("tokens"), secondary.get("tokens")) if isinstance(value, int)]
        if token_values:
            updates["tokens"] = sum(token_values)

        for field in stats_fields:
            preferred_value = stats_doc.get(field)
            fallback_value = fallback_doc.get(field)
            if preferred_value not in (None, "", []):
                updates[field] = preferred_value
            elif field not in updates and fallback_value not in (None, "", []):
                updates[field] = fallback_value

    primary_team_id = primary.get("team_id")
    secondary_team_id = secondary.get("team_id")
    if not primary_team_id and secondary_team_id:
        updates["team_id"] = secondary_team_id
        updates["team_role"] = secondary.get("team_role")
        if secondary.get("team_role") == "captain":
            await db.teams.update_one({"captain_user_id": secondary["id"]}, {"$set": {"captain_user_id": primary["id"]}})
    elif primary_team_id and secondary_team_id and primary_team_id == secondary_team_id:
        if primary.get("team_role") != "captain" and secondary.get("team_role") == "captain":
            updates["team_role"] = "captain"
            await db.teams.update_one({"captain_user_id": secondary["id"]}, {"$set": {"captain_user_id": primary["id"]}})

    if _parse_iso_or_min(secondary.get("created_at")) < _parse_iso_or_min(primary.get("created_at")):
        updates["created_at"] = secondary.get("created_at")

    await db.users.update_one({"id": primary["id"]}, {"$set": updates})
    merged = await db.users.find_one({"id": primary["id"]}, {"_id": 0}) or {**primary, **updates}
    final_pseudo = merged.get("pseudo") or updates.get("pseudo") or primary.get("pseudo")

    await db.audit_logs.update_many({"user_id": secondary["id"]}, {"$set": {"user_id": primary["id"]}})
    await db.password_resets.update_many({"user_id": secondary["id"]}, {"$set": {"user_id": primary["id"]}})
    await db.team_applications.update_many({"user_id": secondary["id"]}, {"$set": {"user_id": primary["id"], "pseudo": final_pseudo}})
    await db.contest_entries.update_many({"user_id": secondary["id"]}, {"$set": {"user_id": primary["id"]}})
    await db.reward_redemptions.update_many({"user_id": secondary["id"]}, {"$set": {"user_id": primary["id"], "pseudo": final_pseudo}})
    await db.tournament_registrations.update_many({"user_id": secondary["id"]}, {"$set": {"user_id": primary["id"]}})
    await db.tournament_registrations.update_many(
        {"user_id": primary["id"], "entity_type": "solo"},
        {"$set": {"entity_name": final_pseudo}},
    )
    await db.match_reports.update_many(
        {"reporter_user_id": secondary["id"]},
        {"$set": {"reporter_user_id": primary["id"], "reporter_pseudo": final_pseudo}},
    )
    await db.match_reports.update_many(
        {"target_user_id": secondary["id"]},
        {"$set": {"target_user_id": primary["id"], "target_pseudo": final_pseudo}},
    )
    await db.cards.update_many(
        {"target_user_id": secondary["id"]},
        {"$set": {"target_user_id": primary["id"], "target_pseudo": final_pseudo}},
    )
    await db.cards.update_many(
        {"issuer_user_id": secondary["id"]},
        {"$set": {"issuer_user_id": primary["id"], "issuer_pseudo": final_pseudo}},
    )
    await db.duels.update_many(
        {"creator_id": secondary["id"]},
        {"$set": {"creator_id": primary["id"], "creator_pseudo": final_pseudo}},
    )
    await db.duels.update_many(
        {"opponent_id": secondary["id"]},
        {"$set": {"opponent_id": primary["id"], "opponent_pseudo": final_pseudo}},
    )
    await db.duels.update_many({"winner_id": secondary["id"]}, {"$set": {"winner_id": primary["id"]}})

    await _dedupe_contest_entries_for_user(primary["id"])
    await _dedupe_tournament_registrations_for_user(primary["id"])
    await _dedupe_team_applications_for_user(primary["id"])

    await db.users.delete_one({"id": secondary["id"]})
    await journal(
        "accounts_merged",
        primary["id"],
        {"from_user_id": secondary["id"], "steam_id": final_steam_id, "reason": reason},
    )
    return merged


async def _resolve_steam_user(steam_id: str, request: Request, link_token: Optional[str] = None) -> dict:
    linked_user = await _load_user_from_steam_link_token(link_token)
    steam_users = await db.users.find({"steam_id": steam_id}, {"_id": 0}).to_list(20)

    if linked_user and linked_user.get("steam_id") and linked_user.get("steam_id") != steam_id:
        raise HTTPException(409, "steam_link_conflict")

    if linked_user:
        duplicates = [doc for doc in steam_users if doc["id"] != linked_user["id"]]
        if duplicates:
            merge_candidate = _select_progression_candidate(duplicates)
            raise SteamMergeRequired(make_steam_merge_token(linked_user["id"], merge_candidate["id"], steam_id))
        if not any(doc["id"] == linked_user["id"] for doc in steam_users):
            await db.users.update_one(
                {"id": linked_user["id"]},
                {"$set": {"steam_id": steam_id, "steam_verified": True, "updated_at": datetime.now(timezone.utc).isoformat()}},
            )
            linked_user = await db.users.find_one({"id": linked_user["id"]}, {"_id": 0})
        return linked_user

    if steam_users:
        primary = _select_primary_steam_user(steam_users)
        for duplicate in steam_users:
            if duplicate["id"] == primary["id"]:
                continue
            primary = await _merge_user_accounts(primary, duplicate, "steam_duplicate_cleanup")
        if not primary.get("steam_verified"):
            await db.users.update_one(
                {"id": primary["id"]},
                {"$set": {"steam_verified": True, "updated_at": datetime.now(timezone.utc).isoformat()}},
            )
            primary = await db.users.find_one({"id": primary["id"]}, {"_id": 0}) or {**primary, "steam_verified": True}
        return primary

    user = _build_steam_user_doc(steam_id, request)
    await db.users.insert_one(user)
    await journal("steam_profile_created", user["id"], {"steam_id": steam_id})
    return user


async def _bootstrap_steam_profile(user: dict) -> dict:
    steam_id = (user.get("steam_id") or "").strip()
    if not steam_id or not steam_id.isdigit():
        return user

    try:
        updates = await _fetch_external_stats_for_steam_id(steam_id)
    except Exception as exc:
        logger.warning("steam bootstrap sync failed for steam_id=%s: %s", steam_id, exc)
        return user

    steam_display_name = updates.pop("_steam_display_name", None)
    current_pseudo = str(user.get("pseudo") or "").strip()
    if steam_display_name and (not current_pseudo or current_pseudo.startswith("Steam_")):
        updates["pseudo"] = await _resolve_available_pseudo(steam_display_name, user["id"], steam_id[-4:])

    updates["steam_verified"] = True
    updates["stats_last_sync_at"] = datetime.now(timezone.utc).isoformat()
    await db.users.update_one({"id": user["id"]}, {"$set": updates})
    refreshed = await db.users.find_one({"id": user["id"]}, {"_id": 0})
    return refreshed or {**user, **updates}


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


class TeamMemberAdminReq(BaseModel):
    source: str = Field(default="user", pattern="^(user|seed)$")
    role: Optional[str] = Field(default=None, pattern="^(captain|member)$")


class FunMatchCreateReq(BaseModel):
    title: str = Field(min_length=3, max_length=80)
    description: str = Field(default="", max_length=500)
    map: str = Field(default="de_dust2", min_length=2, max_length=32)


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


async def _assign_team_captain(team_id: str, new_captain: dict) -> None:
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.users.update_many({"team_id": team_id, "team_role": "captain"}, {"$set": {"team_role": "member"}})
    await db.users.update_one({"id": new_captain["id"]}, {"$set": {"team_role": "captain"}})
    await db.teams.update_one(
        {"id": team_id},
        {"$set": {"captain_user_id": new_captain["id"], "captain_pseudo": new_captain.get("pseudo"), "updated_at": now_iso}},
    )


async def _disband_team(team: dict, actor_user_id: str, reason: str, event_name: str = "team_disbanded") -> None:
    team_id = team["id"]
    await db.users.update_many({"team_id": team_id}, {"$set": {"team_id": None, "team_role": None}})
    await db.players.update_many({"team_id": team_id}, {"$set": {"team_id": None}})
    await db.teams.delete_one({"id": team_id})
    await db.team_applications.delete_many({"team_id": team_id})
    await db.tournament_registrations.delete_many({"entity_type": "team", "entity_id": team_id})
    await journal(event_name, actor_user_id, {"team_id": team_id, "name": team.get("name"), "reason": reason})


def _build_fun_match_player_entry(user: dict) -> dict:
    return {
        "user_id": user["id"],
        "pseudo": user.get("pseudo"),
        "steam_id": user.get("steam_id"),
        "steam_verified": bool(user.get("steam_verified")),
        "country": user.get("country") or "EU",
        "elo": user.get("platform_elo", user.get("elo", 1000)),
        "faceit_elo": user.get("faceit_elo"),
        "kdr": _compute_kdr(user),
        "reliability": user.get("reliability", 50),
        "avatar_url": user.get("custom_avatar_url") or user.get("steam_avatar_url"),
        "joined_at": datetime.now(timezone.utc).isoformat(),
    }


async def _get_fun_match_or_404(match_id: str) -> dict:
    doc = await db.fun_matches.find_one({"id": match_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Match fun introuvable")
    return doc


async def _ensure_user_not_in_other_fun_match(user_id: str, exclude_match_id: Optional[str] = None) -> None:
    docs = await db.fun_matches.find({"status": {"$in": ["open", "ready", "live"]}}, {"_id": 0, "id": 1, "players": 1}).to_list(200)
    for doc in docs:
        if exclude_match_id and str(doc.get("id")) == str(exclude_match_id):
            continue
        if any(str(player.get("user_id")) == str(user_id) for player in (doc.get("players") or [])):
            raise HTTPException(409, "Vous etes deja inscrit dans un autre match fun actif")


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
        await _disband_team(team, user["id"], "captain_left_team")
        return {"ok": True, "disbanded": True}

    await db.users.update_one({"id": user["id"]}, {"$set": {"team_id": None, "team_role": None}})
    await journal("team_left", user["id"], {"team_id": team_id})
    return {"ok": True, "disbanded": False}


@api_router.get("/admin/teams", dependencies=[Depends(get_admin_user)])
async def admin_list_teams():
    docs = await db.teams.find({}, {"_id": 0}).sort("elo", -1).to_list(200)
    return [await _team_public(doc, include_members=True) for doc in docs]


@api_router.patch("/admin/teams/{team_id}", dependencies=[Depends(get_admin_user)])
async def admin_update_team(team_id: str, req: TeamUpdateReq, admin=Depends(get_admin_user)):
    team = await _get_team_or_404(team_id)
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
    await journal("team_admin_updated", admin["id"], {"team_id": team_id, "name": team.get("name")})
    updated = await db.teams.find_one({"id": team_id}, {"_id": 0})
    return await _team_public(updated, include_members=True)


@api_router.delete("/admin/teams/{team_id}", dependencies=[Depends(get_admin_user)])
async def admin_delete_team(team_id: str, admin=Depends(get_admin_user)):
    team = await _get_team_or_404(team_id)
    await _disband_team(team, admin["id"], "admin_deleted_team", event_name="team_admin_deleted")
    return {"ok": True, "id": team_id}


@api_router.post("/admin/teams/{team_id}/members/{member_id}/role", dependencies=[Depends(get_admin_user)])
async def admin_set_team_member_role(team_id: str, member_id: str, req: TeamMemberAdminReq, admin=Depends(get_admin_user)):
    team = await _get_team_or_404(team_id)
    if req.source != "user":
        raise HTTPException(400, "Seuls les comptes joueurs peuvent devenir capitaine")
    member = await db.users.find_one({"id": member_id, "team_id": team_id}, {"_id": 0})
    if not member:
        raise HTTPException(404, "Membre introuvable")
    if req.role == "captain":
        await _assign_team_captain(team_id, member)
        await journal("team_admin_captain_changed", admin["id"], {"team_id": team_id, "member_id": member_id})
    elif team.get("captain_user_id") == member_id:
        raise HTTPException(400, "Promouvez un autre joueur avant de retirer le capitanat")
    else:
        await db.users.update_one({"id": member_id}, {"$set": {"team_role": "member"}})
        await journal("team_admin_role_changed", admin["id"], {"team_id": team_id, "member_id": member_id, "role": "member"})
    updated = await db.teams.find_one({"id": team_id}, {"_id": 0})
    return await _team_public(updated, include_members=True)


@api_router.post("/admin/teams/{team_id}/members/{member_id}/remove", dependencies=[Depends(get_admin_user)])
async def admin_remove_team_member(team_id: str, member_id: str, req: TeamMemberAdminReq, admin=Depends(get_admin_user)):
    team = await _get_team_or_404(team_id)
    if req.source == "seed":
        member = await db.players.find_one({"id": member_id, "team_id": team_id}, {"_id": 0})
        if not member:
            raise HTTPException(404, "Membre seed introuvable")
        await db.players.update_one({"id": member_id}, {"$set": {"team_id": None}})
        await journal("team_admin_member_removed", admin["id"], {"team_id": team_id, "member_id": member_id, "source": "seed"})
    else:
        member = await db.users.find_one({"id": member_id, "team_id": team_id}, {"_id": 0})
        if not member:
            raise HTTPException(404, "Membre introuvable")
        if team.get("captain_user_id") == member_id:
            other_users = await db.users.find({"team_id": team_id, "id": {"$ne": member_id}}, {"_id": 0}).to_list(20)
            if other_users:
                next_captain = sorted(other_users, key=lambda item: (str(item.get("team_role") or "") != "captain", str(item.get("pseudo") or "")))[0]
                await _assign_team_captain(team_id, next_captain)
                await db.users.update_one({"id": member_id}, {"$set": {"team_id": None, "team_role": None}})
            else:
                await _disband_team(team, admin["id"], "captain_removed_by_admin", event_name="team_admin_deleted")
                return {"ok": True, "id": member_id, "disbanded": True}
        else:
            await db.users.update_one({"id": member_id}, {"$set": {"team_id": None, "team_role": None}})
        await journal("team_admin_member_removed", admin["id"], {"team_id": team_id, "member_id": member_id, "source": "user"})
    updated = await db.teams.find_one({"id": team_id}, {"_id": 0})
    return await _team_public(updated, include_members=True)


@api_router.get("/fun-matches")
async def list_fun_matches():
    docs = await db.fun_matches.find({}, {"_id": 0}).sort("created_at", -1).to_list(50)
    return [summarize_fun_match(doc) for doc in docs]


@api_router.get("/fun-matches/{match_id}")
async def get_fun_match(match_id: str):
    return summarize_fun_match(await _get_fun_match_or_404(match_id))


@api_router.post("/fun-matches", dependencies=[Depends(get_current_user)])
async def create_fun_match(req: FunMatchCreateReq, user=Depends(get_current_user)):
    if not _has_steam_ready(user):
        raise HTTPException(400, "Liez votre compte Steam avant de creer un match fun 5v5")
    await _ensure_user_not_in_other_fun_match(user["id"])
    now_iso = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": str(uuid.uuid4()),
        "title": req.title.strip(),
        "description": req.description.strip(),
        "map": req.map.strip(),
        "creator_id": user["id"],
        "creator_pseudo": user["pseudo"],
        "status": "open",
        "players": [{**_build_fun_match_player_entry(user), "joined_at": now_iso}],
        "created_at": now_iso,
        "updated_at": now_iso,
        "closed_at": None,
    }
    await db.fun_matches.insert_one(doc)
    await journal("fun_match_created", user["id"], {"match_id": doc["id"], "title": doc["title"]})
    return summarize_fun_match(doc)


@api_router.post("/fun-matches/{match_id}/join", dependencies=[Depends(get_current_user)])
async def join_fun_match(match_id: str, user=Depends(get_current_user)):
    if not _has_steam_ready(user):
        raise HTTPException(400, "Liez votre compte Steam avant de rejoindre un match fun 5v5")
    doc = await _get_fun_match_or_404(match_id)
    if doc.get("status") not in {"open", "ready"}:
        raise HTTPException(400, "Ce match fun n'accepte plus de joueurs")
    if any(str(player.get("user_id")) == str(user["id"]) for player in (doc.get("players") or [])):
        return summarize_fun_match(doc)
    if len(doc.get("players") or []) >= FUN_MATCH_PLAYER_CAP:
        raise HTTPException(400, "Le lobby 5v5 est deja complet")
    await _ensure_user_not_in_other_fun_match(user["id"], exclude_match_id=match_id)
    players = [*list(doc.get("players") or []), _build_fun_match_player_entry(user)]
    updates = {
        "players": players,
        "status": "ready" if len(players) >= FUN_MATCH_PLAYER_CAP else "open",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.fun_matches.update_one({"id": match_id}, {"$set": updates})
    await journal("fun_match_joined", user["id"], {"match_id": match_id})
    updated = await db.fun_matches.find_one({"id": match_id}, {"_id": 0})
    return summarize_fun_match(updated)


@api_router.post("/fun-matches/{match_id}/leave", dependencies=[Depends(get_current_user)])
async def leave_fun_match(match_id: str, user=Depends(get_current_user)):
    doc = await _get_fun_match_or_404(match_id)
    if doc.get("status") not in {"open", "ready"}:
        raise HTTPException(400, "Le lobby est deja verrouille")
    players = [player for player in (doc.get("players") or []) if str(player.get("user_id")) != str(user["id"])]
    if len(players) == len(doc.get("players") or []):
        raise HTTPException(400, "Vous n'etes pas inscrit dans ce lobby")
    now_iso = datetime.now(timezone.utc).isoformat()
    updates: dict[str, Any] = {"players": players, "updated_at": now_iso}
    if not players:
        updates.update({"status": "closed", "closed_at": now_iso})
    else:
        updates["status"] = "ready" if len(players) >= FUN_MATCH_PLAYER_CAP else "open"
        if str(doc.get("creator_id")) == str(user["id"]):
            updates["creator_id"] = players[0]["user_id"]
            updates["creator_pseudo"] = players[0]["pseudo"]
    await db.fun_matches.update_one({"id": match_id}, {"$set": updates})
    await journal("fun_match_left", user["id"], {"match_id": match_id})
    updated = await db.fun_matches.find_one({"id": match_id}, {"_id": 0})
    return summarize_fun_match(updated)


@api_router.post("/fun-matches/{match_id}/rebalance", dependencies=[Depends(get_current_user)])
async def rebalance_fun_match(match_id: str, user=Depends(get_current_user)):
    doc = await _get_fun_match_or_404(match_id)
    if user["id"] != doc.get("creator_id") and not is_admin_email(user.get("email")):
        raise HTTPException(403, "Seul le createur ou un admin peut reequilibrer ce match")
    if len(doc.get("players") or []) < FUN_MATCH_PLAYER_CAP:
        raise HTTPException(400, "Il faut 10 joueurs pour generer les equipes 5v5")
    await db.fun_matches.update_one(
        {"id": match_id},
        {"$set": {"status": "ready", "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    await journal("fun_match_rebalanced", user["id"], {"match_id": match_id})
    updated = await db.fun_matches.find_one({"id": match_id}, {"_id": 0})
    return summarize_fun_match(updated)


@api_router.post("/fun-matches/{match_id}/close", dependencies=[Depends(get_current_user)])
async def close_fun_match(match_id: str, user=Depends(get_current_user)):
    doc = await _get_fun_match_or_404(match_id)
    if user["id"] != doc.get("creator_id") and not is_admin_email(user.get("email")):
        raise HTTPException(403, "Seul le createur ou un admin peut fermer ce match")
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.fun_matches.update_one({"id": match_id}, {"$set": {"status": "closed", "closed_at": now_iso, "updated_at": now_iso}})
    await journal("fun_match_closed", user["id"], {"match_id": match_id})
    updated = await db.fun_matches.find_one({"id": match_id}, {"_id": 0})
    return summarize_fun_match(updated)

@api_router.get("/players")
async def list_players(available_only: bool = False):
    q = {"available": True} if available_only else {}
    docs = await db.players.find(q, {"_id": 0}).sort("elo", -1).to_list(200)
    return [{**doc, **_public_stats_payload(doc)} for doc in docs]

@api_router.get("/tournaments")
async def list_tournaments(status: Optional[str] = None):
    q = {"status": status} if status else {}
    docs = await db.tournaments.find(q, {"_id": 0}).sort("starts_at", 1).to_list(200)
    items = []
    for doc in docs:
        summary = await _build_tournament_registration_summary(doc)
        items.append(_tournament_response_payload(doc, summary))
    return items

@api_router.get("/tournaments/{tid}")
async def get_tournament(tid: str):
    t = await db.tournaments.find_one({"id": tid}, {"_id": 0})
    if not t:
        raise HTTPException(404, "Tournament not found")
    snapshot = await _build_tournament_registration_snapshot(t)
    return _tournament_response_payload(t, snapshot, include_lists=True)

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
    summary = await _build_tournament_registration_summary(existing)
    if req.capacity < summary.get("registered_effective", 0):
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
    target_user_id: Optional[str] = Field(default=None, max_length=128)
    target_steam_id: Optional[str] = Field(default=None, max_length=64)


class BridgeMatchReportReq(BaseModel):
    reporter_pseudo: str = Field(min_length=1, max_length=128)
    reporter_steam_id: str = Field(min_length=3, max_length=64)
    target_steam_id: str = Field(min_length=3, max_length=64)
    target_pseudo: Optional[str] = Field(default=None, max_length=128)
    reason: str = Field(min_length=3, max_length=500)
    kind: str = Field(default="behavior", pattern="^(behavior|absence|cheat|other)$")


class MatchReportStatusReq(BaseModel):
    status: str = Field(pattern="^(open|acknowledged|resolved|rejected)$")
    resolution_note: Optional[str] = Field(default=None, max_length=500)


REPORT_CARD_KINDS = {"behavior", "absence", "cheat", "other"}
REPORT_CARD_THRESHOLD = 3

@api_router.get("/twitch/live")
async def twitch_live():
    channel = env_text("TWITCH_CHANNEL", "esl_csgo")
    configured = bool(env_text("TWITCH_CLIENT_ID") and env_text("TWITCH_CLIENT_SECRET"))
    try:
        return await _fetch_twitch_live_snapshot()
    except Exception as exc:
        logger.warning("Twitch live lookup failed: %s", exc)
        return _twitch_fallback_payload(channel, configured, "API Twitch temporairement indisponible.", "api_error")

# Steam OpenID (REAL — validates signature against Steam servers)
STEAM_OPENID_URL = "https://steamcommunity.com/openid/login"

def _backend_base(request: Request) -> str:
    # External URL for OpenID realm/return_to
    return os.environ.get("BACKEND_PUBLIC_URL") or str(request.base_url).rstrip("/")

def _frontend_base() -> str:
    return env_text("FRONTEND_URL", DEFAULT_FRONTEND_URL).rstrip("/")

def _steam_openid_redirect_url(backend: str, link_token: Optional[str] = None) -> str:
    callback_url = f"{backend}/api/auth/steam/callback"
    if link_token:
        callback_url = f"{callback_url}?{urlencode({'link_token': link_token})}"
    params = {
        "openid.ns": "http://specs.openid.net/auth/2.0",
        "openid.mode": "checkid_setup",
        "openid.return_to": callback_url,
        "openid.realm": backend,
        "openid.identity": "http://specs.openid.net/auth/2.0/identifier_select",
        "openid.claimed_id": "http://specs.openid.net/auth/2.0/identifier_select",
    }
    return f"{STEAM_OPENID_URL}?{urlencode(params)}"


@api_router.get("/auth/steam/login")
async def steam_login_real(request: Request):
    backend = _backend_base(request)
    return RedirectResponse(url=_steam_openid_redirect_url(backend), status_code=302)


@api_router.post("/auth/steam/link-session")
async def create_steam_link_session(request: Request, user=Depends(get_current_user)):
    backend = _backend_base(request)
    link_token = make_steam_link_token(user["id"])
    return {"url": _steam_openid_redirect_url(backend, link_token)}


@api_router.get("/auth/steam/merge-preview")
async def get_steam_merge_preview(token: str, user=Depends(get_current_user)):
    payload = await _load_steam_merge_token(token, user["id"])
    other_user = await db.users.find_one({"id": payload.get("other_user_id")}, {"_id": 0})
    current_user = await db.users.find_one({"id": user["id"]}, {"_id": 0})
    if not current_user or not other_user:
        raise HTTPException(404, "steam_merge_missing")
    return {
        "steam_id": payload.get("steam_id"),
        "current_account": _steam_merge_preview_summary(current_user),
        "other_account": _steam_merge_preview_summary(other_user),
        "choices": {
            "keep_current": "Garder ma progression actuelle",
            "keep_other_progression": "Ecraser ma progression actuelle par celle de l'autre compte",
        },
    }


@api_router.post("/auth/steam/merge-confirm", response_model=UserPublic)
async def confirm_steam_merge(req: SteamMergeConfirmReq, user=Depends(get_current_user)):
    payload = await _load_steam_merge_token(req.token, user["id"])
    current_user = await db.users.find_one({"id": user["id"]}, {"_id": 0})
    other_user = await db.users.find_one({"id": payload.get("other_user_id")}, {"_id": 0})
    if not current_user or not other_user:
        raise HTTPException(404, "steam_merge_missing")

    strategy = req.strategy
    reason = f"steam_confirmed_{strategy}"
    merged = await _merge_user_accounts(current_user, other_user, reason, strategy)

    duplicates = await db.users.find(
        {"steam_id": payload.get("steam_id"), "id": {"$ne": merged["id"]}},
        {"_id": 0},
    ).to_list(20)
    primary = merged
    for duplicate in duplicates:
        primary = await _merge_user_accounts(primary, duplicate, "steam_confirmed_cleanup", "keep_current")

    await db.users.update_one(
        {"id": primary["id"]},
        {"$set": {"steam_id": payload.get("steam_id"), "steam_verified": True, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    refreshed = await db.users.find_one({"id": primary["id"]}, {"_id": 0})
    refreshed = await _bootstrap_steam_profile(refreshed or primary)
    return user_to_public(refreshed)

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
    try:
        user = await _resolve_steam_user(steam_id, request, qp.get("link_token"))
    except SteamMergeRequired as exc:
        return RedirectResponse(url=f"{_frontend_base()}/profile?steam_merge_token={exc.merge_token}", status_code=302)
    except HTTPException as exc:
        error_target = "profile" if qp.get("link_token") else "login"
        return RedirectResponse(url=f"{_frontend_base()}/{error_target}?steam_error={exc.detail}", status_code=302)
    user = await _bootstrap_steam_profile(user)
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

# Live waiting room snapshot (real registrations + countdown)
@api_router.get("/tournaments/{tid}/waiting-room")
async def waiting_room_live_snapshot(tid: str):
    tournament = await db.tournaments.find_one({"id": tid}, {"_id": 0})
    if not tournament:
        raise HTTPException(404, "Tournoi introuvable")
    snapshot = await _build_tournament_registration_snapshot(tournament)
    countdown = await rs.get_countdown(tid)
    starts_in_seconds = (
        max(0, int(round(float(countdown["deadline"]) - time.time())))
        if countdown else _seconds_until_iso(tournament.get("starts_at"))
    )
    return {
        "tournament_id": tid,
        "tournament_name": tournament.get("name"),
        "starts_in_seconds": starts_in_seconds,
        "phase": _phase_for(starts_in_seconds),
        "teams_confirmed": snapshot["registered_effective"],
        "teams_total": int(tournament.get("capacity", 0) or 0),
        "teams_missing": max(int(tournament.get("capacity", 0) or 0) - snapshot["registered_effective"], 0),
        "manual_teams_count": snapshot["manual_teams_count"],
        "auto_generated_teams_count": snapshot["auto_generated_teams_count"],
        "solo_queue_count": snapshot["solo_waiting_count"],
        "presence_count": len(hub.presence.get(tid, {})),
        "teams_in": snapshot["teams_in"],
        "solo_queue": snapshot["solo_queue"],
        "events": _build_waiting_room_events(snapshot, starts_in_seconds),
    }

# Legacy waiting room snapshot (mock realtime fallback)
@api_router.get("/tournaments/{tid}/waiting-room-legacy")
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
    return await build_live_matches_snapshot(db)


async def _match_config_participants(match_id: str) -> list[dict]:
    match_id = str(match_id)
    docs: list[dict] = []

    stored_match = await db.matchzy_match_configs.find_one({"match_id": match_id}, {"_id": 0, "config": 1})
    if stored_match and isinstance(stored_match.get("config"), dict):
        docs.append(stored_match["config"])

    stored_duel = await db.duel_match_configs.find_one({"duel_id": match_id}, {"_id": 0, "config": 1})
    if stored_duel and isinstance(stored_duel.get("config"), dict):
        docs.append(stored_duel["config"])

    participants: list[dict] = []
    seen: set[str] = set()
    for config in docs:
        for team_key, fallback_name in (("team1", "Equipe 1"), ("team2", "Equipe 2")):
            team_doc = config.get(team_key) or {}
            team_name = str(team_doc.get("name") or fallback_name).strip()
            players_doc = team_doc.get("players") or {}
            if not isinstance(players_doc, dict):
                continue
            for raw_steam_id, raw_pseudo in players_doc.items():
                steam_id = str(raw_steam_id or "").strip()
                pseudo = str(raw_pseudo or steam_id or "Joueur").strip()
                unique_key = steam_id or f"{team_key}:{pseudo.lower()}"
                if unique_key in seen:
                    continue
                seen.add(unique_key)

                user_doc = None
                if steam_id:
                    user_doc = await db.users.find_one(
                        {"steam_id": steam_id},
                        {"_id": 0, "id": 1, "pseudo": 1, "steam_id": 1, "custom_avatar_url": 1, "steam_avatar_url": 1},
                    )

                participants.append({
                    "user_id": (user_doc or {}).get("id"),
                    "pseudo": pseudo,
                    "steam_id": steam_id or None,
                    "team_key": team_key,
                    "team_name": team_name,
                    "avatar_url": (user_doc or {}).get("custom_avatar_url") or (user_doc or {}).get("steam_avatar_url"),
                    "linked_account": bool(user_doc),
                })
    return participants


async def _match_exists(match_id: str) -> bool:
    match_id = str(match_id)
    if await db.matchzy_events.find_one({"matchid": match_id}, {"_id": 1}):
        return True
    if await db.matchzy_match_configs.find_one({"match_id": match_id}, {"_id": 1}):
        return True
    if await db.duel_match_configs.find_one({"duel_id": match_id}, {"_id": 1}):
        return True
    if await db.cs2_servers.find_one(
        {"$or": [{"current_match_id": match_id}, {"last_match_id": match_id}]},
        {"_id": 1},
    ):
        return True
    all_events = await db.matchzy_events.find({}, {"_id": 0, "matchid": 1}).limit(2000).to_list(2000)
    if any(str(doc.get("matchid")) == match_id for doc in all_events):
        return True
    return False


async def _match_server_doc(match_id: str) -> Optional[dict]:
    return await db.cs2_servers.find_one(
        {"$or": [{"current_match_id": str(match_id)}, {"last_match_id": str(match_id)}]},
        {"_id": 0},
    )


def _user_can_access_match_server(user: dict, participants: list[dict]) -> bool:
    if is_admin_email(user.get("email")):
        return True
    user_id = str(user.get("id") or "").strip()
    steam_id = str(user.get("steam_id") or "").strip()
    for participant in participants:
        if user_id and participant.get("user_id") == user_id:
            return True
        if steam_id and participant.get("steam_id") == steam_id:
            return True
    return False


def _match_report_target_required(kind: str) -> bool:
    return kind in REPORT_CARD_KINDS


async def _resolve_match_report_target(
    match_id: str,
    target_user_id: Optional[str],
    target_steam_id: Optional[str],
) -> Optional[dict]:
    user_id = str(target_user_id or "").strip() or None
    steam_id = str(target_steam_id or "").strip() or None
    if not user_id and not steam_id:
        return None

    participants = await _match_config_participants(match_id)
    target = None
    if user_id:
        target = next((item for item in participants if item.get("user_id") == user_id), None)
    if not target and steam_id:
        target = next((item for item in participants if item.get("steam_id") == steam_id), None)
    if not target:
        raise HTTPException(404, "Joueur cible introuvable pour ce match")
    return target


async def _insert_card_record(
    *,
    target_user_id: str,
    target_pseudo: str,
    issuer_user_id: Optional[str],
    issuer_pseudo: str,
    severity: str,
    reason: str,
    match_id: Optional[str] = None,
    auto: bool = False,
    auto_source: Optional[str] = None,
    source_report_count: Optional[int] = None,
) -> tuple[dict, Optional[dict]]:
    now_iso = datetime.now(timezone.utc).isoformat()
    card = {
        "id": str(uuid.uuid4()),
        "target_user_id": target_user_id,
        "target_pseudo": target_pseudo,
        "issuer_user_id": issuer_user_id or "system",
        "issuer_pseudo": issuer_pseudo,
        "severity": severity,
        "reason": reason,
        "match_id": match_id,
        "status": "active",
        "created_at": now_iso,
    }
    if auto:
        card["auto"] = True
    if auto_source:
        card["auto_source"] = auto_source
    if source_report_count is not None:
        card["source_report_count"] = source_report_count

    await db.cards.insert_one(card)

    auto_red = None
    yellows = await db.cards.count_documents({"target_user_id": target_user_id, "severity": "yellow", "status": "active"})
    if severity == "yellow" and yellows >= 3:
        existing_auto_red = await db.cards.find_one(
            {
                "target_user_id": target_user_id,
                "severity": "red",
                "status": "active",
                "auto_source": "yellow_card_accumulation",
            },
            {"_id": 1},
        )
        if not existing_auto_red:
            auto_red = {
                "id": str(uuid.uuid4()),
                "target_user_id": target_user_id,
                "target_pseudo": target_pseudo,
                "issuer_user_id": "system",
                "issuer_pseudo": "Systeme",
                "severity": "red",
                "reason": f"Auto-escalation : {yellows} cartons jaunes cumules",
                "match_id": None,
                "status": "active",
                "created_at": now_iso,
                "auto": True,
                "auto_source": "yellow_card_accumulation",
            }
            await db.cards.insert_one(auto_red)
    return card, auto_red


def _report_counts_for_card(report: dict) -> bool:
    return bool(report.get("target_user_id")) and str(report.get("kind") or "") in REPORT_CARD_KINDS


async def _maybe_issue_auto_yellow_from_reports(report: dict) -> dict:
    if not _report_counts_for_card(report):
        return {"yellow_card": None, "auto_red": None, "unique_reports": 0}

    existing_auto = await db.cards.find_one(
        {
            "target_user_id": report["target_user_id"],
            "match_id": report["match_id"],
            "severity": "yellow",
            "auto_source": "match_reports_threshold",
        },
        {"_id": 0},
    )
    if existing_auto:
        return {"yellow_card": None, "auto_red": None, "unique_reports": int(existing_auto.get("source_report_count") or REPORT_CARD_THRESHOLD)}

    docs = await db.match_reports.find(
        {
            "match_id": report["match_id"],
            "target_user_id": report["target_user_id"],
            "status": {"$ne": "rejected"},
            "kind": {"$in": list(REPORT_CARD_KINDS)},
        },
        {"_id": 0, "reporter_user_id": 1, "reporter_steam_id": 1, "reporter_pseudo": 1},
    ).to_list(200)

    identities: set[str] = set()
    for item in docs:
        identity = str(
            item.get("reporter_user_id")
            or item.get("reporter_steam_id")
            or item.get("reporter_pseudo")
            or ""
        ).strip().lower()
        if identity:
            identities.add(identity)

    unique_reports = len(identities)
    if unique_reports < REPORT_CARD_THRESHOLD:
        return {"yellow_card": None, "auto_red": None, "unique_reports": unique_reports}

    yellow_card, auto_red = await _insert_card_record(
        target_user_id=report["target_user_id"],
        target_pseudo=report.get("target_pseudo") or "Joueur",
        issuer_user_id=None,
        issuer_pseudo="Systeme",
        severity="yellow",
        reason=f"Auto-carton jaune : {unique_reports} signalements joueurs distincts sur le match",
        match_id=report["match_id"],
        auto=True,
        auto_source="match_reports_threshold",
        source_report_count=unique_reports,
    )
    await journal(
        "card_auto_report_threshold",
        None,
        {"target": report["target_user_id"], "match_id": report["match_id"], "reports": unique_reports},
    )
    if auto_red:
        await journal("card_auto_escalated", None, {"target": report["target_user_id"], "yellows": 3})
    return {"yellow_card": yellow_card, "auto_red": auto_red, "unique_reports": unique_reports}


async def _create_match_report(
    *,
    match_id: str,
    kind: str,
    message: str,
    round_label: Optional[str],
    reporter_user_id: Optional[str],
    reporter_pseudo: str,
    reporter_steam_id: Optional[str],
    source: str,
    target: Optional[dict] = None,
) -> tuple[dict, dict]:
    now_iso = datetime.now(timezone.utc).isoformat()
    report = {
        "id": str(uuid.uuid4()),
        "match_id": str(match_id),
        "kind": kind,
        "message": message.strip(),
        "round_label": (round_label or "").strip() or None,
        "status": "open",
        "source": source,
        "reporter_user_id": reporter_user_id,
        "reporter_pseudo": reporter_pseudo.strip(),
        "reporter_steam_id": (reporter_steam_id or "").strip() or None,
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    if target:
        report["target_user_id"] = target.get("user_id")
        report["target_pseudo"] = target.get("pseudo")
        report["target_steam_id"] = target.get("steam_id")
        report["target_team_name"] = target.get("team_name")

    await db.match_reports.insert_one(report)
    await journal(
        "match_report_created",
        reporter_user_id,
        {
            "match_id": str(match_id),
            "kind": kind,
            "source": source,
            "target_user_id": report.get("target_user_id"),
            "target_steam_id": report.get("target_steam_id"),
        },
    )
    auto_state = await _maybe_issue_auto_yellow_from_reports(report)
    return report, auto_state


async def _get_bridge_server_from_authorization(authorization: Optional[str]) -> dict:
    token = (authorization or "").replace("Bearer ", "", 1).strip()
    if not token:
        raise HTTPException(401, "Bridge non autorise")
    server = await db.cs2_servers.find_one({"bridge_token_hash": hashlib.sha256(token.encode("utf-8")).hexdigest()}, {"_id": 0})
    if not server:
        raise HTTPException(401, "Bridge non autorise")
    return server

@api_router.get("/matches/{matchid}")
async def match_detail(matchid: str):
    events = await db.matchzy_events.find({"matchid": matchid}, {"_id": 0}).sort("received_at", 1).to_list(1000)
    if not events:
        allev = await db.matchzy_events.find({}, {"_id": 0}).sort("received_at", 1).to_list(2000)
        events = [e for e in allev if str(e.get("matchid")) == str(matchid)]
    server = await _match_server_doc(str(matchid))
    stored_match = await db.matchzy_match_configs.find_one({"match_id": str(matchid)}, {"_id": 0, "config": 1})
    stored_duel = await db.duel_match_configs.find_one({"duel_id": str(matchid)}, {"_id": 0, "config": 1})
    stored_config = (stored_match or stored_duel or {}).get("config") or {}
    if not events and not stored_config and not server:
        raise HTTPException(404, "Match introuvable")
    latest: dict = {}
    for e in events:
        _merge_latest(latest, _extract_score(e.get("payload") or {}))
    if not latest and stored_config:
        shell = {
            "team1_name": (stored_config.get("team1") or {}).get("name") or "Team 1",
            "team2_name": (stored_config.get("team2") or {}).get("name") or "Team 2",
            "team1_score": 0,
            "team2_score": 0,
            "map_name": ((stored_config.get("maplist") or ["—"])[0]),
            "map_number": 0,
        }
        latest.update(shell)
    participants = await _match_config_participants(str(matchid))
    return {
        "matchid": str(matchid),
        "summary": latest,
        "ended": any(e["event"] == "series_end" for e in events),
        "timeline": events,
        "server": public_server_payload(server) if server else None,
        "participants": participants,
    }


@api_router.get("/matches/{matchid}/reports", dependencies=[Depends(get_current_user)])
async def list_match_reports(matchid: str, user=Depends(get_current_user)):
    docs = await db.match_reports.find({"match_id": str(matchid)}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return docs


@api_router.post("/matches/{matchid}/join", dependencies=[Depends(get_current_user)])
async def join_match_server(matchid: str, user=Depends(get_current_user)):
    if not await _match_exists(str(matchid)):
        raise HTTPException(404, "Match introuvable")
    server = await _match_server_doc(str(matchid))
    if not server or str(server.get("current_match_id") or "").strip() != str(matchid):
        raise HTTPException(409, "Le serveur du match n'est pas encore pret")
    participants = await _match_config_participants(str(matchid))
    if not _user_can_access_match_server(user, participants):
        raise HTTPException(403, "Acces reserve aux joueurs de ce match")
    join_url = build_server_connect_url(server, spectator=False)
    if not join_url:
        raise HTTPException(409, "Connexion Steam indisponible pour ce match")
    return {
        "ok": True,
        "join_url": join_url,
        "server_name": server.get("name"),
        "map": server.get("current_map"),
    }


@api_router.post("/matches/{matchid}/spectate", dependencies=[Depends(get_current_user)])
async def spectate_match_server(matchid: str, user=Depends(get_current_user)):
    if not await _match_exists(str(matchid)):
        raise HTTPException(404, "Match introuvable")
    server = await _match_server_doc(str(matchid))
    if not server or not server.get("gotv_port"):
        raise HTTPException(404, "Spectateur HLTV indisponible pour ce match")
    if str(server.get("current_match_id") or "").strip() != str(matchid):
        raise HTTPException(409, "Le flux spectateur n'est pas encore pret")
    spectator_url = build_server_connect_url(server, spectator=True)
    if not spectator_url:
        raise HTTPException(409, "Connexion spectateur indisponible pour ce match")
    return {
        "ok": True,
        "spectator_url": spectator_url,
        "server_name": server.get("name"),
        "map": server.get("current_map"),
    }


@api_router.post("/matches/{matchid}/reports", dependencies=[Depends(get_current_user)])
async def create_match_report(matchid: str, req: MatchReportReq, user=Depends(get_current_user)):
    if not await _match_exists(str(matchid)):
        raise HTTPException(404, "Match introuvable")

    target = await _resolve_match_report_target(str(matchid), req.target_user_id, req.target_steam_id)
    if _match_report_target_required(req.kind) and not target:
        raise HTTPException(400, "Selectionnez le joueur vise par le signalement")
    if target and (
        target.get("user_id") == user["id"]
        or (target.get("steam_id") and target.get("steam_id") == str(user.get("steam_id") or "").strip())
    ):
        raise HTTPException(400, "Vous ne pouvez pas vous signaler vous-meme")

    report, auto_state = await _create_match_report(
        match_id=str(matchid),
        kind=req.kind,
        message=req.message,
        round_label=req.round_label,
        reporter_user_id=user["id"],
        reporter_pseudo=user["pseudo"],
        reporter_steam_id=user.get("steam_id"),
        source="web_ui",
        target=target,
    )
    return {
        **report,
        "auto_card_triggered": bool(auto_state.get("yellow_card")),
        "auto_red_triggered": bool(auto_state.get("auto_red")),
        "unique_reports": auto_state.get("unique_reports", 0),
    }


@api_router.post("/matches/bridge/report")
async def create_bridge_match_report(req: BridgeMatchReportReq, authorization: Optional[str] = Header(default=None)):
    server = await _get_bridge_server_from_authorization(authorization)
    match_id = str(server.get("current_match_id") or "").strip()
    if not match_id:
        raise HTTPException(409, "Aucun match actif n'est assigne a ce serveur")

    target = await _resolve_match_report_target(match_id, None, req.target_steam_id)
    if not target:
        raise HTTPException(404, "Joueur cible introuvable sur le match en cours")

    reporter_steam_id = str(req.reporter_steam_id or "").strip()
    if target.get("steam_id") and target.get("steam_id") == reporter_steam_id:
        raise HTTPException(400, "Un joueur ne peut pas se signaler lui-meme")

    duplicate = await db.match_reports.find_one(
        {
            "match_id": match_id,
            "source": "cs2_chat",
            "kind": req.kind,
            "reporter_steam_id": reporter_steam_id,
            "target_steam_id": target.get("steam_id"),
            "status": {"$ne": "rejected"},
        },
        {"_id": 0, "id": 1},
    )
    if duplicate:
        return {"ok": True, "duplicate": True, "match_id": match_id, "report_id": duplicate["id"]}

    reporter_user = await db.users.find_one({"steam_id": reporter_steam_id}, {"_id": 0, "id": 1, "pseudo": 1, "steam_id": 1})
    report, auto_state = await _create_match_report(
        match_id=match_id,
        kind=req.kind,
        message=req.reason,
        round_label=None,
        reporter_user_id=(reporter_user or {}).get("id"),
        reporter_pseudo=(reporter_user or {}).get("pseudo") or req.reporter_pseudo,
        reporter_steam_id=reporter_steam_id,
        source="cs2_chat",
        target=target,
    )
    await db.cs2_servers.update_one({"id": server["id"]}, {"$set": {"last_bridge_seen_at": datetime.now(timezone.utc).isoformat()}})
    return {
        "ok": True,
        "duplicate": False,
        "match_id": match_id,
        "report_id": report["id"],
        "auto_card_triggered": bool(auto_state.get("yellow_card")),
        "auto_red_triggered": bool(auto_state.get("auto_red")),
        "unique_reports": auto_state.get("unique_reports", 0),
    }


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
    card, auto_red = await _insert_card_record(
        target_user_id=req.target_user_id,
        target_pseudo=target["pseudo"],
        issuer_user_id=issuer["id"],
        issuer_pseudo=issuer["pseudo"],
        severity=req.severity,
        reason=req.reason,
        match_id=req.match_id,
    )
    await journal("card_issued", issuer["id"], {"target": req.target_user_id, "severity": req.severity, "reason": req.reason})
    if auto_red:
        await journal("card_auto_escalated", None, {"target": req.target_user_id, "yellows": 3})
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
DUEL_MAPS = ["Mirage", "Inferno", "Anubis", "Nuke", "Vertigo", "Ancient", "Dust2"]
DUEL_MAP_CODE_BY_LABEL = {
    "Mirage": "de_mirage",
    "Inferno": "de_inferno",
    "Anubis": "de_anubis",
    "Nuke": "de_nuke",
    "Vertigo": "de_vertigo",
    "Ancient": "de_ancient",
    "Dust2": "de_dust2",
}
DUEL_ACTIVE_STATUSES = {"veto", "launch_pending", "ready", "live", "in_progress"}


def _normalize_duel_map(raw_map: str) -> str:
    value = str(raw_map or "").strip().lower()
    aliases = {
        "mirage": "Mirage",
        "de_mirage": "Mirage",
        "inferno": "Inferno",
        "de_inferno": "Inferno",
        "anubis": "Anubis",
        "de_anubis": "Anubis",
        "nuke": "Nuke",
        "de_nuke": "Nuke",
        "vertigo": "Vertigo",
        "de_vertigo": "Vertigo",
        "ancient": "Ancient",
        "de_ancient": "Ancient",
        "dust2": "Dust2",
        "de_dust2": "Dust2",
    }
    label = aliases.get(value)
    if not label:
        raise HTTPException(400, "Map duel invalide")
    return label


def _duel_matchzy_map(raw_map: str) -> str:
    label = _normalize_duel_map(raw_map)
    return DUEL_MAP_CODE_BY_LABEL[label]


def _has_steam_ready(doc: Optional[dict]) -> bool:
    steam_id = str((doc or {}).get("steam_id") or "").strip()
    return bool(steam_id and steam_id.isdigit())


def _duel_participant_ids(duel: dict) -> set[str]:
    ids = {str(duel.get("creator_id") or "")}
    if duel.get("opponent_id"):
        ids.add(str(duel.get("opponent_id")))
    return {item for item in ids if item}


def _duel_turn_pseudo(duel: dict) -> Optional[str]:
    if duel.get("veto_turn_user_id") == duel.get("creator_id"):
        return duel.get("creator_pseudo")
    if duel.get("veto_turn_user_id") == duel.get("opponent_id"):
        return duel.get("opponent_pseudo")
    return None


def _duel_public_payload(duel: dict, viewer_id: Optional[str] = None) -> dict:
    participant_ids = _duel_participant_ids(duel)
    is_participant = bool(viewer_id and viewer_id in participant_ids)
    server_meta = None
    if duel.get("server_id"):
        server_meta = {
            "id": duel.get("server_id"),
            "name": duel.get("server_name"),
            "host": duel.get("server_host"),
            "game_port": duel.get("server_game_port"),
            "gotv_port": duel.get("server_gotv_port"),
        }
    return {
        "id": duel["id"],
        "creator_id": duel["creator_id"],
        "creator_pseudo": duel["creator_pseudo"],
        "opponent_id": duel.get("opponent_id"),
        "opponent_pseudo": duel.get("opponent_pseudo"),
        "stake": int(duel.get("stake", 0)),
        "pot": int(duel.get("stake", 0)) * 2,
        "status": duel.get("status", "open"),
        "preferred_map": duel.get("preferred_map") or duel.get("map"),
        "selected_map": duel.get("selected_map") or duel.get("map"),
        "remaining_maps": duel.get("map_pool") or [],
        "veto_history": duel.get("veto_history") or [],
        "veto_turn_user_id": duel.get("veto_turn_user_id"),
        "veto_turn_pseudo": _duel_turn_pseudo(duel),
        "created_at": duel.get("created_at"),
        "accepted_at": duel.get("accepted_at"),
        "started_at": duel.get("started_at"),
        "closed_at": duel.get("closed_at"),
        "winner_id": duel.get("winner_id"),
        "winner_pseudo": duel.get("winner_pseudo"),
        "launch_status": duel.get("launch_status"),
        "launch_error": duel.get("launch_error"),
        "server": server_meta,
        "is_participant": is_participant,
        "is_my_turn": bool(is_participant and viewer_id == duel.get("veto_turn_user_id") and duel.get("status") == "veto"),
        "can_join": bool(is_participant and duel.get("server_id") and duel.get("status") in DUEL_ACTIVE_STATUSES),
        "join_cta": "Rejoindre le serveur" if duel.get("server_id") and duel.get("status") in DUEL_ACTIVE_STATUSES else None,
    }


async def _reserve_duel_server(duel_id: str) -> Optional[dict]:
    now_iso = datetime.now(timezone.utc).isoformat()
    return await db.cs2_servers.find_one_and_update(
        {
            "matchzy_enabled": True,
            "current_match_id": None,
            "status": {"$nin": ["live", "launch_pending", "allocating"]},
        },
        {"$set": {
            "current_match_id": duel_id,
            "current_duel_id": duel_id,
            "last_match_id": duel_id,
            "status": "allocating",
            "last_checked_at": now_iso,
        }},
        sort=[("last_checked_at", 1), ("created_at", 1)],
        return_document=ReturnDocument.AFTER,
    )


async def _release_duel_server(server_id: str, duel_id: str) -> None:
    await db.cs2_servers.update_one(
        {"id": server_id, "current_match_id": duel_id},
        {"$set": {
            "status": "online",
            "current_match_id": None,
            "current_duel_id": None,
            "current_tournament_id": None,
            "current_bracket_match_id": None,
            "last_checked_at": datetime.now(timezone.utc).isoformat(),
        }},
    )


async def _store_duel_matchzy_config(duel_id: str, server_id: str, config: dict[str, Any]) -> None:
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.duel_match_configs.replace_one(
        {"duel_id": duel_id},
        {
            "id": duel_id,
            "duel_id": duel_id,
            "server_id": server_id,
            "config": config,
            "created_at": now_iso,
            "updated_at": now_iso,
        },
        upsert=True,
    )


async def _launch_duel_match(duel: dict) -> dict:
    creator = await db.users.find_one({"id": duel["creator_id"]}, {"_id": 0, "id": 1, "pseudo": 1, "steam_id": 1})
    opponent = await db.users.find_one({"id": duel["opponent_id"]}, {"_id": 0, "id": 1, "pseudo": 1, "steam_id": 1})
    if not _has_steam_ready(creator) or not _has_steam_ready(opponent):
        raise HTTPException(409, "Les deux joueurs doivent lier leur Steam avant le lancement du duel")
    selected_map = duel.get("selected_map")
    if not selected_map:
        raise HTTPException(409, "La map finale du duel n'est pas encore definie")
    public_base = backend_public_base()
    if not public_base:
        raise HTTPException(500, "BACKEND_PUBLIC_URL manquant pour lancer un duel MatchZy")

    server = await _reserve_duel_server(duel["id"])
    if not server:
        raise HTTPException(409, "Aucun serveur CS2 libre n'est disponible pour ce duel")

    try:
        config = build_duel_matchzy_config(
            duel_id=duel["id"],
            creator=creator,
            opponent=opponent,
            map_name=_duel_matchzy_map(selected_map),
            cvars={"hostname": f"ReadyUp Arena Duel | {creator['pseudo']} vs {opponent['pseudo']}"},
        )
        await _store_duel_matchzy_config(duel["id"], server["id"], config)
        config_url = f"{public_base}/api/duels/{duel['id']}/matchzy-config"
        header_name, header_value = matchzy_config_header()
        remote_log_outputs = await configure_matchzy_remote_log(
            db,
            server,
            created_by=duel["creator_id"],
            metadata={"duel_id": duel["id"], "config_url": config_url},
        )
        command = matchzy_load_url_command(config_url, header_name, header_value)
        result = await run_server_command(
            db,
            server,
            command,
            kind="launch_duel_match",
            metadata={"duel_id": duel["id"], "config_url": config_url},
            created_by=duel["creator_id"],
        )
        launch_status = "launch_pending" if result["queued"] else "ready"
        now_iso = datetime.now(timezone.utc).isoformat()
        await db.cs2_servers.update_one(
            {"id": server["id"]},
            {"$set": {
                "current_match_id": duel["id"],
                "current_duel_id": duel["id"],
                "last_match_id": duel["id"],
                "status": "launch_pending" if result["queued"] else "live",
                "last_checked_at": now_iso,
            }},
        )
        payload = {
            "status": launch_status,
            "launch_status": launch_status,
            "launch_error": None,
            "started_at": now_iso,
            "server_id": server["id"],
            "server_name": server.get("name"),
            "server_host": server.get("public_host") or server.get("host"),
            "server_game_port": server.get("game_port") or server.get("port"),
            "server_gotv_port": server.get("gotv_port"),
            "matchzy_config_url": config_url,
            "launch_command_id": result.get("command_id"),
            "launch_mode": result.get("mode"),
            "remote_log_configured": bool(remote_log_outputs),
        }
        await db.duels.update_one({"id": duel["id"]}, {"$set": payload})
        await journal("duel_match_launched", duel["creator_id"], {"duel_id": duel["id"], "server_id": server["id"], "status": launch_status})
        return payload
    except HTTPException:
        await _release_duel_server(server["id"], duel["id"])
        raise
    except Exception as exc:
        await _release_duel_server(server["id"], duel["id"])
        raise HTTPException(502, f"Echec du lancement MatchZy du duel : {exc}")


class DuelReq(BaseModel):
    map_: str = Field(alias="map", min_length=2, max_length=24)
    stake: int = Field(ge=10, le=5000)
    class Config: populate_by_name = True


class DuelVetoReq(BaseModel):
    map: str = Field(min_length=2, max_length=24)

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
    if not _has_steam_ready(user):
        raise HTTPException(400, "Liez votre compte Steam avant de creer un duel CS2")
    bal = await get_balance(user["id"])
    if bal < req.stake: raise HTTPException(400, f"Solde insuffisant ({bal} jetons)")
    preferred_map = _normalize_duel_map(req.map_)
    await db.users.update_one({"id": user["id"]}, {"$inc": {"tokens": -req.stake}})
    duel = {
        "id": str(uuid.uuid4()), "creator_id": user["id"], "creator_pseudo": user["pseudo"],
        "opponent_id": None, "opponent_pseudo": None,
        "map": preferred_map, "preferred_map": preferred_map,
        "selected_map": None, "map_pool": None, "veto_history": [], "veto_turn_user_id": None,
        "server_id": None, "server_name": None, "server_host": None, "server_game_port": None, "server_gotv_port": None,
        "launch_status": "open", "launch_error": None,
        "stake": req.stake, "status": "open",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.duels.insert_one(duel)
    await journal("duel_created", user["id"], {"duel_id": duel["id"], "stake": req.stake, "map": preferred_map})
    return _duel_public_payload(duel, user["id"])

@duels_router.get("")
async def list_open_duels(status_f: str = "open"):
    safe_status = "open" if status_f != "open" else status_f
    docs = await db.duels.find({"status": safe_status}, {"_id": 0}).sort("created_at", -1).to_list(50)
    return [_duel_public_payload(doc) for doc in docs]


@duels_router.get("/mine", dependencies=[Depends(get_current_user)])
async def list_my_duels(user=Depends(get_current_user)):
    docs = await db.duels.find(
        {"$or": [{"creator_id": user["id"]}, {"opponent_id": user["id"]}]},
        {"_id": 0},
    ).sort("created_at", -1).to_list(100)
    return [_duel_public_payload(doc, user["id"]) for doc in docs]


@duels_router.get("/{duel_id}/matchzy-config")
async def get_duel_matchzy_config(
    duel_id: str,
    authorization: Optional[str] = Header(default=None),
    x_matchzy_token: Optional[str] = Header(default=None),
):
    header_name, header_value = matchzy_config_header()
    if header_value:
        expected_token = header_value.replace("Bearer ", "", 1)
        provided_token = (authorization or "").replace("Bearer ", "", 1) or (x_matchzy_token or "")
        if not secrets.compare_digest(provided_token, expected_token):
            raise HTTPException(401, "Config MatchZy non autorisee")
    doc = await db.duel_match_configs.find_one({"duel_id": duel_id}, {"_id": 0, "config": 1})
    if not doc:
        raise HTTPException(404, "Configuration duel introuvable")
    return doc["config"]

@duels_router.post("/{duel_id}/accept", dependencies=[Depends(get_current_user)])
async def accept_duel(duel_id: str, user=Depends(get_current_user)):
    duel = await db.duels.find_one({"id": duel_id}, {"_id": 0})
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


@duels_router.post("/{duel_id}/accept-cs2", dependencies=[Depends(get_current_user)])
async def accept_duel_cs2(duel_id: str, user=Depends(get_current_user)):
    duel = await db.duels.find_one({"id": duel_id}, {"_id": 0})
    if not duel:
        raise HTTPException(404, "Duel introuvable")
    if duel["status"] != "open":
        raise HTTPException(400, "Duel deja accepte ou clos")
    if duel["creator_id"] == user["id"]:
        raise HTTPException(400, "Impossible d'accepter son propre duel")
    if not _has_steam_ready(user):
        raise HTTPException(400, "Liez votre compte Steam avant d'accepter un duel CS2")
    creator = await db.users.find_one({"id": duel["creator_id"]}, {"_id": 0, "steam_id": 1})
    if not _has_steam_ready(creator):
        raise HTTPException(409, "Le createur du duel doit lier son Steam avant le lancement")
    bal = await get_balance(user["id"])
    if bal < duel["stake"]:
        raise HTTPException(400, f"Solde insuffisant ({bal} jetons)")
    await db.users.update_one({"id": user["id"]}, {"$inc": {"tokens": -duel["stake"]}})
    now_iso = datetime.now(timezone.utc).isoformat()
    result = await db.duels.update_one(
        {"id": duel_id, "status": "open"},
        {"$set": {
            "opponent_id": user["id"],
            "opponent_pseudo": user["pseudo"],
            "status": "veto",
            "accepted_at": now_iso,
            "map_pool": DUEL_MAPS.copy(),
            "veto_history": [],
            "veto_turn_user_id": duel["creator_id"],
            "launch_status": "veto_pending",
            "launch_error": None,
        }},
    )
    if result.modified_count == 0:
        await db.users.update_one({"id": user["id"]}, {"$inc": {"tokens": duel["stake"]}})
        raise HTTPException(409, "Le duel vient d'etre modifie, rechargez la page")
    await journal("duel_accepted_cs2", user["id"], {"duel_id": duel_id})
    updated = await db.duels.find_one({"id": duel_id}, {"_id": 0})
    return _duel_public_payload(updated or {**duel, "opponent_id": user["id"], "opponent_pseudo": user["pseudo"], "status": "veto"}, user["id"])


@duels_router.post("/{duel_id}/ban", dependencies=[Depends(get_current_user)])
async def ban_duel_map(duel_id: str, req: DuelVetoReq, user=Depends(get_current_user)):
    duel = await db.duels.find_one({"id": duel_id}, {"_id": 0})
    if not duel:
        raise HTTPException(404, "Duel introuvable")
    if duel.get("status") != "veto":
        raise HTTPException(400, "Le duel n'est pas en phase de veto")
    if user["id"] not in _duel_participant_ids(duel):
        raise HTTPException(403, "Acces refuse")
    if duel.get("veto_turn_user_id") != user["id"]:
        raise HTTPException(409, "Ce n'est pas votre tour pour bannir une map")
    remaining_maps = [_normalize_duel_map(item) for item in (duel.get("map_pool") or DUEL_MAPS.copy())]
    ban_map = _normalize_duel_map(req.map)
    if ban_map not in remaining_maps:
        raise HTTPException(400, "Cette map n'est pas disponible pour le veto")
    if len(remaining_maps) <= 1:
        raise HTTPException(409, "Le veto est deja termine")
    remaining_maps = [item for item in remaining_maps if item != ban_map]
    veto_history = list(duel.get("veto_history") or [])
    veto_history.append({
        "by_user_id": user["id"],
        "by_pseudo": user["pseudo"],
        "action": "ban",
        "map": ban_map,
        "at": datetime.now(timezone.utc).isoformat(),
    })
    next_turn = duel["opponent_id"] if user["id"] == duel["creator_id"] else duel["creator_id"]
    updates: dict[str, Any] = {
        "map_pool": remaining_maps,
        "veto_history": veto_history,
        "veto_turn_user_id": next_turn,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if len(remaining_maps) == 1:
        updates.update({
            "selected_map": remaining_maps[0],
            "veto_turn_user_id": None,
            "status": "launch_pending",
            "launch_status": "allocating_server",
            "veto_completed_at": datetime.now(timezone.utc).isoformat(),
        })
    updated = await db.duels.find_one_and_update(
        {"id": duel_id, "status": "veto", "veto_turn_user_id": user["id"]},
        {"$set": updates},
        return_document=ReturnDocument.AFTER,
        projection={"_id": 0},
    )
    if not updated:
        raise HTTPException(409, "Le duel a change pendant le veto, rechargez la page")
    if len(remaining_maps) == 1:
        try:
            launch_updates = await _launch_duel_match(updated)
            updated.update(launch_updates)
        except HTTPException as exc:
            await db.duels.update_one(
                {"id": duel_id},
                {"$set": {"status": "launch_failed", "launch_status": "failed", "launch_error": str(exc.detail)}},
            )
            raise
    await journal("duel_map_banned", user["id"], {"duel_id": duel_id, "map": ban_map})
    return _duel_public_payload(updated, user["id"])


@duels_router.post("/{duel_id}/join", dependencies=[Depends(get_current_user)])
async def join_duel_server(duel_id: str, user=Depends(get_current_user)):
    duel = await db.duels.find_one({"id": duel_id}, {"_id": 0})
    if not duel:
        raise HTTPException(404, "Duel introuvable")
    if user["id"] not in _duel_participant_ids(duel):
        raise HTTPException(403, "Acces refuse")
    if duel.get("status") not in DUEL_ACTIVE_STATUSES or not duel.get("server_id"):
        raise HTTPException(409, "Le serveur du duel n'est pas encore pret")
    server = await db.cs2_servers.find_one({"id": duel["server_id"]})
    if not server:
        raise HTTPException(404, "Serveur duel introuvable")
    join_url = build_server_connect_url(server)
    if not join_url:
        raise HTTPException(409, "Connexion Steam indisponible pour ce serveur")
    return {"ok": True, "join_url": join_url, "server_name": server.get("name"), "map": duel.get("selected_map")}


@duels_router.post("/{duel_id}/result-manual", dependencies=[Depends(get_current_user)])
async def report_duel_result_manual(duel_id: str, req: DuelResultReq, reporter=Depends(get_current_user)):
    duel = await db.duels.find_one({"id": duel_id}, {"_id": 0})
    if not duel:
        raise HTTPException(404, "Duel introuvable")
    if duel["status"] not in DUEL_ACTIVE_STATUSES:
        raise HTTPException(400, "Duel non en cours")
    if req.winner_id not in (duel["creator_id"], duel["opponent_id"]):
        raise HTTPException(400, "Le gagnant doit etre l'un des 2 participants")
    pot = duel["stake"] * 2
    await db.users.update_one({"id": req.winner_id}, {"$inc": {"tokens": pot}})
    winner_pseudo = duel["creator_pseudo"] if req.winner_id == duel["creator_id"] else duel.get("opponent_pseudo")
    await db.duels.update_one(
        {"id": duel_id, "status": {"$in": list(DUEL_ACTIVE_STATUSES)}},
        {"$set": {
            "status": "closed",
            "winner_id": req.winner_id,
            "winner_pseudo": winner_pseudo,
            "closed_at": datetime.now(timezone.utc).isoformat(),
            "result_source": "manual_report",
        }},
    )
    if duel.get("server_id"):
        await _release_duel_server(duel["server_id"], duel_id)
    await journal("duel_closed_manual", reporter["id"], {"duel_id": duel_id, "winner": req.winner_id, "pot": pot})
    return {"ok": True, "winner_id": req.winner_id, "pot_awarded": pot}

@duels_router.post("/{duel_id}/result", dependencies=[Depends(get_current_user)])
async def report_result(duel_id: str, req: DuelResultReq, reporter=Depends(get_current_user)):
    duel = await db.duels.find_one({"id": duel_id})
    if not duel: raise HTTPException(404, "Duel introuvable")
    if duel["status"] != "in_progress": raise HTTPException(400, "Duel non en cours")
    if req.winner_id not in (duel["creator_id"], duel["opponent_id"]):
        raise HTTPException(400, "Le gagnant doit être l'un des 2 participants")
    pot = duel["stake"] * 2
    await db.users.update_one({"id": req.winner_id}, {"$inc": {"tokens": pot}})
    winner_pseudo = duel["creator_pseudo"] if req.winner_id == duel["creator_id"] else duel.get("opponent_pseudo")
    await db.duels.update_one({"id": duel_id, "status": "in_progress"},
        {"$set": {
            "status": "closed",
            "winner_id": req.winner_id,
            "winner_pseudo": winner_pseudo,
            "closed_at": datetime.now(timezone.utc).isoformat(),
            "result_source": "manual_report",
        }})
    if duel.get("server_id"):
        await _release_duel_server(duel["server_id"], duel_id)
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
    if not env_text("BACKEND_PUBLIC_URL"):
        logger.warning("BACKEND_PUBLIC_URL is missing. Steam OpenID and MatchZy config URLs will be unreliable outside local development.")
    if not env_text("MATCHZY_WEBHOOK_SECRET"):
        logger.warning("MATCHZY_WEBHOOK_SECRET is missing. MatchZy webhook authentication is not secured.")
    if not env_text("MATCHZY_CONFIG_TOKEN"):
        logger.warning("MATCHZY_CONFIG_TOKEN is missing. MatchZy config fetch URLs are not protected.")
    if env_flag("FEATURE_TWITCH", True) and not (env_text("TWITCH_CLIENT_ID") and env_text("TWITCH_CLIENT_SECRET")):
        logger.info("Twitch live status fallback active: set TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET for real Twitch API data.")
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
