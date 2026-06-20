from __future__ import annotations

from copy import deepcopy
from typing import Any

FUN_MATCH_TEAM_SIZE = 5
FUN_MATCH_PLAYER_CAP = FUN_MATCH_TEAM_SIZE * 2
FUN_MATCH_TEAM_DEFS = (
    {"id": "alpha", "name": "Neon Five", "accent_color": "#00F0FF"},
    {"id": "bravo", "name": "Strike Five", "accent_color": "#FF4600"},
)


def _safe_number(value: Any, default: float = 0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _sort_key(player: dict[str, Any]) -> tuple[float, float, str]:
    return (
        -_safe_number(player.get("elo"), 1000),
        -_safe_number(player.get("reliability"), 50),
        str(player.get("joined_at") or ""),
    )


def build_fun_match_teams(players: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(players) < FUN_MATCH_PLAYER_CAP:
        return []

    teams = [
        {
            **team_def,
            "members": [],
            "members_count": 0,
            "total_elo": 0,
            "avg_elo": 0,
            "avg_kdr": None,
        }
        for team_def in FUN_MATCH_TEAM_DEFS
    ]
    ordered = sorted((deepcopy(player) for player in players[:FUN_MATCH_PLAYER_CAP]), key=_sort_key)

    for player in ordered:
        candidates = [team for team in teams if len(team["members"]) < FUN_MATCH_TEAM_SIZE]
        candidates.sort(key=lambda team: (len(team["members"]), team["total_elo"]))
        target = candidates[0]
        target["members"].append(player)
        target["total_elo"] += round(_safe_number(player.get("elo"), 1000))

    for team in teams:
        team["members_count"] = len(team["members"])
        if team["members"]:
            team["avg_elo"] = round(team["total_elo"] / len(team["members"]))
            kdr_values = [
                _safe_number(member.get("kdr"))
                for member in team["members"]
                if member.get("kdr") not in (None, "")
            ]
            team["avg_kdr"] = round(sum(kdr_values) / len(kdr_values), 2) if kdr_values else None

    return teams


def summarize_fun_match(doc: dict[str, Any]) -> dict[str, Any]:
    players = deepcopy(list(doc.get("players") or []))
    players_count = len(players)
    teams = build_fun_match_teams(players)
    status = str(doc.get("status") or "open")
    if status == "open" and players_count >= FUN_MATCH_PLAYER_CAP:
        status = "ready"
    return {
        **deepcopy(doc),
        "format": "5v5",
        "team_size": FUN_MATCH_TEAM_SIZE,
        "player_cap": FUN_MATCH_PLAYER_CAP,
        "players": players,
        "players_count": players_count,
        "slots_remaining": max(FUN_MATCH_PLAYER_CAP - players_count, 0),
        "ready_to_start": players_count >= FUN_MATCH_PLAYER_CAP,
        "teams": teams,
        "status": status,
    }
