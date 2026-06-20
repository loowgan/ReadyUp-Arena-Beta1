import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from fun_matches import FUN_MATCH_PLAYER_CAP, build_fun_match_teams, summarize_fun_match


def _player(index: int, elo: int) -> dict:
    return {
        "user_id": f"user-{index}",
        "pseudo": f"Player{index}",
        "elo": elo,
        "kdr": 1.0 + (index * 0.01),
        "reliability": 50 + index,
        "joined_at": f"2026-06-20T12:{index:02d}:00+00:00",
    }


def test_build_fun_match_teams_balances_ten_players_into_two_fives():
    players = [_player(index, 2000 - (index * 90)) for index in range(FUN_MATCH_PLAYER_CAP)]

    teams = build_fun_match_teams(players)

    assert len(teams) == 2
    assert all(team["members_count"] == 5 for team in teams)
    assigned_ids = {member["user_id"] for team in teams for member in team["members"]}
    assert len(assigned_ids) == FUN_MATCH_PLAYER_CAP
    assert abs(teams[0]["total_elo"] - teams[1]["total_elo"]) <= 200


def test_summarize_fun_match_marks_lobby_ready_when_full():
    players = [_player(index, 1500 - (index * 25)) for index in range(FUN_MATCH_PLAYER_CAP)]
    payload = summarize_fun_match({
        "id": "fun-1",
        "title": "Night Mix",
        "status": "open",
        "players": players,
    })

    assert payload["status"] == "ready"
    assert payload["ready_to_start"] is True
    assert payload["slots_remaining"] == 0
    assert len(payload["teams"]) == 2


def test_summarize_fun_match_keeps_open_state_when_incomplete():
    players = [_player(index, 1200 - (index * 10)) for index in range(6)]

    payload = summarize_fun_match({
        "id": "fun-2",
        "title": "Warmup",
        "status": "open",
        "players": players,
    })

    assert payload["status"] == "open"
    assert payload["ready_to_start"] is False
    assert payload["slots_remaining"] == 4
    assert payload["teams"] == []
