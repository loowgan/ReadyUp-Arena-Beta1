"""CS2 server orchestration (Iteration 6) — RCON adapter + MatchZy webhook.

Built as a factory so it can reuse the DB handle, auth dependency and audit
helper from server.py without circular imports.
"""
import os
import uuid
import hmac
import json
import hashlib
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Any
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Depends, Request, Header
from pydantic import BaseModel, Field
from cryptography.fernet import Fernet

from rcon.source import Client as RconClient
from bracket import report_match
from fun_matches import FUN_MATCH_TEAM_SIZE, summarize_fun_match

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


def _coerce_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_matchzy_winner_team(payload: dict[str, Any]) -> Optional[str]:
    winner = payload.get("winner")
    raw_team = None
    if isinstance(winner, dict):
        raw_team = winner.get("team") or winner.get("side") or winner.get("id") or winner.get("name")
    elif winner is not None:
        raw_team = winner
    if raw_team is None:
        raw_team = payload.get("winner_team") or payload.get("winning_team")
    normalized = str(raw_team or "").strip().lower()
    return normalized if normalized in {"team1", "team2"} else None


def _extract_matchzy_series_score(payload: dict[str, Any]) -> dict[str, Optional[int]]:
    team1 = payload.get("team1") or {}
    team2 = payload.get("team2") or {}
    return {
        "team1": _coerce_int(payload.get("team1_series_score", team1.get("series_score", team1.get("score")))),
        "team2": _coerce_int(payload.get("team2_series_score", team2.get("series_score", team2.get("score")))),
    }


def _extract_matchzy_map_name(payload: dict[str, Any]) -> Optional[str]:
    raw = payload.get("map_name") or payload.get("map")
    value = str(raw or "").strip()
    return value or None


def _build_match_shell_from_config(match_id: str, config: dict[str, Any]) -> dict[str, Any]:
    team1 = config.get("team1") or {}
    team2 = config.get("team2") or {}
    maplist = config.get("maplist") or []
    return {
        "matchid": str(match_id),
        "events": 0,
        "last_event": None,
        "ended": False,
        "updated_at": None,
        "team1_name": team1.get("name") or "Team 1",
        "team2_name": team2.get("name") or "Team 2",
        "team1_score": 0,
        "team2_score": 0,
        "map_name": str(maplist[0]).strip() if maplist else "—",
        "map_number": 0,
        "source": "config",
    }


def _iter_bracket_matches_doc(bracket_doc: dict):
    for group in ("W", "L", "GF"):
        for match_doc in bracket_doc.get("matches", {}).get(group, []):
            yield match_doc


def _find_bracket_match_doc(bracket_doc: dict, match_id: str) -> Optional[dict]:
    target_id = str(match_id)
    for match_doc in _iter_bracket_matches_doc(bracket_doc):
        if str(match_doc.get("id")) == target_id:
            return match_doc
    return None


async def _find_bracket_doc_by_match_id(db, match_id: str) -> Optional[dict]:
    raw = await db.brackets.find_one(
        {"$or": [{"matches.W.id": str(match_id)}, {"matches.L.id": str(match_id)}, {"matches.GF.id": str(match_id)}]}
    )
    if raw:
        return raw
    docs = await db.brackets.find({}, {"_id": 0}).to_list(200)
    return next((doc for doc in docs if _find_bracket_match_doc(doc, str(match_id))), None)


async def _attach_match_runtime_metadata(db, match_id: str, updates: dict[str, Any]) -> bool:
    raw = await _find_bracket_doc_by_match_id(db, match_id)
    if not raw:
        return False
    bracket_doc = {k: v for k, v in raw.items() if k != "_id"}
    match_doc = _find_bracket_match_doc(bracket_doc, str(match_id))
    if not match_doc:
        return False
    for key, value in updates.items():
        if value is None:
            continue
        match_doc[key] = value
    await db.brackets.replace_one({"tournament_id": raw["tournament_id"]}, bracket_doc, upsert=False)
    return True


async def _build_live_matches_snapshot(db) -> list[dict[str, Any]]:
    events = await db.matchzy_events.find({"matchid": {"$ne": None}}, {"_id": 0}).sort("received_at", 1).to_list(2000)
    by_match: dict[str, dict[str, Any]] = {}

    def _extract_score(payload: dict[str, Any]) -> dict[str, Any]:
        team1 = payload.get("team1") or {}
        team2 = payload.get("team2") or {}
        return {
            "team1_name": team1.get("name") or payload.get("team1_name") or "Team 1",
            "team2_name": team2.get("name") or payload.get("team2_name") or "Team 2",
            "team1_score": team1.get("score", payload.get("team1_score", 0)) or 0,
            "team2_score": team2.get("score", payload.get("team2_score", 0)) or 0,
            "map_name": payload.get("map_name") or payload.get("map") or "—",
            "map_number": payload.get("map_number", 0) or 0,
        }

    defaults = {None, 0, "—", "Team 1", "Team 2"}

    def _merge_latest(acc: dict[str, Any], latest: dict[str, Any]) -> None:
        for key, value in latest.items():
            if value not in defaults:
                acc[key] = value
            else:
                acc.setdefault(key, value)

    for event in events:
        match_id = str(event["matchid"])
        match_row = by_match.setdefault(
            match_id,
            {"matchid": match_id, "events": 0, "last_event": None, "ended": False, "updated_at": None, "source": "matchzy"},
        )
        match_row["events"] += 1
        match_row["last_event"] = event["event"]
        match_row["updated_at"] = event["received_at"]
        _merge_latest(match_row, _extract_score(event.get("payload") or {}))
        if event["event"] == "series_end":
            match_row["ended"] = True

    active_servers = await db.cs2_servers.find(
        {"current_match_id": {"$ne": None}},
        {"_id": 0, "rcon_password": 0},
    ).to_list(100)
    for server in active_servers:
        match_id = str(server.get("current_match_id") or "").strip()
        if not match_id:
            continue
        existing = by_match.get(match_id)
        if existing and existing.get("ended"):
            continue
        if not existing:
            match_config = await db.matchzy_match_configs.find_one({"match_id": match_id}, {"_id": 0, "config": 1})
            duel_config = await db.duel_match_configs.find_one({"duel_id": match_id}, {"_id": 0, "config": 1})
            config = (match_config or duel_config or {}).get("config") or {}
            existing = _build_match_shell_from_config(match_id, config)
            existing["updated_at"] = server.get("last_checked_at") or server.get("created_at")
            existing["launch_status"] = server.get("status")
            existing["source"] = "server_state"
            by_match[match_id] = existing
        existing["server"] = server.get("name")
        existing["server_id"] = server.get("id")
        existing["launch_status"] = server.get("status") or existing.get("launch_status")
        public_server = _public_server(server)
        existing["connect_url"] = public_server.get("connect_url")
        existing["spectator_url"] = public_server.get("hltv_url")
        existing["join_password_required"] = public_server.get("join_password_required", False)
        existing["spectator_password_required"] = public_server.get("spectator_password_required", False)

    live = [row for row in by_match.values() if not row.get("ended")]
    return sorted(live, key=lambda item: item.get("updated_at") or "", reverse=True)


async def build_live_matches_snapshot(db) -> list[dict[str, Any]]:
    return await _build_live_matches_snapshot(db)


def extract_matchzy_winner_team(payload: dict[str, Any]) -> Optional[str]:
    return _extract_matchzy_winner_team(payload)


async def apply_matchzy_bracket_result(db, journal, match_id: str, payload: dict[str, Any], report_match_fn=report_match) -> bool:
    winner_team = _extract_matchzy_winner_team(payload)
    if winner_team not in {"team1", "team2"}:
        return False
    raw = await _find_bracket_doc_by_match_id(db, str(match_id))
    if not raw:
        return False
    bracket_doc = {k: v for k, v in raw.items() if k != "_id"}
    match_doc = _find_bracket_match_doc(bracket_doc, str(match_id))
    if not match_doc or match_doc.get("winner_id") or not match_doc.get("a") or not match_doc.get("b"):
        return False
    winner_id = match_doc["a"]["id"] if winner_team == "team1" else match_doc["b"]["id"]
    report_match_fn(bracket_doc, str(match_id), str(winner_id))
    resolved_match = _find_bracket_match_doc(bracket_doc, str(match_id))
    if resolved_match:
        resolved_match["result_source"] = "matchzy_webhook"
        resolved_match["result_received_at"] = _now_iso()
        resolved_match["launch_status"] = "finished"
        resolved_match["last_event"] = str(payload.get("event") or "series_end")
        resolved_match["series_score"] = _extract_matchzy_series_score(payload)
        if _extract_matchzy_map_name(payload):
            resolved_match["current_map"] = _extract_matchzy_map_name(payload)
    current_version = int(raw.get("version", 0) or 0)
    bracket_doc["version"] = current_version + 1
    await db.brackets.replace_one({"tournament_id": raw["tournament_id"]}, bracket_doc, upsert=False)
    await journal(
        "bracket_result_auto",
        None,
        {"tournament_id": raw["tournament_id"], "match_id": str(match_id), "winner_team": winner_team, "winner_id": str(winner_id)},
    )
    return True


async def apply_matchzy_duel_result(db, journal, match_id: str, payload: dict[str, Any]) -> bool:
    winner_team = _extract_matchzy_winner_team(payload)
    if winner_team not in {"team1", "team2"}:
        return False
    duel = await db.duels.find_one({"id": str(match_id)}, {"_id": 0})
    if not duel or not duel.get("opponent_id") or duel.get("status") == "closed":
        return False
    winner_id = duel["creator_id"] if winner_team == "team1" else duel["opponent_id"]
    winner_pseudo = duel["creator_pseudo"] if winner_team == "team1" else duel.get("opponent_pseudo")
    result = await db.duels.update_one(
        {"id": str(match_id), "status": {"$ne": "closed"}},
        {"$set": {
            "status": "closed",
            "winner_id": winner_id,
            "winner_pseudo": winner_pseudo,
            "closed_at": _now_iso(),
            "result_source": "matchzy_webhook",
            "launch_status": "finished",
            "series_score": _extract_matchzy_series_score(payload),
            "last_event": str(payload.get("event") or "series_end"),
        }},
    )
    if result.modified_count == 0:
        return False
    await db.users.update_one({"id": winner_id}, {"$inc": {"tokens": int(duel.get("stake", 0)) * 2}})
    await journal(
        "duel_result_auto",
        None,
        {"duel_id": str(match_id), "winner_team": winner_team, "winner_id": winner_id},
    )
    return True


async def _apply_matchzy_runtime_state(db, match_id: str, payload: dict[str, Any]) -> None:
    event_name = str(payload.get("event") or "unknown").strip().lower()
    now_iso = _now_iso()
    map_name = _extract_matchzy_map_name(payload)
    score = _extract_matchzy_series_score(payload)
    is_terminal = event_name == "series_end"
    started_at = now_iso if event_name in {"series_start", "map_start"} else None

    server_updates: dict[str, Any] = {
        "last_match_id": str(match_id),
        "last_checked_at": now_iso,
        "status": "online" if is_terminal else "live",
    }
    if map_name:
        server_updates["current_map"] = map_name
    if is_terminal:
        server_updates.update(
            {
                "current_match_id": None,
                "current_tournament_id": None,
                "current_bracket_match_id": None,
                "current_duel_id": None,
                "current_fun_match_id": None,
            }
        )
    else:
        server_updates["current_match_id"] = str(match_id)
    await db.cs2_servers.update_many(
        {"$or": [{"current_match_id": str(match_id)}, {"last_match_id": str(match_id)}]},
        {"$set": server_updates},
    )

    await _attach_match_runtime_metadata(
        db,
        str(match_id),
        {
            "launch_status": "finished" if is_terminal else "live",
            "last_event": event_name,
            "updated_at": now_iso,
            "started_at": started_at,
            "series_score": score,
            "current_map": map_name,
        },
    )

    duel_updates: dict[str, Any] = {
        "launch_status": "finished" if is_terminal else "live",
        "last_event": event_name,
        "updated_at": now_iso,
        "series_score": score,
    }
    if map_name:
        duel_updates["current_map"] = map_name
    if not is_terminal:
        duel_updates["status"] = "live"
        if started_at:
            duel_updates["started_at"] = started_at
    await db.duels.update_many(
        {"id": str(match_id), "status": {"$ne": "closed"}},
        {"$set": duel_updates},
    )

    fun_updates: dict[str, Any] = {
        "launch_status": "finished" if is_terminal else "live",
        "last_event": event_name,
        "updated_at": now_iso,
        "series_score": score,
    }
    if map_name:
        fun_updates["current_map"] = map_name
    if is_terminal:
        fun_updates["status"] = "closed"
        fun_updates["closed_at"] = now_iso
    else:
        fun_updates["status"] = "live"
        if started_at:
            fun_updates["started_at"] = started_at
    await db.fun_matches.update_many(
        {"id": str(match_id), "status": {"$ne": "closed"}},
        {"$set": fun_updates},
    )


def _rcon_exec(host: str, port: int, password: str, command: str, timeout: float = 8.0) -> str:
    """Blocking Source-RCON call. Run inside a thread via asyncio.to_thread."""
    with RconClient(host, int(port), passwd=password, timeout=timeout) as client:
        return client.run(command)


def _optional_steam_connect(host: Optional[str], port: Optional[int]) -> Optional[str]:
    if not host or not port:
        return None
    command = f"+connect {host}:{int(port)}"
    return f"steam://rungameid/730//{quote(command, safe=':+.')}"


def _private_steam_connect(host: Optional[str], port: Optional[int], password: Optional[str] = None) -> Optional[str]:
    if not host or not port:
        return None
    secret = (password or "").strip()
    command = f"+connect {host}:{int(port)}"
    if secret:
        command = f"{command} +password {secret}"
    return f"steam://rungameid/730//{quote(command, safe=':+.')}"


def _backend_public_base() -> str:
    return (os.environ.get("BACKEND_PUBLIC_URL") or "").strip().rstrip("/")


def _hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _server_control_mode(doc: dict) -> str:
    mode = str(doc.get("control_mode") or ("bridge" if doc.get("bridge_token_hash") else "rcon")).strip().lower()
    return mode if mode in {"rcon", "bridge"} else "rcon"


def _matchzy_config_header() -> tuple[Optional[str], Optional[str]]:
    token = (os.environ.get("MATCHZY_CONFIG_TOKEN") or "").strip()
    if not token:
        return None, None
    return "Authorization", f"Bearer {token}"


def _matchzy_remote_log_target() -> tuple[Optional[str], Optional[str], Optional[str]]:
    public_base = _backend_public_base()
    secret = (os.environ.get("MATCHZY_WEBHOOK_SECRET") or "").strip()
    if not public_base or not secret:
        return None, None, None
    return f"{public_base}/api/cs2/webhooks/matchzy", "Authorization", f"Bearer {secret}"


def _matchzy_load_url_command(url: str, header_name: Optional[str] = None, header_value: Optional[str] = None) -> str:
    parts = ["matchzy_loadmatch_url", json.dumps(url)]
    if header_name and header_value:
        parts.append(json.dumps(header_name))
        parts.append(json.dumps(header_value))
    return " ".join(parts)


def _matchzy_set_cvar_command(name: str, value: str) -> str:
    return f"{name} {json.dumps(value)}"


def _public_server(doc: dict) -> dict:
    """Strip the RCON password before returning a server to clients."""
    clean = {
        k: v for k, v in doc.items()
        if k not in ("_id", "rcon_password", "bridge_token_hash", "join_password", "gotv_password")
    }
    public_host = clean.get("public_host") or clean.get("host")
    game_port = clean.get("game_port") or clean.get("port")
    gotv_port = clean.get("gotv_port")
    join_password_required = bool(doc.get("join_password"))
    spectator_password_required = bool(doc.get("gotv_password"))
    clean["provider"] = clean.get("provider") or "custom"
    clean["control_mode"] = _server_control_mode(doc)
    clean["public_host"] = public_host
    clean["game_port"] = int(game_port) if game_port else None
    clean["gotv_port"] = int(gotv_port) if gotv_port else None
    clean["join_password_required"] = join_password_required
    clean["spectator_password_required"] = spectator_password_required
    clean["connect_url"] = None if join_password_required else _optional_steam_connect(public_host, clean.get("game_port"))
    clean["hltv_url"] = None if spectator_password_required else _optional_steam_connect(public_host, clean.get("gotv_port"))
    clean["last_match_id"] = clean.get("last_match_id")
    clean["current_tournament_id"] = clean.get("current_tournament_id")
    clean["current_bracket_match_id"] = clean.get("current_bracket_match_id")
    clean["last_bridge_seen_at"] = clean.get("last_bridge_seen_at")
    clean["capabilities"] = {
        "matchzy": bool(clean.get("matchzy_enabled")),
        "cssimpleadmin": bool(clean.get("cssimpleadmin_enabled")),
        "fake_rcon": bool(clean.get("fake_rcon_enabled")),
        "hltv": bool(clean.get("hltv_enabled") or clean.get("gotv_port")),
    }
    return clean


class ServerReq(BaseModel):
    name: str = Field(min_length=2, max_length=64)
    host: str = Field(min_length=3, max_length=128)
    port: int = Field(ge=1, le=65535, default=27015)
    control_mode: str = Field(default="rcon", pattern="^(rcon|bridge)$")
    rcon_password: Optional[str] = Field(default=None, min_length=1, max_length=128)
    bridge_token: Optional[str] = Field(default=None, min_length=8, max_length=256)
    provider: Optional[str] = Field(default="custom", max_length=64)
    region: Optional[str] = Field(default=None, max_length=64)
    public_host: Optional[str] = Field(default=None, max_length=128)
    game_port: Optional[int] = Field(default=None, ge=1, le=65535)
    gotv_port: Optional[int] = Field(default=None, ge=1, le=65535)
    join_password: Optional[str] = Field(default=None, min_length=1, max_length=128)
    gotv_password: Optional[str] = Field(default=None, min_length=1, max_length=128)
    panel_url: Optional[str] = Field(default=None, max_length=512)
    matchzy_enabled: bool = True
    cssimpleadmin_enabled: bool = False
    fake_rcon_enabled: bool = False
    hltv_enabled: bool = False
    notes: Optional[str] = Field(default=None, max_length=1000)


class ServerPatchReq(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=64)
    host: Optional[str] = Field(default=None, min_length=3, max_length=128)
    port: Optional[int] = Field(default=None, ge=1, le=65535)
    control_mode: Optional[str] = Field(default=None, pattern="^(rcon|bridge)$")
    rcon_password: Optional[str] = Field(default=None, min_length=1, max_length=128)
    bridge_token: Optional[str] = Field(default=None, min_length=8, max_length=256)
    provider: Optional[str] = Field(default=None, max_length=64)
    region: Optional[str] = Field(default=None, max_length=64)
    public_host: Optional[str] = Field(default=None, max_length=128)
    game_port: Optional[int] = Field(default=None, ge=1, le=65535)
    gotv_port: Optional[int] = Field(default=None, ge=1, le=65535)
    join_password: Optional[str] = Field(default=None, min_length=1, max_length=128)
    gotv_password: Optional[str] = Field(default=None, min_length=1, max_length=128)
    panel_url: Optional[str] = Field(default=None, max_length=512)
    matchzy_enabled: Optional[bool] = None
    cssimpleadmin_enabled: Optional[bool] = None
    fake_rcon_enabled: Optional[bool] = None
    hltv_enabled: Optional[bool] = None
    notes: Optional[str] = Field(default=None, max_length=1000)


class RconCmd(BaseModel):
    command: str = Field(min_length=1, max_length=512)


class MatchSetupReq(BaseModel):
    matchzy_url: Optional[str] = Field(default=None, max_length=512)
    raw_command: Optional[str] = Field(default=None, max_length=512)
    platform_match_id: Optional[str] = Field(default=None, max_length=128)
    header_name: Optional[str] = Field(default=None, max_length=128)
    header_value: Optional[str] = Field(default=None, max_length=512)
    tournament_id: Optional[str] = Field(default=None, max_length=128)
    bracket_match_id: Optional[str] = Field(default=None, max_length=128)


class LaunchBracketMatchReq(BaseModel):
    server_id: str = Field(min_length=8, max_length=128)
    num_maps: int = Field(default=1, ge=1, le=5)
    maplist: list[str] = Field(default_factory=list)
    map_sides: list[str] = Field(default_factory=list)
    players_per_team: int = Field(default=5, ge=1, le=7)
    clinch_series: bool = True
    allow_incomplete_roster: bool = False
    cvars: dict[str, str] = Field(default_factory=dict)


class BridgeHeartbeatReq(BaseModel):
    status: Optional[str] = Field(default=None, max_length=32)
    current_map: Optional[str] = Field(default=None, max_length=128)
    player_count: Optional[int] = Field(default=None, ge=0, le=64)
    plugin_version: Optional[str] = Field(default=None, max_length=64)


class BridgeCommandResultReq(BaseModel):
    status: str = Field(pattern="^(completed|failed)$")
    output: Optional[str] = Field(default=None, max_length=4000)


async def queue_bridge_command(
    db,
    srv: dict,
    command: str,
    *,
    kind: str = "console_command",
    metadata: Optional[dict[str, Any]] = None,
    created_by: Optional[str] = None,
) -> dict:
    if _server_control_mode(srv) != "bridge":
        raise HTTPException(409, "Ce serveur n'est pas en mode bridge")
    if not srv.get("bridge_token_hash"):
        raise HTTPException(409, "Bridge token manquant pour ce serveur")
    now_iso = _now_iso()
    doc = {
        "id": str(uuid.uuid4()),
        "server_id": srv["id"],
        "kind": kind,
        "command": command,
        "metadata": metadata or {},
        "status": "pending",
        "attempts": 0,
        "created_at": now_iso,
        "created_by": created_by,
        "dispatched_at": None,
        "completed_at": None,
        "output": None,
    }
    await db.cs2_bridge_commands.insert_one(doc)
    return doc


async def run_rcon_command(srv: dict, command: str) -> str:
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_rcon_exec, srv["host"], srv["port"], _dec(srv["rcon_password"]), command),
            timeout=12,
        )
    except asyncio.TimeoutError:
        raise HTTPException(504, "RCON timeout — serveur injoignable")
    except Exception as exc:
        raise HTTPException(502, f"Erreur RCON : {exc}")


async def run_server_command(
    db,
    srv: dict,
    command: str,
    *,
    kind: str = "console_command",
    metadata: Optional[dict[str, Any]] = None,
    created_by: Optional[str] = None,
) -> dict[str, Any]:
    if _server_control_mode(srv) == "bridge":
        queued = await queue_bridge_command(
            db,
            srv,
            command,
            kind=kind,
            metadata=metadata,
            created_by=created_by,
        )
        return {
            "mode": "bridge",
            "queued": True,
            "command_id": queued["id"],
            "output": "Commande placee en file d'attente pour le bridge serveur.",
        }
    output = await run_rcon_command(srv, command)
    return {"mode": "rcon", "queued": False, "command_id": None, "output": output}


def build_server_connect_url(srv: dict, *, spectator: bool = False) -> Optional[str]:
    host = srv.get("public_host") or srv.get("host")
    port = srv.get("gotv_port") if spectator else (srv.get("game_port") or srv.get("port"))
    password_key = "gotv_password" if spectator else "join_password"
    password = _dec(srv[password_key]) if srv.get(password_key) else None
    return _private_steam_connect(host, port, password)


def public_server_payload(srv: dict) -> dict:
    return _public_server(srv)


def build_duel_matchzy_config(
    *,
    duel_id: str,
    creator: dict,
    opponent: dict,
    map_name: str,
    cvars: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    creator_name = str(creator.get("pseudo") or creator.get("steam_id") or "Joueur 1").strip()
    opponent_name = str(opponent.get("pseudo") or opponent.get("steam_id") or "Joueur 2").strip()
    return {
        "matchid": duel_id,
        "team1": {"name": creator_name, "players": {str(creator["steam_id"]): creator_name}},
        "team2": {"name": opponent_name, "players": {str(opponent["steam_id"]): opponent_name}},
        "num_maps": 1,
        "maplist": [map_name],
        "map_sides": ["knife"],
        "clinch_series": True,
        "players_per_team": 1,
        "cvars": {
            "hostname": f"ReadyUp Arena Duel | {creator_name} vs {opponent_name}",
            **(cvars or {}),
        },
    }


def matchzy_config_header() -> tuple[Optional[str], Optional[str]]:
    return _matchzy_config_header()


def matchzy_load_url_command(url: str, header_name: Optional[str] = None, header_value: Optional[str] = None) -> str:
    return _matchzy_load_url_command(url, header_name, header_value)


def backend_public_base() -> str:
    return _backend_public_base()


async def configure_matchzy_remote_log(
    db,
    srv: dict,
    *,
    created_by: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> list[dict[str, Any]]:
    webhook_url, auth_key, auth_value = _matchzy_remote_log_target()
    if not webhook_url or not auth_key or not auth_value:
        return []
    commands = [
        _matchzy_set_cvar_command("matchzy_remote_log_url", webhook_url),
        _matchzy_set_cvar_command("matchzy_remote_log_auth_key", auth_key),
        _matchzy_set_cvar_command("matchzy_remote_log_auth_value", auth_value),
    ]
    outputs: list[dict[str, Any]] = []
    for command in commands:
        result = await run_server_command(
            db,
            srv,
            command,
            kind="matchzy_remote_log",
            metadata=metadata,
            created_by=created_by,
        )
        outputs.append({
            "command": command,
            "mode": result["mode"],
            "queued": result["queued"],
            "command_id": result.get("command_id"),
            "output": result.get("output"),
        })
    return outputs


def _match_launch_group_order(match_doc: dict[str, Any]) -> tuple[int, int, int]:
    group_order = {"W": 0, "L": 1, "GF": 2}
    return (
        group_order.get(str(match_doc.get("group") or "").strip().upper(), 9),
        int(match_doc.get("round", 0) or 0),
        int(match_doc.get("index", 0) or 0),
    )


def _match_is_launchable(match_doc: dict[str, Any]) -> bool:
    launch_status = str(match_doc.get("launch_status") or "").strip().lower()
    if match_doc.get("winner_id"):
        return False
    if not match_doc.get("a") or not match_doc.get("b"):
        return False
    return launch_status not in {"launch_pending", "live", "finished"}


def _server_ready_for_match_launch(server_doc: dict[str, Any]) -> bool:
    status = str(server_doc.get("status") or "").strip().lower()
    return bool(
        server_doc.get("matchzy_enabled")
        and not server_doc.get("current_match_id")
        and status not in {"live", "launch_pending", "allocating"}
    )


def _select_matchzy_roster_candidates(docs: list[dict[str, Any]]) -> list[tuple[int, str, str, str]]:
    candidates: list[tuple[int, str, str, str]] = []
    seen: set[str] = set()
    for doc in docs:
        steam_id = str(doc.get("steam_id") or "").strip()
        if not steam_id or not steam_id.isdigit() or steam_id in seen:
            continue
        seen.add(steam_id)
        pseudo = str(doc.get("pseudo") or steam_id).strip() or steam_id
        team_role = str(doc.get("team_role") or doc.get("role") or "").strip().lower()
        priority = 0 if team_role == "captain" else 1
        candidates.append((priority, pseudo.lower(), steam_id, pseudo))
    candidates.sort()
    return candidates


def _build_matchzy_team_from_candidate_docs(
    *,
    team_name: str,
    docs: list[dict[str, Any]],
    players_per_team: int,
    allow_incomplete_roster: bool,
    missing_label: str,
) -> dict[str, Any]:
    candidates = _select_matchzy_roster_candidates(docs)
    selected = candidates[:players_per_team]
    if not selected:
        raise HTTPException(409, f"Aucun Steam ID exploitable trouve pour {missing_label}")
    if not allow_incomplete_roster and len(selected) < players_per_team:
        raise HTTPException(
            409,
            f"Roster incomplet pour {missing_label}: {len(selected)}/{players_per_team} joueurs avec Steam ID",
        )
    return {
        "name": team_name,
        "players": {steam_id: pseudo for _, _, steam_id, pseudo in selected},
    }


async def _load_matchzy_team_payload_for_entrant(
    db,
    entrant: dict[str, Any],
    fallback_name: str,
    players_per_team: int,
    allow_incomplete_roster: bool,
) -> dict[str, Any]:
    entrant_name = str(entrant.get("name") or fallback_name).strip() or fallback_name
    entrant_members = list(entrant.get("members") or entrant.get("roster_players") or [])
    if entrant_members:
        return _build_matchzy_team_from_candidate_docs(
            team_name=entrant_name,
            docs=entrant_members,
            players_per_team=players_per_team,
            allow_incomplete_roster=allow_incomplete_roster,
            missing_label=entrant_name,
        )

    team_id = str(entrant.get("id") or "").strip()
    team_doc = await db.teams.find_one({"id": team_id}, {"_id": 0, "id": 1, "name": 1}) if team_id else None
    if not team_doc:
        raise HTTPException(404, f"Equipe introuvable pour le match ({entrant_name})")

    user_docs = await db.users.find(
        {"team_id": team_id},
        {"_id": 0, "pseudo": 1, "steam_id": 1, "team_role": 1, "role": 1},
    ).to_list(30)
    seed_docs = await db.players.find(
        {"team_id": team_id},
        {"_id": 0, "pseudo": 1, "steam_id": 1, "team_role": 1, "role": 1},
    ).to_list(30)

    return _build_matchzy_team_from_candidate_docs(
        team_name=team_doc.get("name") or entrant_name,
        docs=[*user_docs, *seed_docs],
        players_per_team=players_per_team,
        allow_incomplete_roster=allow_incomplete_roster,
        missing_label=team_doc.get("name") or entrant_name,
    )


async def _store_matchzy_config_doc(
    db,
    tournament_id: str,
    match_id: str,
    server_id: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    now_iso = _now_iso()
    doc = {
        "id": f"{tournament_id}:{match_id}",
        "tournament_id": tournament_id,
        "match_id": match_id,
        "server_id": server_id,
        "config": config,
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    await db.matchzy_match_configs.replace_one(
        {"tournament_id": tournament_id, "match_id": match_id},
        doc,
        upsert=True,
    )
    return doc


async def _store_fun_matchzy_config_doc(
    db,
    fun_match_id: str,
    server_id: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    now_iso = _now_iso()
    doc = {
        "id": f"fun:{fun_match_id}",
        "scope": "fun_match",
        "fun_match_id": fun_match_id,
        "match_id": fun_match_id,
        "server_id": server_id,
        "config": config,
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    await db.matchzy_match_configs.replace_one(
        {"fun_match_id": fun_match_id},
        doc,
        upsert=True,
    )
    return doc


async def launch_bracket_match_on_server(
    db,
    journal,
    tournament_id: str,
    match_id: str,
    server_id: str,
    *,
    created_by: Optional[str] = None,
    num_maps: int = 1,
    maplist: Optional[list[str]] = None,
    map_sides: Optional[list[str]] = None,
    players_per_team: int = 5,
    clinch_series: bool = True,
    allow_incomplete_roster: bool = False,
    cvars: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    srv = await db.cs2_servers.find_one({"id": server_id}, {"_id": 0})
    if not srv:
        raise HTTPException(404, "Serveur CS2 introuvable")
    if srv.get("status") == "live" and srv.get("current_match_id") and str(srv.get("current_match_id")) != str(match_id):
        raise HTTPException(409, f"Le serveur {srv.get('name')} heberge deja le match {srv.get('current_match_id')}")

    public_base = _backend_public_base()
    if not public_base:
        raise HTTPException(500, "BACKEND_PUBLIC_URL manquant pour generer l'URL MatchZy")

    tournament = await db.tournaments.find_one({"id": tournament_id}, {"_id": 0})
    if not tournament:
        raise HTTPException(404, "Tournoi introuvable")
    bracket_doc = await db.brackets.find_one({"tournament_id": tournament_id}, {"_id": 0})
    if not bracket_doc:
        raise HTTPException(404, "Bracket introuvable")
    match_doc = _find_bracket_match_doc(bracket_doc, match_id)
    if not match_doc:
        raise HTTPException(404, "Match de bracket introuvable")
    if match_doc.get("winner_id"):
        raise HTTPException(409, "Ce match est deja termine")
    if not match_doc.get("a") or not match_doc.get("b"):
        raise HTTPException(409, "Les deux equipes ne sont pas encore connues pour ce match")

    team1 = await _load_matchzy_team_payload_for_entrant(
        db,
        dict(match_doc["a"]),
        str(match_doc.get("a_name") or "Equipe 1"),
        players_per_team,
        allow_incomplete_roster,
    )
    team2 = await _load_matchzy_team_payload_for_entrant(
        db,
        dict(match_doc["b"]),
        str(match_doc.get("b_name") or "Equipe 2"),
        players_per_team,
        allow_incomplete_roster,
    )

    selected_maps = [str(item).strip() for item in (maplist or tournament.get("maps") or []) if str(item).strip()]
    if not selected_maps:
        selected_maps = ["de_dust2"]
    if len(selected_maps) < num_maps:
        raise HTTPException(400, f"Maplist insuffisante pour un BO{num_maps} ({len(selected_maps)} map(s) disponible(s))")
    selected_maps = selected_maps[:num_maps]

    selected_sides = [str(item).strip() for item in (map_sides or []) if str(item).strip()]
    if not selected_sides:
        selected_sides = ["knife"] * num_maps
    while len(selected_sides) < num_maps:
        selected_sides.append(selected_sides[-1] if selected_sides else "knife")
    selected_sides = selected_sides[:num_maps]

    config = {
        "matchid": str(match_id),
        "team1": team1,
        "team2": team2,
        "num_maps": num_maps,
        "maplist": selected_maps,
        "map_sides": selected_sides,
        "clinch_series": clinch_series,
        "players_per_team": players_per_team,
        "cvars": {
            "hostname": f"ReadyUp Arena | {tournament.get('name', 'Tournament')} | {team1['name']} vs {team2['name']}",
            **(cvars or {}),
        },
    }
    stored = await _store_matchzy_config_doc(db, tournament_id, str(match_id), server_id, config)

    config_url = f"{public_base}/api/cs2/tournaments/{tournament_id}/bracket-matches/{match_id}/matchzy-config"
    header_name, header_value = _matchzy_config_header()
    remote_log_outputs = await configure_matchzy_remote_log(
        db,
        srv,
        created_by=created_by,
        metadata={"tournament_id": tournament_id, "match_id": match_id, "config_url": config_url},
    )
    command = _matchzy_load_url_command(config_url, header_name, header_value)
    result = await run_server_command(
        db,
        srv,
        command,
        kind="launch_bracket_match",
        metadata={"tournament_id": tournament_id, "match_id": match_id, "config_url": config_url},
        created_by=created_by,
    )

    now_iso = _now_iso()
    await db.cs2_servers.update_one(
        {"id": server_id},
        {"$set": {
            "current_match_id": str(match_id),
            "current_tournament_id": str(tournament_id),
            "current_bracket_match_id": str(match_id),
            "last_match_id": str(match_id),
            "status": "launch_pending" if result["queued"] else "live",
            "last_checked_at": now_iso,
        }},
    )
    await _attach_match_runtime_metadata(
        db,
        str(match_id),
        {
            "server_id": server_id,
            "server_name": srv.get("name"),
            "server_host": srv.get("public_host") or srv.get("host"),
            "server_game_port": srv.get("game_port") or srv.get("port"),
            "matchzy_config_url": config_url,
            "launch_status": "launch_pending" if result["queued"] else "live",
            "launch_error": None,
            "launched_at": now_iso,
            "updated_at": now_iso,
            "num_maps": num_maps,
            "players_per_team": players_per_team,
        },
    )
    if journal:
        await journal(
            "cs2_bracket_match_launched",
            created_by,
            {"tournament_id": tournament_id, "match_id": str(match_id), "server_id": server_id, "server_name": srv.get("name")},
        )
    return {
        "ok": True,
        "tournament_id": tournament_id,
        "match_id": str(match_id),
        "server_id": server_id,
        "server_name": srv.get("name"),
        "config_url": config_url,
        "match_url": f"/match/{match_id}",
        "config_preview": stored["config"],
        "mode": result["mode"],
        "queued": result["queued"],
        "command_id": result.get("command_id"),
        "output": result["output"],
        "remote_log_configured": bool(remote_log_outputs),
        "remote_log_outputs": remote_log_outputs,
        "tournament_name": tournament.get("name"),
    }


def build_fun_match_matchzy_config(
    *,
    fun_match_id: str,
    title: str,
    map_name: str,
    teams: list[dict[str, Any]],
    cvars: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    if len(teams) < 2:
        raise HTTPException(409, "Deux equipes 5v5 sont requises pour lancer ce match fun")

    team1_doc, team2_doc = teams[:2]
    team1 = _build_matchzy_team_from_candidate_docs(
        team_name=str(team1_doc.get("name") or "Equipe 1").strip() or "Equipe 1",
        docs=list(team1_doc.get("members") or []),
        players_per_team=FUN_MATCH_TEAM_SIZE,
        allow_incomplete_roster=False,
        missing_label=str(team1_doc.get("name") or "Equipe 1"),
    )
    team2 = _build_matchzy_team_from_candidate_docs(
        team_name=str(team2_doc.get("name") or "Equipe 2").strip() or "Equipe 2",
        docs=list(team2_doc.get("members") or []),
        players_per_team=FUN_MATCH_TEAM_SIZE,
        allow_incomplete_roster=False,
        missing_label=str(team2_doc.get("name") or "Equipe 2"),
    )
    selected_map = str(map_name or "de_dust2").strip() or "de_dust2"
    safe_title = str(title or "Fun 5v5").strip() or "Fun 5v5"
    return {
        "matchid": str(fun_match_id),
        "team1": team1,
        "team2": team2,
        "num_maps": 1,
        "maplist": [selected_map],
        "map_sides": ["knife"],
        "clinch_series": True,
        "players_per_team": FUN_MATCH_TEAM_SIZE,
        "cvars": {
            "hostname": f"ReadyUp Arena Fun 5v5 | {safe_title} | {team1['name']} vs {team2['name']}",
            **(cvars or {}),
        },
    }


async def launch_fun_match_on_server(
    db,
    journal,
    fun_match_id: str,
    server_id: str,
    *,
    created_by: Optional[str] = None,
    cvars: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    srv = await db.cs2_servers.find_one({"id": server_id}, {"_id": 0})
    if not srv:
        raise HTTPException(404, "Serveur CS2 introuvable")
    if srv.get("status") == "live" and srv.get("current_match_id") and str(srv.get("current_match_id")) != str(fun_match_id):
        raise HTTPException(409, f"Le serveur {srv.get('name')} heberge deja le match {srv.get('current_match_id')}")

    public_base = _backend_public_base()
    if not public_base:
        raise HTTPException(500, "BACKEND_PUBLIC_URL manquant pour generer l'URL MatchZy")

    fun_match_doc = await db.fun_matches.find_one({"id": str(fun_match_id)}, {"_id": 0})
    if not fun_match_doc:
        raise HTTPException(404, "Match fun introuvable")
    if str(fun_match_doc.get("status") or "").strip().lower() == "closed":
        raise HTTPException(409, "Ce match fun est deja ferme")

    summary = summarize_fun_match(fun_match_doc)
    teams = list(summary.get("teams") or [])
    if not summary.get("ready_to_start") or len(teams) < 2:
        raise HTTPException(409, "Le lobby fun doit contenir 10 joueurs pour lancer un serveur")

    config = build_fun_match_matchzy_config(
        fun_match_id=str(fun_match_id),
        title=str(summary.get("title") or "Fun 5v5"),
        map_name=str(summary.get("map") or "de_dust2"),
        teams=teams,
        cvars=cvars,
    )
    stored = await _store_fun_matchzy_config_doc(db, str(fun_match_id), server_id, config)

    config_url = f"{public_base}/api/fun-matches/{fun_match_id}/matchzy-config"
    header_name, header_value = _matchzy_config_header()
    remote_log_outputs = await configure_matchzy_remote_log(
        db,
        srv,
        created_by=created_by,
        metadata={"fun_match_id": str(fun_match_id), "config_url": config_url},
    )
    command = _matchzy_load_url_command(config_url, header_name, header_value)
    result = await run_server_command(
        db,
        srv,
        command,
        kind="launch_fun_match",
        metadata={"fun_match_id": str(fun_match_id), "config_url": config_url},
        created_by=created_by,
    )

    now_iso = _now_iso()
    launch_status = "launch_pending" if result["queued"] else "live"
    await db.cs2_servers.update_one(
        {"id": server_id},
        {"$set": {
            "current_match_id": str(fun_match_id),
            "current_fun_match_id": str(fun_match_id),
            "last_match_id": str(fun_match_id),
            "status": launch_status,
            "last_checked_at": now_iso,
        }},
    )
    await db.fun_matches.update_one(
        {"id": str(fun_match_id)},
        {"$set": {
            "status": launch_status,
            "launch_status": launch_status,
            "launch_error": None,
            "launched_at": now_iso,
            "updated_at": now_iso,
            "server_id": server_id,
            "server_name": srv.get("name"),
            "server_host": srv.get("public_host") or srv.get("host"),
            "server_game_port": srv.get("game_port") or srv.get("port"),
            "server_gotv_port": srv.get("gotv_port"),
            "matchzy_config_url": config_url,
            "match_room_url": f"/match/{fun_match_id}",
            "launch_command_id": result.get("command_id"),
            "launch_mode": result.get("mode"),
            "teams": teams,
        }},
    )
    if journal:
        await journal(
            "cs2_fun_match_launched",
            created_by,
            {"fun_match_id": str(fun_match_id), "server_id": server_id, "server_name": srv.get("name")},
        )
    return {
        "ok": True,
        "fun_match_id": str(fun_match_id),
        "server_id": server_id,
        "server_name": srv.get("name"),
        "config_url": config_url,
        "match_url": f"/match/{fun_match_id}",
        "config_preview": stored["config"],
        "mode": result["mode"],
        "queued": result["queued"],
        "command_id": result.get("command_id"),
        "output": result["output"],
        "remote_log_configured": bool(remote_log_outputs),
        "remote_log_outputs": remote_log_outputs,
        "title": summary.get("title"),
    }


async def auto_launch_ready_bracket_matches(
    db,
    journal,
    tournament_id: str,
    *,
    created_by: Optional[str] = None,
    max_matches: Optional[int] = None,
    num_maps: int = 1,
    maplist: Optional[list[str]] = None,
    map_sides: Optional[list[str]] = None,
    players_per_team: int = 5,
    clinch_series: bool = True,
    allow_incomplete_roster: bool = False,
    cvars: Optional[dict[str, str]] = None,
) -> list[dict[str, Any]]:
    bracket_doc = await db.brackets.find_one({"tournament_id": tournament_id}, {"_id": 0})
    if not bracket_doc:
        return []

    ready_matches = sorted(
        [match_doc for match_doc in _iter_bracket_matches_doc(bracket_doc) if _match_is_launchable(match_doc)],
        key=_match_launch_group_order,
    )
    if not ready_matches:
        return []

    launched: list[dict[str, Any]] = []
    for match_doc in ready_matches:
        if max_matches is not None and len(launched) >= max_matches:
            break
        servers = await db.cs2_servers.find({}, {"_id": 0}).sort("created_at", 1).to_list(200)
        available_servers = [server for server in servers if _server_ready_for_match_launch(server)]
        if not available_servers:
            break

        preferred_server = next(
            (server for server in available_servers if str(server.get("id")) == str(match_doc.get("server_id") or "")),
            None,
        )
        server = preferred_server or available_servers[0]
        try:
            launched.append(
                await launch_bracket_match_on_server(
                    db,
                    journal,
                    tournament_id,
                    str(match_doc["id"]),
                    str(server["id"]),
                    created_by=created_by,
                    num_maps=num_maps,
                    maplist=maplist,
                    map_sides=map_sides,
                    players_per_team=players_per_team,
                    clinch_series=clinch_series,
                    allow_incomplete_roster=allow_incomplete_roster,
                    cvars=cvars,
                )
            )
        except HTTPException as exc:
            await _attach_match_runtime_metadata(
                db,
                str(match_doc["id"]),
                {
                    "launch_status": "failed",
                    "launch_error": str(exc.detail),
                    "updated_at": _now_iso(),
                },
            )
    return launched


async def auto_launch_live_tournament_matches(
    db,
    journal,
    *,
    created_by: Optional[str] = None,
    max_matches: Optional[int] = None,
    num_maps: int = 1,
    maplist: Optional[list[str]] = None,
    map_sides: Optional[list[str]] = None,
    players_per_team: int = 5,
    clinch_series: bool = True,
    allow_incomplete_roster: bool = False,
    cvars: Optional[dict[str, str]] = None,
) -> list[dict[str, Any]]:
    tournaments = await db.tournaments.find({"status": {"$in": ["live", "starting"]}}, {"_id": 0, "id": 1, "starts_at": 1}).sort("starts_at", 1).to_list(100)
    launched: list[dict[str, Any]] = []
    for tournament in tournaments:
        remaining = None if max_matches is None else max(max_matches - len(launched), 0)
        if remaining == 0:
            break
        items = await auto_launch_ready_bracket_matches(
            db,
            journal,
            str(tournament["id"]),
            created_by=created_by,
            max_matches=remaining,
            num_maps=num_maps,
            maplist=maplist,
            map_sides=map_sides,
            players_per_team=players_per_team,
            clinch_series=clinch_series,
            allow_incomplete_roster=allow_incomplete_roster,
            cvars=cvars,
        )
        launched.extend(items)
    return launched


async def auto_launch_ready_fun_matches(
    db,
    journal,
    *,
    created_by: Optional[str] = None,
    max_matches: Optional[int] = None,
    cvars: Optional[dict[str, str]] = None,
) -> list[dict[str, Any]]:
    docs = await db.fun_matches.find({"status": {"$in": ["ready", "launch_failed"]}}, {"_id": 0}).sort("created_at", 1).to_list(100)
    if not docs:
        return []

    launched: list[dict[str, Any]] = []
    for doc in docs:
        summary = summarize_fun_match(doc)
        if not summary.get("ready_to_start"):
            continue
        if max_matches is not None and len(launched) >= max_matches:
            break

        servers = await db.cs2_servers.find({}, {"_id": 0}).sort("created_at", 1).to_list(200)
        available_servers = [server for server in servers if _server_ready_for_match_launch(server)]
        if not available_servers:
            await db.fun_matches.update_one(
                {"id": str(doc["id"]), "status": {"$in": ["ready", "launch_failed"]}},
                {"$set": {"launch_status": "waiting_server", "launch_error": None, "updated_at": _now_iso()}},
            )
            break

        preferred_server = next(
            (server for server in available_servers if str(server.get("id")) == str(doc.get("server_id") or "")),
            None,
        )
        server = preferred_server or available_servers[0]
        try:
            launched.append(
                await launch_fun_match_on_server(
                    db,
                    journal,
                    str(doc["id"]),
                    str(server["id"]),
                    created_by=created_by,
                    cvars=cvars,
                )
            )
        except HTTPException as exc:
            await db.fun_matches.update_one(
                {"id": str(doc["id"])},
                {"$set": {"status": "launch_failed", "launch_status": "launch_failed", "launch_error": str(exc.detail), "updated_at": _now_iso()}},
            )
    return launched


def build_cs2_router(db, get_current_user, get_admin_user, journal):
    router = APIRouter(prefix="/api/cs2")

    async def _get_server(sid: str) -> dict:
        srv = await db.cs2_servers.find_one({"id": sid})
        if not srv:
            raise HTTPException(404, "Serveur CS2 introuvable")
        return srv

    async def _queue_bridge_command(
        srv: dict,
        command: str,
        *,
        kind: str = "console_command",
        metadata: Optional[dict[str, Any]] = None,
        created_by: Optional[str] = None,
    ) -> dict:
        if _server_control_mode(srv) != "bridge":
            raise HTTPException(409, "Ce serveur n'est pas en mode bridge")
        if not srv.get("bridge_token_hash"):
            raise HTTPException(409, "Bridge token manquant pour ce serveur")
        now_iso = _now_iso()
        doc = {
            "id": str(uuid.uuid4()),
            "server_id": srv["id"],
            "kind": kind,
            "command": command,
            "metadata": metadata or {},
            "status": "pending",
            "attempts": 0,
            "created_at": now_iso,
            "created_by": created_by,
            "dispatched_at": None,
            "completed_at": None,
            "output": None,
        }
        await db.cs2_bridge_commands.insert_one(doc)
        return doc

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

    async def _run_server_command(
        srv: dict,
        command: str,
        *,
        kind: str = "console_command",
        metadata: Optional[dict[str, Any]] = None,
        created_by: Optional[str] = None,
    ) -> dict[str, Any]:
        if _server_control_mode(srv) == "bridge":
            queued = await _queue_bridge_command(
                srv,
                command,
                kind=kind,
                metadata=metadata,
                created_by=created_by,
            )
            return {
                "mode": "bridge",
                "queued": True,
                "command_id": queued["id"],
                "output": "Commande placee en file d'attente pour le plugin serveur",
            }
        return {
            "mode": "rcon",
            "queued": False,
            "command_id": None,
            "output": await _run_rcon(srv, command),
        }

    async def _get_bridge_server(authorization: Optional[str]) -> dict:
        token = ((authorization or "").replace("Bearer ", "", 1)).strip()
        if not token:
            raise HTTPException(401, "Bridge non autorise")
        srv = await db.cs2_servers.find_one({"bridge_token_hash": _hash_secret(token)})
        if not srv or _server_control_mode(srv) != "bridge":
            raise HTTPException(401, "Bridge non autorise")
        return srv

    async def _configure_matchzy_remote_log(
        srv: dict,
        *,
        created_by: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        webhook_url, auth_key, auth_value = _matchzy_remote_log_target()
        if not webhook_url or not auth_key or not auth_value:
            return []
        commands = [
            _matchzy_set_cvar_command("matchzy_remote_log_url", webhook_url),
            _matchzy_set_cvar_command("matchzy_remote_log_auth_key", auth_key),
            _matchzy_set_cvar_command("matchzy_remote_log_auth_value", auth_value),
        ]
        outputs: list[dict[str, Any]] = []
        for command in commands:
            result = await _run_server_command(
                srv,
                command,
                kind="matchzy_remote_log",
                metadata=metadata,
                created_by=created_by,
            )
            outputs.append({
                "command": command,
                "mode": result["mode"],
                "queued": result["queued"],
                "command_id": result.get("command_id"),
                "output": result["output"],
            })
        return outputs

    def _iter_bracket_matches(bracket_doc: dict):
        for group in ("W", "L", "GF"):
            for match_doc in bracket_doc.get("matches", {}).get(group, []):
                yield match_doc

    def _find_bracket_match(bracket_doc: dict, match_id: str) -> Optional[dict]:
        for match_doc in _iter_bracket_matches(bracket_doc):
            if str(match_doc.get("id")) == str(match_id):
                return match_doc
        return None

    async def _get_bracket_match_or_404(tournament_id: str, match_id: str) -> tuple[dict, dict, dict]:
        tournament = await db.tournaments.find_one({"id": tournament_id}, {"_id": 0})
        if not tournament:
            raise HTTPException(404, "Tournoi introuvable")
        bracket_doc = await db.brackets.find_one({"tournament_id": tournament_id}, {"_id": 0})
        if not bracket_doc:
            raise HTTPException(404, "Bracket introuvable")
        match_doc = _find_bracket_match(bracket_doc, match_id)
        if not match_doc:
            raise HTTPException(404, "Match de bracket introuvable")
        return tournament, bracket_doc, match_doc

    async def _load_matchzy_team_payload(team_id: str, fallback_name: str, players_per_team: int, allow_incomplete_roster: bool) -> dict:
        team_doc = await db.teams.find_one({"id": team_id}, {"_id": 0, "id": 1, "name": 1})
        if not team_doc:
            raise HTTPException(404, f"Equipe introuvable pour le match ({fallback_name})")

        user_docs = await db.users.find(
            {"team_id": team_id},
            {"_id": 0, "pseudo": 1, "steam_id": 1, "team_role": 1},
        ).to_list(30)
        seed_docs = await db.players.find(
            {"team_id": team_id},
            {"_id": 0, "pseudo": 1, "steam_id": 1, "team_role": 1},
        ).to_list(30)

        candidates: list[tuple[int, str, str, str]] = []
        seen: set[str] = set()
        for doc in user_docs + seed_docs:
            steam_id = str(doc.get("steam_id") or "").strip()
            if not steam_id or not steam_id.isdigit() or steam_id in seen:
                continue
            seen.add(steam_id)
            pseudo = str(doc.get("pseudo") or steam_id).strip() or steam_id
            priority = 0 if str(doc.get("team_role") or "").strip().lower() == "captain" else 1
            candidates.append((priority, pseudo.lower(), steam_id, pseudo))

        candidates.sort()
        selected = candidates[:players_per_team]
        if not selected:
            raise HTTPException(409, f"Aucun Steam ID exploitable trouve pour l'equipe {team_doc.get('name') or fallback_name}")
        if not allow_incomplete_roster and len(selected) < players_per_team:
            raise HTTPException(
                409,
                f"Roster incomplet pour {team_doc.get('name') or fallback_name}: {len(selected)}/{players_per_team} joueurs avec Steam ID",
            )

        return {
            "name": team_doc.get("name") or fallback_name,
            "players": {steam_id: pseudo for _, _, steam_id, pseudo in selected},
        }

    async def _store_matchzy_config(
        tournament_id: str,
        match_id: str,
        server_id: str,
        config: dict[str, Any],
    ) -> dict:
        now_iso = _now_iso()
        doc = {
            "id": f"{tournament_id}:{match_id}",
            "tournament_id": tournament_id,
            "match_id": match_id,
            "server_id": server_id,
            "config": config,
            "created_at": now_iso,
            "updated_at": now_iso,
        }
        await db.matchzy_match_configs.replace_one(
            {"tournament_id": tournament_id, "match_id": match_id},
            doc,
            upsert=True,
        )
        return doc

    async def _build_matchzy_config(
        tournament_id: str,
        match_id: str,
        server_id: str,
        req: LaunchBracketMatchReq,
    ) -> tuple[dict, dict, dict]:
        tournament, bracket_doc, match_doc = await _get_bracket_match_or_404(tournament_id, match_id)
        if match_doc.get("winner_id"):
            raise HTTPException(409, "Ce match est deja termine")
        if not match_doc.get("a") or not match_doc.get("b"):
            raise HTTPException(409, "Les deux equipes ne sont pas encore connues pour ce match")

        team1 = await _load_matchzy_team_payload(
            str(match_doc["a"]["id"]),
            str(match_doc.get("a_name") or "Equipe 1"),
            req.players_per_team,
            req.allow_incomplete_roster,
        )
        team2 = await _load_matchzy_team_payload(
            str(match_doc["b"]["id"]),
            str(match_doc.get("b_name") or "Equipe 2"),
            req.players_per_team,
            req.allow_incomplete_roster,
        )

        maplist = [str(item).strip() for item in (req.maplist or tournament.get("maps") or []) if str(item).strip()]
        if not maplist:
            maplist = ["de_dust2"]
        if len(maplist) < req.num_maps:
            raise HTTPException(400, f"Maplist insuffisante pour un BO{req.num_maps} ({len(maplist)} map(s) disponible(s))")
        maplist = maplist[:req.num_maps]

        map_sides = [str(item).strip() for item in (req.map_sides or []) if str(item).strip()]
        if not map_sides:
            map_sides = ["knife"] * req.num_maps
        while len(map_sides) < req.num_maps:
            map_sides.append(map_sides[-1] if map_sides else "knife")
        map_sides = map_sides[:req.num_maps]

        config = {
            "matchid": match_id,
            "team1": team1,
            "team2": team2,
            "num_maps": req.num_maps,
            "maplist": maplist,
            "map_sides": map_sides,
            "clinch_series": req.clinch_series,
            "players_per_team": req.players_per_team,
            "cvars": {
                "hostname": f"ReadyUp Arena | {tournament.get('name', 'Tournament')} | {team1['name']} vs {team2['name']}",
                **(req.cvars or {}),
            },
        }
        stored = await _store_matchzy_config(tournament_id, match_id, server_id, config)
        return tournament, bracket_doc, stored

    async def _attach_bracket_match_metadata(tournament_id: str, match_id: str, updates: dict[str, Any]) -> dict:
        bracket_doc = await db.brackets.find_one({"tournament_id": tournament_id}, {"_id": 0})
        if not bracket_doc:
            raise HTTPException(404, "Bracket introuvable")
        match_doc = _find_bracket_match(bracket_doc, match_id)
        if not match_doc:
            raise HTTPException(404, "Match de bracket introuvable")
        match_doc.update(updates)
        await db.brackets.replace_one({"tournament_id": tournament_id}, bracket_doc, upsert=False)
        return bracket_doc

    async def _try_apply_matchzy_result(match_id: str, payload: dict[str, Any]) -> bool:
        return await apply_matchzy_bracket_result(db, journal, str(match_id), payload, report_match_fn=report_match)

    async def _try_apply_duel_matchzy_result(match_id: str, payload: dict[str, Any]) -> bool:
        return await apply_matchzy_duel_result(db, journal, str(match_id), payload)

    @router.post("/servers", dependencies=[Depends(get_admin_user)])
    async def create_server(req: ServerReq, user=Depends(get_admin_user)):
        control_mode = (req.control_mode or "rcon").strip().lower()
        if control_mode == "rcon" and not req.rcon_password:
            raise HTTPException(400, "rcon_password requis pour un serveur en mode rcon")
        if control_mode == "bridge" and not req.bridge_token:
            raise HTTPException(400, "bridge_token requis pour un serveur en mode bridge")
        srv = {
            "id": str(uuid.uuid4()), "name": req.name, "host": req.host,
            "port": req.port,
            "control_mode": control_mode,
            "rcon_password": _enc(req.rcon_password) if req.rcon_password else None,
            "bridge_token_hash": _hash_secret(req.bridge_token) if req.bridge_token else None,
            "provider": req.provider or "custom",
            "region": req.region,
            "public_host": req.public_host or req.host,
            "game_port": req.game_port or req.port,
            "gotv_port": req.gotv_port,
            "join_password": _enc(req.join_password) if req.join_password else None,
            "gotv_password": _enc(req.gotv_password) if req.gotv_password else None,
            "panel_url": req.panel_url,
            "matchzy_enabled": req.matchzy_enabled,
            "cssimpleadmin_enabled": req.cssimpleadmin_enabled,
            "fake_rcon_enabled": req.fake_rcon_enabled,
            "hltv_enabled": req.hltv_enabled or bool(req.gotv_port),
            "notes": req.notes,
            "status": "unknown", "last_checked_at": None,
            "current_match_id": None, "current_tournament_id": None, "current_bracket_match_id": None, "current_duel_id": None,
            "last_match_id": None, "last_bridge_seen_at": None, "created_at": _now_iso(),
            "created_by": user["id"],
        }
        await db.cs2_servers.insert_one(srv)
        await journal("cs2_server_added", user["id"], {"server_id": srv["id"], "host": req.host, "port": req.port})
        return _public_server(srv)

    @router.patch("/servers/{sid}", dependencies=[Depends(get_admin_user)])
    async def update_server(sid: str, req: ServerPatchReq, user=Depends(get_admin_user)):
        srv = await _get_server(sid)
        updates = req.model_dump(exclude_unset=True)
        next_mode = str(updates.get("control_mode") or srv.get("control_mode") or "rcon").strip().lower()
        if "rcon_password" in updates:
            updates["rcon_password"] = _enc(updates["rcon_password"])
        if "join_password" in updates:
            updates["join_password"] = _enc(updates["join_password"]) if updates["join_password"] else None
        if "gotv_password" in updates:
            updates["gotv_password"] = _enc(updates["gotv_password"]) if updates["gotv_password"] else None
        if "bridge_token" in updates:
            updates["bridge_token_hash"] = _hash_secret(updates.pop("bridge_token"))
        if next_mode == "rcon" and not (updates.get("rcon_password") or srv.get("rcon_password")):
            raise HTTPException(400, "rcon_password requis pour un serveur en mode rcon")
        if next_mode == "bridge" and not (updates.get("bridge_token_hash") or srv.get("bridge_token_hash")):
            raise HTTPException(400, "bridge_token requis pour un serveur en mode bridge")
        if "host" in updates and "public_host" not in updates and not srv.get("public_host"):
            updates["public_host"] = updates["host"]
        if "port" in updates and "game_port" not in updates and not srv.get("game_port"):
            updates["game_port"] = updates["port"]
        if "gotv_port" in updates and "hltv_enabled" not in updates:
            updates["hltv_enabled"] = bool(updates["gotv_port"])
        if updates:
            await db.cs2_servers.update_one({"id": sid}, {"$set": updates})
        updated = await _get_server(sid)
        await journal("cs2_server_updated", user["id"], {"server_id": sid, "fields": sorted(updates.keys())})
        return _public_server(updated)

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
    async def ping_server(sid: str, user=Depends(get_admin_user)):
        srv = await _get_server(sid)
        result = await _run_server_command(
            srv,
            "status",
            kind="status_ping",
            created_by=user["id"],
        )
        await db.cs2_servers.update_one(
            {"id": sid},
            {"$set": {"status": "bridge_pending" if result["queued"] else "online", "last_checked_at": _now_iso()}},
        )
        return {
            "server_id": sid,
            "status": "queued" if result["queued"] else "online",
            "mode": result["mode"],
            "queued": result["queued"],
            "command_id": result.get("command_id"),
            "output": result["output"],
        }

    @router.post("/servers/{sid}/rcon", dependencies=[Depends(get_admin_user)])
    async def run_command(sid: str, req: RconCmd, user=Depends(get_admin_user)):
        srv = await _get_server(sid)
        result = await _run_server_command(
            srv,
            req.command,
            kind="console_command",
            created_by=user["id"],
        )
        await journal("cs2_rcon", user["id"], {"server_id": sid, "command": req.command})
        return {
            "server_id": sid,
            "command": req.command,
            "mode": result["mode"],
            "queued": result["queued"],
            "command_id": result.get("command_id"),
            "output": result["output"],
        }

    @router.post("/servers/{sid}/setup-match", dependencies=[Depends(get_admin_user)])
    async def setup_match(sid: str, req: MatchSetupReq, user=Depends(get_admin_user)):
        srv = await _get_server(sid)
        remote_log_outputs: list[dict[str, Any]] = []
        if req.raw_command:
            command = req.raw_command
        elif req.matchzy_url:
            remote_log_outputs = await _configure_matchzy_remote_log(
                srv,
                created_by=user["id"],
                metadata={"server_id": sid, "matchzy_url": req.matchzy_url},
            )
            command = _matchzy_load_url_command(req.matchzy_url, req.header_name, req.header_value)
        else:
            raise HTTPException(400, "Fournir matchzy_url ou raw_command")
        match_id = str(req.platform_match_id or uuid.uuid4())
        result = await _run_server_command(
            srv,
            command,
            kind="setup_match",
            metadata={
                "match_id": match_id,
                "tournament_id": req.tournament_id,
                "bracket_match_id": req.bracket_match_id,
            },
            created_by=user["id"],
        )
        await db.cs2_servers.update_one(
            {"id": sid},
            {"$set": {
                "current_match_id": match_id,
                "current_tournament_id": req.tournament_id,
                "current_bracket_match_id": req.bracket_match_id,
                "last_match_id": match_id,
                "status": "launch_pending" if result["queued"] else "live",
            }},
        )
        await journal("cs2_match_setup", user["id"], {"server_id": sid, "match_id": match_id, "command": command})
        return {
            "server_id": sid,
            "match_id": match_id,
            "command": command,
            "mode": result["mode"],
            "queued": result["queued"],
            "command_id": result.get("command_id"),
            "output": result["output"],
            "remote_log_configured": bool(remote_log_outputs),
            "remote_log_outputs": remote_log_outputs,
        }

    @router.post("/servers/{sid}/configure-matchzy-remote-log", dependencies=[Depends(get_admin_user)])
    async def configure_matchzy_remote_log(sid: str, user=Depends(get_admin_user)):
        srv = await _get_server(sid)
        webhook_url, auth_key, auth_value = _matchzy_remote_log_target()
        if not webhook_url or not auth_key or not auth_value:
            raise HTTPException(500, "BACKEND_PUBLIC_URL ou MATCHZY_WEBHOOK_SECRET manquant")
        outputs = await _configure_matchzy_remote_log(
            srv,
            created_by=user["id"],
            metadata={"server_id": sid, "webhook_url": webhook_url},
        )
        await journal(
            "cs2_matchzy_remote_log_configured",
            user["id"],
            {"server_id": sid, "webhook_url": webhook_url},
        )
        return {
            "ok": True,
            "server_id": sid,
            "webhook_url": webhook_url,
            "auth_header_key": auth_key,
            "applied_commands": len(outputs),
            "outputs": outputs,
        }

    @router.get("/tournaments/{tid}/bracket-matches/{match_id}/matchzy-config")
    async def get_matchzy_config(
        tid: str,
        match_id: str,
        authorization: Optional[str] = Header(default=None),
        x_matchzy_token: Optional[str] = Header(default=None),
    ):
        header_name, header_value = _matchzy_config_header()
        if header_value:
            expected_token = header_value.replace("Bearer ", "", 1)
            provided_token = (authorization or "").replace("Bearer ", "", 1) or (x_matchzy_token or "")
            if not hmac.compare_digest(provided_token, expected_token):
                raise HTTPException(401, "Config MatchZy non autorisee")
        doc = await db.matchzy_match_configs.find_one({"tournament_id": tid, "match_id": match_id}, {"_id": 0, "config": 1})
        if not doc:
            raise HTTPException(404, "Configuration MatchZy introuvable")
        return doc["config"]

    @router.post("/tournaments/{tid}/bracket-matches/{match_id}/launch", dependencies=[Depends(get_admin_user)])
    async def launch_bracket_match(
        tid: str,
        match_id: str,
        req: LaunchBracketMatchReq,
        user=Depends(get_admin_user),
    ):
        return await launch_bracket_match_on_server(
            db,
            journal,
            tid,
            match_id,
            req.server_id,
            created_by=user["id"],
            num_maps=req.num_maps,
            maplist=req.maplist,
            map_sides=req.map_sides,
            players_per_team=req.players_per_team,
            clinch_series=req.clinch_series,
            allow_incomplete_roster=req.allow_incomplete_roster,
            cvars=req.cvars,
        )

    @router.post("/bridge/heartbeat")
    async def bridge_heartbeat(req: BridgeHeartbeatReq, authorization: Optional[str] = Header(default=None)):
        srv = await _get_bridge_server(authorization)
        updates: dict[str, Any] = {
            "last_bridge_seen_at": _now_iso(),
        }
        if req.status:
            updates["status"] = req.status
        if req.current_map:
            updates["current_map"] = req.current_map
        if req.player_count is not None:
            updates["player_count"] = req.player_count
        if req.plugin_version:
            updates["bridge_plugin_version"] = req.plugin_version
        await db.cs2_servers.update_one({"id": srv["id"]}, {"$set": updates})
        pending_count = await db.cs2_bridge_commands.count_documents({"server_id": srv["id"], "status": "pending"})
        return {"ok": True, "server_id": srv["id"], "pending_commands": pending_count}

    @router.get("/bridge/pending")
    async def bridge_pending(limit: int = 10, authorization: Optional[str] = Header(default=None)):
        srv = await _get_bridge_server(authorization)
        stale_before = (datetime.now(timezone.utc) - timedelta(seconds=45)).isoformat()
        query = {
            "server_id": srv["id"],
            "$or": [
                {"status": "pending"},
                {"status": "dispatched", "dispatched_at": {"$lt": stale_before}},
            ],
        }
        docs = await db.cs2_bridge_commands.find(query, {"_id": 0}).sort("created_at", 1).to_list(min(limit, 25))
        payload: list[dict[str, Any]] = []
        for doc in docs:
            now_iso = _now_iso()
            await db.cs2_bridge_commands.update_one(
                {"id": doc["id"]},
                {"$set": {"status": "dispatched", "dispatched_at": now_iso}, "$inc": {"attempts": 1}},
            )
            payload.append({
                "id": doc["id"],
                "kind": doc["kind"],
                "command": doc["command"],
                "metadata": doc.get("metadata") or {},
                "created_at": doc["created_at"],
            })
        await db.cs2_servers.update_one({"id": srv["id"]}, {"$set": {"last_bridge_seen_at": _now_iso()}})
        return payload

    @router.post("/bridge/commands/{command_id}/result")
    async def bridge_command_result(
        command_id: str,
        req: BridgeCommandResultReq,
        authorization: Optional[str] = Header(default=None),
    ):
        srv = await _get_bridge_server(authorization)
        command = await db.cs2_bridge_commands.find_one({"id": command_id, "server_id": srv["id"]})
        if not command:
            raise HTTPException(404, "Commande bridge introuvable")
        await db.cs2_bridge_commands.update_one(
            {"id": command_id},
            {"$set": {"status": req.status, "output": req.output, "completed_at": _now_iso()}},
        )
        server_updates: dict[str, Any] = {"last_bridge_seen_at": _now_iso()}
        if command.get("kind") == "status_ping" and req.status == "completed":
            server_updates["status"] = "online"
            server_updates["last_checked_at"] = _now_iso()
        elif command.get("kind") in {"launch_bracket_match", "launch_duel_match", "launch_fun_match", "setup_match"}:
            server_updates["last_checked_at"] = _now_iso()
            if req.status == "completed":
                server_updates["status"] = "live"
            else:
                server_updates.update(
                    {
                        "status": "online",
                        "current_match_id": None,
                        "current_tournament_id": None,
                        "current_bracket_match_id": None,
                        "current_duel_id": None,
                        "current_fun_match_id": None,
                    }
                )
        await db.cs2_servers.update_one({"id": srv["id"]}, {"$set": server_updates})
        metadata = command.get("metadata") or {}
        if command.get("kind") == "launch_bracket_match":
            match_id = str(metadata.get("match_id") or "").strip()
            if match_id:
                await _attach_match_runtime_metadata(
                    db,
                    match_id,
                    {
                        "launch_status": "live" if req.status == "completed" else "failed",
                        "updated_at": _now_iso(),
                        "started_at": _now_iso() if req.status == "completed" else None,
                        "launch_error": None if req.status == "completed" else (req.output or "Bridge command failed"),
                    },
                )
        elif command.get("kind") == "launch_duel_match":
            duel_id = str(metadata.get("duel_id") or "").strip()
            if duel_id:
                duel_updates = {
                    "launch_status": "live" if req.status == "completed" else "failed",
                    "updated_at": _now_iso(),
                    "launch_error": None if req.status == "completed" else (req.output or "Bridge command failed"),
                }
                if req.status == "completed":
                    duel_updates["status"] = "live"
                    duel_updates["started_at"] = _now_iso()
                else:
                    duel_updates["status"] = "launch_failed"
                await db.duels.update_one({"id": duel_id, "status": {"$ne": "closed"}}, {"$set": duel_updates})
        elif command.get("kind") == "launch_fun_match":
            fun_match_id = str(metadata.get("fun_match_id") or "").strip()
            if fun_match_id:
                fun_updates = {
                    "launch_status": "live" if req.status == "completed" else "launch_failed",
                    "updated_at": _now_iso(),
                    "launch_error": None if req.status == "completed" else (req.output or "Bridge command failed"),
                }
                if req.status == "completed":
                    fun_updates["status"] = "live"
                    fun_updates["started_at"] = _now_iso()
                else:
                    fun_updates["status"] = "launch_failed"
                await db.fun_matches.update_one({"id": fun_match_id, "status": {"$ne": "closed"}}, {"$set": fun_updates})
        return {"ok": True, "command_id": command_id}

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
        auto_launched_matches: list[str] = []
        auto_launched_fun_matches: list[str] = []
        if payload.get("matchid") is not None:
            await _apply_matchzy_runtime_state(db, str(payload.get("matchid")), payload)
        if payload.get("event") == "series_end" and payload.get("matchid"):
            bracket_resolved = await _try_apply_matchzy_result(str(payload.get("matchid")), payload)
            if bracket_resolved:
                launched = await auto_launch_live_tournament_matches(db, journal)
                auto_launched_matches = [str(item.get("match_id")) for item in launched if item.get("match_id")]
            await _try_apply_duel_matchzy_result(str(payload.get("matchid")), payload)
            launched_fun = await auto_launch_ready_fun_matches(db, journal)
            auto_launched_fun_matches = [str(item.get("fun_match_id")) for item in launched_fun if item.get("fun_match_id")]
        return {
            "received": True,
            "id": event["id"],
            "auto_launched_matches": auto_launched_matches,
            "auto_launched_fun_matches": auto_launched_fun_matches,
        }

    @router.get("/events")
    async def list_events(limit: int = 50, matchid: Optional[str] = None):
        q = {}
        if matchid:
            q["matchid"] = matchid
        docs = await db.matchzy_events.find(q, {"_id": 0}).sort("received_at", -1).to_list(min(limit, 200))
        return docs

    return router
