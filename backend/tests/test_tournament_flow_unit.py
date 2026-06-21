import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from tournament_flow import (  # noqa: E402
    AUTO_TEAM_SIZE,
    build_auto_solo_teams,
    filter_solo_registrations_for_user_ids,
    summarize_tournament_registrations_from_regs,
)


def _solo_reg(index: int, user_id: str | None = None) -> dict:
    return {
        "id": f"solo-{index}",
        "entity_type": "solo",
        "user_id": user_id or f"user-{index}",
        "entity_name": f"Solo {index}",
    }


def _team_reg(index: int) -> dict:
    return {
        "id": f"team-{index}",
        "entity_type": "team",
        "entity_id": f"team-{index}",
        "entity_name": f"Team {index}",
    }


def test_summarize_tournament_registrations_keeps_solo_capacity_independent_from_team_slots():
    regs = [_solo_reg(index) for index in range(8)]

    summary = summarize_tournament_registrations_from_regs(8, regs)

    assert summary["manual_teams_count"] == 0
    assert summary["registered_effective"] == 0
    assert summary["team_slots_remaining"] == 8
    assert summary["solo_slots_remaining"] == 32
    assert summary["solo_waiting_count"] == 8


def test_summarize_tournament_registrations_builds_two_auto_teams_from_ten_solos():
    regs = [_solo_reg(index) for index in range(10)]

    summary = summarize_tournament_registrations_from_regs(8, regs)

    assert summary["auto_generated_teams_count"] == 2
    assert summary["registered_effective"] == 2
    assert summary["team_slots_remaining"] == 6
    assert summary["solo_waiting_count"] == 0


def test_filter_solo_registrations_for_user_ids_only_removes_targeted_entries():
    regs = [
        _solo_reg(1, "u-1"),
        _team_reg(1),
        _solo_reg(2, "u-2"),
        _solo_reg(3, "u-3"),
    ]

    filtered = filter_solo_registrations_for_user_ids(regs, ["u-2", "u-9"])

    assert [reg["id"] for reg in filtered] == ["solo-1", "team-1", "solo-3"]


def test_build_auto_solo_teams_returns_full_fives_only():
    solo_entries = [
        {
            "id": f"user-{index}",
            "pseudo": f"Player{index}",
            "country": "FR",
            "level": 5,
            "elo": 1200 + index,
            "reliability": 60,
        }
        for index in range((AUTO_TEAM_SIZE * 2) + 3)
    ]

    teams, remaining = build_auto_solo_teams(solo_entries, slots_remaining=4)

    assert len(teams) == 2
    assert all(team["members_count"] == AUTO_TEAM_SIZE for team in teams)
    assert len(remaining) == 3
