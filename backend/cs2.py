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

from fastapi import APIRouter, HTTPException, Depends, Request, Header
from pydantic import BaseModel, Field
from cryptography.fernet import Fernet

from rcon.source import Client as RconClient
from bracket import report_match

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


def _optional_steam_connect(host: Optional[str], port: Optional[int]) -> Optional[str]:
    if not host or not port:
        return None
    return f"steam://connect/{host}:{int(port)}"


def _private_steam_connect(host: Optional[str], port: Optional[int], password: Optional[str] = None) -> Optional[str]:
    if not host or not port:
        return None
    connect = f"steam://connect/{host}:{int(port)}"
    secret = (password or "").strip()
    return f"{connect}/{secret}" if secret else connect


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
    clean["provider"] = clean.get("provider") or "custom"
    clean["control_mode"] = _server_control_mode(doc)
    clean["public_host"] = public_host
    clean["game_port"] = int(game_port) if game_port else None
    clean["gotv_port"] = int(gotv_port) if gotv_port else None
    clean["connect_url"] = _optional_steam_connect(public_host, clean.get("game_port"))
    clean["hltv_url"] = _optional_steam_connect(public_host, clean.get("gotv_port"))
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
        winner_team = str((payload.get("winner") or {}).get("team") or "").strip().lower()
        if winner_team not in {"team1", "team2"}:
            return False
        raw = await db.brackets.find_one(
            {"$or": [{"matches.W.id": str(match_id)}, {"matches.L.id": str(match_id)}, {"matches.GF.id": str(match_id)}]}
        )
        if not raw:
            candidates = await db.brackets.find({}, {"_id": 0}).to_list(200)
            raw = next((doc for doc in candidates if _find_bracket_match(doc, str(match_id))), None)
        if not raw:
            return False
        bracket_doc = {k: v for k, v in raw.items() if k != "_id"}
        match_doc = _find_bracket_match(bracket_doc, str(match_id))
        if not match_doc or match_doc.get("winner_id") or not match_doc.get("a") or not match_doc.get("b"):
            return False
        winner_id = match_doc["a"]["id"] if winner_team == "team1" else match_doc["b"]["id"]
        report_match(bracket_doc, str(match_id), str(winner_id))
        resolved_match = _find_bracket_match(bracket_doc, str(match_id))
        if resolved_match:
            resolved_match["result_source"] = "matchzy_webhook"
            resolved_match["result_received_at"] = _now_iso()
            resolved_match["launch_status"] = "finished"
            resolved_match["series_score"] = {
                "team1": payload.get("team1_series_score"),
                "team2": payload.get("team2_series_score"),
            }
        current_version = int(raw.get("version", 0) or 0)
        bracket_doc["version"] = current_version + 1
        await db.brackets.replace_one({"tournament_id": raw["tournament_id"]}, bracket_doc, upsert=False)
        await journal(
            "bracket_result_auto",
            None,
            {"tournament_id": raw["tournament_id"], "match_id": str(match_id), "winner_team": winner_team, "winner_id": str(winner_id)},
        )
        return True

    async def _try_apply_duel_matchzy_result(match_id: str, payload: dict[str, Any]) -> bool:
        winner_team = str((payload.get("winner") or {}).get("team") or "").strip().lower()
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
                "series_score": {
                    "team1": payload.get("team1_series_score"),
                    "team2": payload.get("team2_series_score"),
                },
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
        srv = await _get_server(req.server_id)
        if srv.get("status") == "live" and srv.get("current_match_id") and str(srv.get("current_match_id")) != str(match_id):
            raise HTTPException(409, f"Le serveur {srv.get('name')} heberge deja le match {srv.get('current_match_id')}")

        public_base = _backend_public_base()
        if not public_base:
            raise HTTPException(500, "BACKEND_PUBLIC_URL manquant pour generer l'URL MatchZy")

        tournament, _bracket_doc, stored = await _build_matchzy_config(tid, match_id, req.server_id, req)
        config_url = f"{public_base}/api/cs2/tournaments/{tid}/bracket-matches/{match_id}/matchzy-config"
        header_name, header_value = _matchzy_config_header()
        remote_log_outputs = await _configure_matchzy_remote_log(
            srv,
            created_by=user["id"],
            metadata={"tournament_id": tid, "match_id": match_id, "config_url": config_url},
        )
        command = _matchzy_load_url_command(config_url, header_name, header_value)
        result = await _run_server_command(
            srv,
            command,
            kind="launch_bracket_match",
            metadata={"tournament_id": tid, "match_id": match_id, "config_url": config_url},
            created_by=user["id"],
        )

        await db.cs2_servers.update_one(
            {"id": req.server_id},
            {"$set": {
                "current_match_id": str(match_id),
                "current_tournament_id": str(tid),
                "current_bracket_match_id": str(match_id),
                "last_match_id": str(match_id),
                "status": "launch_pending" if result["queued"] else "live",
                "last_checked_at": _now_iso(),
            }},
        )
        await _attach_bracket_match_metadata(
            tid,
            match_id,
            {
                "server_id": req.server_id,
                "server_name": srv.get("name"),
                "server_host": srv.get("public_host") or srv.get("host"),
                "server_game_port": srv.get("game_port") or srv.get("port"),
                "matchzy_config_url": config_url,
                "launch_status": "queued" if result["queued"] else "live",
                "launched_at": _now_iso(),
                "num_maps": req.num_maps,
                "players_per_team": req.players_per_team,
            },
        )
        await journal(
            "cs2_bracket_match_launched",
            user["id"],
            {"tournament_id": tid, "match_id": match_id, "server_id": req.server_id, "server_name": srv.get("name")},
        )
        return {
            "ok": True,
            "tournament_id": tid,
            "match_id": match_id,
            "server_id": req.server_id,
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
        await db.cs2_servers.update_one({"id": srv["id"]}, {"$set": server_updates})
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
        # Reflect terminal series state on the bound server, if any
        if payload.get("event") == "series_end" and payload.get("matchid"):
            await db.cs2_servers.update_one(
                {"current_match_id": str(payload.get("matchid"))},
                {"$set": {
                    "status": "online",
                    "last_match_id": str(payload.get("matchid")),
                    "current_match_id": None,
                    "current_tournament_id": None,
                    "current_bracket_match_id": None,
                    "current_duel_id": None,
                }},
            )
        if payload.get("event") == "series_end" and payload.get("matchid"):
            await _try_apply_matchzy_result(str(payload.get("matchid")), payload)
            await _try_apply_duel_matchzy_result(str(payload.get("matchid")), payload)
        return {"received": True, "id": event["id"]}

    @router.get("/events")
    async def list_events(limit: int = 50, matchid: Optional[str] = None):
        q = {}
        if matchid:
            q["matchid"] = matchid
        docs = await db.matchzy_events.find(q, {"_id": 0}).sort("received_at", -1).to_list(min(limit, 200))
        return docs

    return router
