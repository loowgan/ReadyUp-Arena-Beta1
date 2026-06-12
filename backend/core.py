"""Shared core: settings, DB handle, auth helpers and FastAPI dependencies.

All route modules import from here to avoid circular imports.
"""
import os
import uuid
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta
from typing import Optional
from urllib.parse import urlparse

import bcrypt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from motor.motor_asyncio import AsyncIOMotorClient

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

client = AsyncIOMotorClient(mongo_url)
db = client[_resolve_db_name(mongo_url)]

# ============= AUTH =============
JWT_SECRET = os.environ.get("JWT_SECRET", "readyup-arena-dev-secret-change-in-prod")
JWT_ALGO = "HS256"
JWT_EXP_HOURS = 24 * 7
bearer = HTTPBearer(auto_error=False)

ADMIN_EMAILS = {e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()}
SEED_ADMIN_EMAIL = os.environ.get("SEED_ADMIN_EMAIL", "").strip().lower()
EFFECTIVE_ADMIN_EMAILS = ADMIN_EMAILS | ({SEED_ADMIN_EMAIL} if SEED_ADMIN_EMAIL else set())


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(pw: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), h.encode())
    except Exception:
        return False


def make_token(user_id: str, pseudo: str) -> str:
    payload = {"sub": user_id, "pseudo": pseudo,
               "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXP_HOURS),
               "iat": datetime.now(timezone.utc)}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


async def journal(event_type: str, user_id: Optional[str], meta: dict = None):
    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()), "event_type": event_type, "user_id": user_id,
        "meta": meta or {}, "created_at": datetime.now(timezone.utc).isoformat()})


def is_admin_email(email: str) -> bool:
    return (email or "").lower() in EFFECTIVE_ADMIN_EMAILS


def user_to_public(u: dict) -> dict:
    return {"id": u["id"], "pseudo": u["pseudo"], "email": u["email"],
            "country": u.get("country", "FR"), "level": u.get("level", 1),
            "xp": u.get("xp", 0), "elo": u.get("elo", 1000),
            "steam_verified": u.get("steam_verified", False),
            "created_at": u["created_at"],
            "is_admin": is_admin_email(u.get("email"))}


async def get_current_user(creds: HTTPAuthorizationCredentials = Depends(bearer)):
    if not creds:
        raise HTTPException(401, "Token requis")
    try:
        payload = jwt.decode(creds.credentials, JWT_SECRET, algorithms=[JWT_ALGO])
    except JWTError:
        raise HTTPException(401, "Token invalide ou expiré")
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(401, "Utilisateur introuvable")
    return user


async def get_admin_user(user=Depends(get_current_user)):
    if not is_admin_email(user.get("email")):
        raise HTTPException(403, "Accès réservé aux administrateurs")
    return user


def _backend_base(request: Request) -> str:
    return os.environ.get("BACKEND_PUBLIC_URL") or str(request.base_url).rstrip("/")


def _frontend_base() -> str:
    return os.environ.get("FRONTEND_URL", "http://localhost:3000")


def _clean(doc: dict) -> dict:
    return {k: v for k, v in doc.items() if k != "_id"}
