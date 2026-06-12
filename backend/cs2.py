"""CS2 server orchestration (Iteration 6) — RCON adapter + MatchZy webhook.

Built as a factory so it can reuse the DB handle, auth dependency and audit
helper from server.py without circular imports.
"""
import os
import uuid
import hmac
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Request, Header
from pydantic import BaseModel, Field
from cryptography.fernet import Fernet

from rcon.source import Client as RconClient

logger = logging.getLogger(__name__)
_fernet = Fernet(os.environ["RCON_ENC_KEY"]) if os.environ.get("RCON_ENC_KEY") else None

def _enc(s: str) -> str:
    return _fernet.encrypt(s.encode()).decode() if _fernet else s

def _dec(s: str) -> str:
    if not _fernet:
        return s
    try:
        return _fernet.decrypt(s.encode()).decode()
    except Exception:
        logger.warning("RCON password stored as legacy plaintext — consider re-saving the server to encrypt it")
        return s  # tolerate legacy plaintext entries


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _rcon_exec(host: str, port: int, password: str, command: str, timeout: float = 8.0) -> str:
    """Blocking Source-RCON call. Run inside a thread via asyncio.to_thread."""
    with RconClient(host, int(port), passwd=password, timeout=timeout) as client:
        return client.run(command)


def _public_server(doc: dict) -> dict:
    """Strip the RCON password before returning a server to clients."""
    return {k: v for k, v in doc.items() if k not in ("_id", "rcon_password")}


class ServerReq(BaseModel):
    name: str = Field(min_length=2, max_length=64)
    host: str = Field(min_length=3, max_length=128)
    port: int = Field(ge=1, le=65535, default=27015)
    rcon_password: str = Field(min_length=1, max_length=128)


class RconCmd(BaseModel):
    command: str = Field(min_length=1, max_length=512)


class MatchSetupReq(BaseModel):
    matchzy_url: Optional[str] = Field(default=None, max_length=512)
    raw_command: Optional[str] = Field(default=None, max_length=512)


def build_cs2_router(db, get_current_user, get_admin_user, journal):
    router = APIRouter(prefix="/api/cs2")

    async def _get_server(sid: str) -> dict:
        srv = await db.cs2_servers.find_one({"id": sid})
        if not srv:
            raise HTTPException(404, "Serveur CS2 introuvable")
        return srv

    async def _run_rcon(srv: dict, command: str) -> str:
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(_rcon_exec, srv["host"], srv["port"], _dec(srv["rcon_password"]), command),
                timeout=12,
            )
        except asyncio.TimeoutError:
            raise HTTPException(504, "RCON timeout — serveur injoignable")
        except Exception as e:
            raise HTTPException(502, f"Erreur RCON : {e}")

    @router.post("/servers", dependencies=[Depends(get_admin_user)])
    async def create_server(req: ServerReq, user=Depends(get_admin_user)):
        srv = {
            "id": str(uuid.uuid4()), "name": req.name, "host": req.host,
            "port": req.port, "rcon_password": _enc(req.rcon_password),
            "status": "unknown", "last_checked_at": None,
            "current_match_id": None, "created_at": _now_iso(),
            "created_by": user["id"],
        }
        await db.cs2_servers.insert_one(srv)
        await journal("cs2_server_added", user["id"], {"server_id": srv["id"], "host": req.host, "port": req.port})
        return _public_server(srv)

    @router.get("/servers")
    async def list_servers():
        docs = await db.cs2_servers.find({}).sort("created_at", -1).to_list(100)
        return [_public_server(d) for d in docs]

    @router.delete("/servers/{sid}", dependencies=[Depends(get_admin_user)])
    async def delete_server(sid: str, user=Depends(get_admin_user)):
        r = await db.cs2_servers.delete_one({"id": sid})
        if r.deleted_count == 0:
            raise HTTPException(404, "Serveur CS2 introuvable")
        await journal("cs2_server_removed", user["id"], {"server_id": sid})
        return {"ok": True}

    @router.post("/servers/{sid}/ping", dependencies=[Depends(get_admin_user)])
    async def ping_server(sid: str):
        srv = await _get_server(sid)
        out = await _run_rcon(srv, "status")
        await db.cs2_servers.update_one(
            {"id": sid}, {"$set": {"status": "online", "last_checked_at": _now_iso()}})
        return {"server_id": sid, "status": "online", "output": out}

    @router.post("/servers/{sid}/rcon", dependencies=[Depends(get_admin_user)])
    async def run_command(sid: str, req: RconCmd, user=Depends(get_admin_user)):
        srv = await _get_server(sid)
        out = await _run_rcon(srv, req.command)
        await journal("cs2_rcon", user["id"], {"server_id": sid, "command": req.command})
        return {"server_id": sid, "command": req.command, "output": out}

    @router.post("/servers/{sid}/setup-match", dependencies=[Depends(get_admin_user)])
    async def setup_match(sid: str, req: MatchSetupReq, user=Depends(get_admin_user)):
        srv = await _get_server(sid)
        if req.raw_command:
            command = req.raw_command
        elif req.matchzy_url:
            command = f'matchzy_loadmatch_url "{req.matchzy_url}"'
        else:
            raise HTTPException(400, "Fournir matchzy_url ou raw_command")
        out = await _run_rcon(srv, command)
        match_id = str(uuid.uuid4())
        await db.cs2_servers.update_one(
            {"id": sid}, {"$set": {"current_match_id": match_id, "status": "live"}})
        await journal("cs2_match_setup", user["id"], {"server_id": sid, "match_id": match_id, "command": command})
        return {"server_id": sid, "match_id": match_id, "command": command, "output": out}

    # ---------- MatchZy webhook listener ----------
    @router.post("/webhooks/matchzy")
    async def matchzy_webhook(request: Request, authorization: Optional[str] = Header(default=None)):
        secret = os.environ.get("MATCHZY_WEBHOOK_SECRET")
        if secret:
            provided = (authorization or "").replace("Bearer ", "", 1)
            if not (hmac.compare_digest(authorization or "", secret) or hmac.compare_digest(provided, secret)):
                raise HTTPException(401, "Webhook non autorisé")
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        event = {
            "id": str(uuid.uuid4()),
            "event": payload.get("event", "unknown"),
            "matchid": str(payload["matchid"]) if payload.get("matchid") is not None else None,
            "payload": payload,
            "received_at": _now_iso(),
        }
        await db.matchzy_events.insert_one(event)
        # Reflect terminal series state on the bound server, if any
        if payload.get("event") in ("series_end", "map_result") and payload.get("matchid"):
            await db.cs2_servers.update_one(
                {"current_match_id": str(payload.get("matchid"))},
                {"$set": {"status": "online"}})
        return {"received": True, "id": event["id"]}

    @router.get("/events")
    async def list_events(limit: int = 50, matchid: Optional[str] = None):
        q = {}
        if matchid:
            q["matchid"] = matchid
        docs = await db.matchzy_events.find(q, {"_id": 0}).sort("received_at", -1).to_list(min(limit, 200))
        return docs

    return router
