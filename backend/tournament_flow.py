AUTO_TEAM_SIZE = 5
AUTO_TEAM_MIN_TEAMS = 2
AUTO_TEAM_COLORS = ["#FF4600", "#00F0FF", "#FF003C", "#10B981", "#8B5CF6", "#FFB800"]


def auto_solo_team_count(solo_count: int, slots_remaining: int) -> int:
    if slots_remaining <= 0:
        return 0
    possible_teams = min(max(int(solo_count or 0), 0) // AUTO_TEAM_SIZE, slots_remaining)
    return possible_teams if possible_teams >= AUTO_TEAM_MIN_TEAMS else 0


def summarize_tournament_registration_counts(capacity: int, manual_team_count: int, solo_count: int) -> dict:
    manual_team_count = max(int(manual_team_count or 0), 0)
    solo_count = max(int(solo_count or 0), 0)
    capacity = max(int(capacity or 0), 0)
    slots_remaining_from_manual = max(capacity - manual_team_count, 0)
    auto_generated_teams_count = auto_solo_team_count(solo_count, slots_remaining_from_manual)
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


def summarize_tournament_registrations_from_regs(capacity: int, registrations: list[dict]) -> dict:
    regs = list(registrations or [])
    manual_team_count = sum(1 for reg in regs if reg.get("entity_type") == "team")
    solo_count = len(regs) - manual_team_count
    return {
        **summarize_tournament_registration_counts(capacity, manual_team_count, solo_count),
        "registrations_count": len(regs),
    }


def filter_solo_registrations_for_user_ids(registrations: list[dict], user_ids: list[str]) -> list[dict]:
    blocked_ids = {str(user_id) for user_id in (user_ids or []) if user_id}
    if not blocked_ids:
        return list(registrations or [])
    return [
        reg
        for reg in (registrations or [])
        if not (reg.get("entity_type") == "solo" and str(reg.get("user_id") or "") in blocked_ids)
    ]


def build_auto_solo_teams(solo_entries: list[dict], slots_remaining: int) -> tuple[list[dict], list[dict]]:
    auto_team_count = auto_solo_team_count(len(solo_entries), slots_remaining)
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
        color = AUTO_TEAM_COLORS[index % len(AUTO_TEAM_COLORS)]
        teams.append({
            "id": f"auto-solo-{index + 1}",
            "name": f"Escouade solo {index + 1}",
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
