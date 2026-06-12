from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import asyncio, json, time
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os, logging, uuid, random, secrets
import bcrypt, httpx
from jose import jwt, JWTError
from urllib.parse import urlencode, urlparse
from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionRequest
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
from datetime import datetime, timezone, timedelta

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

class UserPublic(BaseModel):
    id: str
    pseudo: str
    email: str
    country: str
    level: int
    xp: int
    elo: int
    steam_verified: bool
    created_at: str
    is_admin: bool = False

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

def user_to_public(u: dict) -> dict:
    return {"id": u["id"], "pseudo": u["pseudo"], "email": u["email"],
            "country": u.get("country","FR"), "level": u.get("level",1),
            "xp": u.get("xp",0), "elo": u.get("elo",1000),
            "steam_verified": u.get("steam_verified", False),
            "created_at": u["created_at"],
            "is_admin": is_admin_email(u.get("email"))}

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
        "level": 1, "xp": 0, "elo": 1000, "steam_verified": False, "steam_id": None,
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

@api_router.get("/teams")
async def list_teams():
    return await db.teams.find({}, {"_id": 0}).sort("elo", -1).to_list(200)

@api_router.get("/players")
async def list_players(available_only: bool = False):
    q = {"available": True} if available_only else {}
    return await db.players.find(q, {"_id": 0}).sort("elo", -1).to_list(200)

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
    reg = {"id": str(uuid.uuid4()), "tournament_id": tid, "user_id": user["id"],
           "entity_type": req.entity_type, "entity_id": req.entity_id,
           "entity_name": req.entity_name, "created_at": datetime.now(timezone.utc).isoformat()}
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
            "level": 1, "xp": 0, "elo": 1000, "steam_verified": True, "steam_id": steam_id,
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
    return {"matchid": str(matchid), "summary": latest,
            "ended": any(e["event"] == "series_end" for e in events), "timeline": events}

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
        "level": 1,
        "xp": 0,
        "elo": 1000,
        "steam_verified": False,
        "steam_id": None,
        "tokens": int(env_text("SEED_ADMIN_TOKENS", "1000")),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    logger.info("Seeded initial admin account from environment configuration")

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
    # Resume any countdowns persisted in Redis (survive backend reboots)
    for tid in await rs.active_countdowns():
        asyncio.create_task(countdown_task(tid))
    asyncio.create_task(_scheduler_loop())
    logger.info("ReadyUp Arena startup: seed + countdown resume + scheduler ready")

@app.on_event("shutdown")
async def shutdown_db_client(): client.close()
