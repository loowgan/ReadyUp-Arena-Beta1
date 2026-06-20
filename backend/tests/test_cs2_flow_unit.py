import asyncio
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from bracket import apply_manual_bracket_result, generate_single
from cs2 import (
    _apply_matchzy_runtime_state,
    apply_matchzy_bracket_result,
    apply_matchzy_duel_result,
    build_live_matches_snapshot,
    extract_matchzy_winner_team,
    public_server_payload,
)


class FakeResult:
    def __init__(self, *, modified_count: int = 0, deleted_count: int = 0, matched_count: int | None = None):
        self.modified_count = modified_count
        self.deleted_count = deleted_count
        self.matched_count = modified_count if matched_count is None else matched_count


def _matches(doc, query):
    if not query:
        return True
    if "$or" in query:
        return any(_matches(doc, item) for item in query["$or"])
    for key, expected in query.items():
        if key == "$or":
            continue
        actual = doc.get(key)
        if isinstance(expected, dict):
            if "$ne" in expected and actual == expected["$ne"]:
                return False
            if "$in" in expected and actual not in expected["$in"]:
                return False
            continue
        if actual != expected:
            return False
    return True


def _apply_update(doc, update):
    if "$set" in update:
        for key, value in update["$set"].items():
            doc[key] = value
    if "$inc" in update:
        for key, value in update["$inc"].items():
            doc[key] = int(doc.get(key, 0) or 0) + int(value)


class FakeCursor:
    def __init__(self, docs):
        self.docs = docs

    def sort(self, field, direction):
        reverse = int(direction) < 0
        self.docs = sorted(self.docs, key=lambda item: item.get(field) or "", reverse=reverse)
        return self

    async def to_list(self, limit):
        if limit is None:
            return deepcopy(self.docs)
        return deepcopy(self.docs[:limit])


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = deepcopy(docs or [])

    async def find_one(self, query=None, projection=None):
        for doc in self.docs:
            if _matches(doc, query or {}):
                return deepcopy(doc)
        return None

    def find(self, query=None, projection=None):
        return FakeCursor([deepcopy(doc) for doc in self.docs if _matches(doc, query or {})])

    async def replace_one(self, query, replacement, upsert=False):
        for index, doc in enumerate(self.docs):
            if _matches(doc, query or {}):
                self.docs[index] = deepcopy(replacement)
                return FakeResult(modified_count=1)
        if upsert:
            self.docs.append(deepcopy(replacement))
            return FakeResult(modified_count=1)
        return FakeResult(modified_count=0)

    async def update_one(self, query, update):
        for doc in self.docs:
            if _matches(doc, query or {}):
                _apply_update(doc, update)
                return FakeResult(modified_count=1)
        return FakeResult(modified_count=0)

    async def update_many(self, query, update):
        modified = 0
        for doc in self.docs:
            if _matches(doc, query or {}):
                _apply_update(doc, update)
                modified += 1
        return FakeResult(modified_count=modified)

    async def insert_one(self, doc):
        self.docs.append(deepcopy(doc))
        return FakeResult(modified_count=1)


class FakeDB:
    def __init__(self, **collections):
        self.brackets = FakeCollection(collections.get("brackets"))
        self.duels = FakeCollection(collections.get("duels"))
        self.users = FakeCollection(collections.get("users"))
        self.matchzy_events = FakeCollection(collections.get("matchzy_events"))
        self.cs2_servers = FakeCollection(collections.get("cs2_servers"))
        self.matchzy_match_configs = FakeCollection(collections.get("matchzy_match_configs"))
        self.duel_match_configs = FakeCollection(collections.get("duel_match_configs"))
        self.tournament_registrations = FakeCollection(collections.get("tournament_registrations"))
        self.teams = FakeCollection(collections.get("teams"))


def _run(coro):
    return asyncio.run(coro)


def test_extract_matchzy_winner_team_handles_string_and_object_payloads():
    assert extract_matchzy_winner_team({"winner": "team1"}) == "team1"
    assert extract_matchzy_winner_team({"winner": {"team": "team2"}}) == "team2"
    assert extract_matchzy_winner_team({"winner_team": "team1"}) == "team1"
    assert extract_matchzy_winner_team({"winner": "Alpha"}) is None


def test_apply_matchzy_bracket_result_closes_match_from_string_winner():
    bracket = generate_single(
        [
            {"id": "team-alpha", "name": "Alpha"},
            {"id": "team-beta", "name": "Beta"},
        ]
    )
    bracket["tournament_id"] = "tr-test"
    bracket["version"] = 1
    match_id = bracket["matches"]["W"][0]["id"]
    db = FakeDB(brackets=[bracket])
    journal_calls = []

    async def journal(event_type, user_id, meta):
        journal_calls.append((event_type, user_id, meta))

    ok = _run(
        apply_matchzy_bracket_result(
            db,
            journal,
            match_id,
            {"event": "series_end", "winner": "team1", "team1_series_score": 1, "team2_series_score": 0},
        )
    )

    assert ok is True
    saved = _run(db.brackets.find_one({"tournament_id": "tr-test"}))
    resolved = saved["matches"]["W"][0]
    assert resolved["winner_id"] == "team-alpha"
    assert resolved["launch_status"] == "finished"
    assert resolved["series_score"] == {"team1": 1, "team2": 0}
    assert saved["champion_id"] == "team-alpha"
    assert journal_calls and journal_calls[0][0] == "bracket_result_auto"


def test_apply_matchzy_duel_result_closes_duel_and_credits_winner():
    db = FakeDB(
        duels=[
            {
                "id": "duel-1",
                "creator_id": "u1",
                "creator_pseudo": "Alpha",
                "opponent_id": "u2",
                "opponent_pseudo": "Beta",
                "stake": 150,
                "status": "live",
            }
        ],
        users=[
            {"id": "u1", "tokens": 100},
            {"id": "u2", "tokens": 50},
        ],
    )
    journal_calls = []

    async def journal(event_type, user_id, meta):
        journal_calls.append((event_type, user_id, meta))

    ok = _run(
        apply_matchzy_duel_result(
            db,
            journal,
            "duel-1",
            {"event": "series_end", "winner": {"team": "team2"}, "team1": {"score": 10}, "team2": {"score": 13}},
        )
    )

    assert ok is True
    duel = _run(db.duels.find_one({"id": "duel-1"}))
    winner = _run(db.users.find_one({"id": "u2"}))
    assert duel["status"] == "closed"
    assert duel["winner_id"] == "u2"
    assert duel["series_score"] == {"team1": 10, "team2": 13}
    assert winner["tokens"] == 350
    assert journal_calls and journal_calls[0][0] == "duel_result_auto"


def test_live_matches_snapshot_includes_active_server_without_matchzy_events():
    db = FakeDB(
        cs2_servers=[
            {
                "id": "srv-1",
                "name": "Arena #1",
                "host": "185.245.99.120",
                "public_host": "185.245.99.120",
                "port": 30060,
                "game_port": 30060,
                "gotv_port": 35017,
                "join_password": None,
                "gotv_password": None,
                "status": "launch_pending",
                "current_match_id": "match-prelive",
                "last_match_id": "match-prelive",
                "last_checked_at": "2026-06-20T18:00:00+00:00",
            }
        ],
        matchzy_match_configs=[
            {
                "match_id": "match-prelive",
                "config": {
                    "team1": {"name": "Alpha"},
                    "team2": {"name": "Beta"},
                    "maplist": ["de_nuke"],
                },
            }
        ],
    )

    live = _run(build_live_matches_snapshot(db))

    assert len(live) == 1
    match_row = live[0]
    assert match_row["matchid"] == "match-prelive"
    assert match_row["team1_name"] == "Alpha"
    assert match_row["team2_name"] == "Beta"
    assert match_row["server"] == "Arena #1"
    assert match_row["launch_status"] == "launch_pending"
    assert match_row["source"] == "server_state"
    assert "steam://rungameid/730//" in match_row["connect_url"]


def test_public_server_payload_hides_private_password_links():
    payload = public_server_payload(
        {
            "id": "srv-private",
            "name": "Arena Private",
            "host": "185.245.99.120",
            "public_host": "185.245.99.120",
            "port": 30060,
            "game_port": 30060,
            "gotv_port": 35017,
            "join_password": "pracc",
            "gotv_password": "club21",
            "bridge_token_hash": "secret",
            "rcon_password": "secret-rcon",
        }
    )

    assert "join_password" not in payload
    assert "gotv_password" not in payload
    assert "bridge_token_hash" not in payload
    assert payload["join_password_required"] is True
    assert payload["spectator_password_required"] is True
    assert payload["connect_url"] is None
    assert payload["hltv_url"] is None


def test_live_matches_snapshot_keeps_private_links_out_of_public_payload():
    db = FakeDB(
        cs2_servers=[
            {
                "id": "srv-private",
                "name": "Arena Private",
                "host": "185.245.99.120",
                "public_host": "185.245.99.120",
                "port": 30060,
                "game_port": 30060,
                "gotv_port": 35017,
                "join_password": "pracc",
                "gotv_password": "club21",
                "status": "live",
                "current_match_id": "match-private",
                "last_match_id": "match-private",
                "last_checked_at": "2026-06-20T18:10:00+00:00",
            }
        ],
        matchzy_match_configs=[
            {
                "match_id": "match-private",
                "config": {
                    "team1": {"name": "Alpha"},
                    "team2": {"name": "Beta"},
                    "maplist": ["de_mirage"],
                },
            }
        ],
    )

    live = _run(build_live_matches_snapshot(db))

    assert len(live) == 1
    match_row = live[0]
    assert match_row["connect_url"] is None
    assert match_row["spectator_url"] is None
    assert match_row["join_password_required"] is True
    assert match_row["spectator_password_required"] is True


def test_apply_matchzy_runtime_state_updates_server_and_duel_lifecycle():
    db = FakeDB(
        cs2_servers=[
            {
                "id": "srv-1",
                "name": "Arena #1",
                "status": "launch_pending",
                "current_match_id": "duel-rt",
                "last_match_id": "duel-rt",
                "current_duel_id": "duel-rt",
            }
        ],
        duels=[
            {
                "id": "duel-rt",
                "status": "launch_pending",
                "launch_status": "allocating_server",
            }
        ],
    )

    _run(_apply_matchzy_runtime_state(db, "duel-rt", {"event": "series_start", "matchid": "duel-rt", "map_name": "de_nuke"}))
    server_live = _run(db.cs2_servers.find_one({"id": "srv-1"}))
    duel_live = _run(db.duels.find_one({"id": "duel-rt"}))

    assert server_live["status"] == "live"
    assert server_live["current_match_id"] == "duel-rt"
    assert server_live["current_map"] == "de_nuke"
    assert duel_live["status"] == "live"
    assert duel_live["launch_status"] == "live"
    assert duel_live["current_map"] == "de_nuke"
    assert duel_live["started_at"]

    _run(_apply_matchzy_runtime_state(db, "duel-rt", {"event": "series_end", "matchid": "duel-rt", "team1": {"score": 13}, "team2": {"score": 11}}))
    server_done = _run(db.cs2_servers.find_one({"id": "srv-1"}))
    duel_done = _run(db.duels.find_one({"id": "duel-rt"}))

    assert server_done["status"] == "online"
    assert server_done["current_match_id"] is None
    assert duel_done["launch_status"] == "finished"
    assert duel_done["series_score"] == {"team1": 13, "team2": 11}


def test_apply_manual_bracket_result_releases_server_and_marks_match_finished():
    bracket = generate_single(
        [
            {"id": "team-alpha", "name": "Alpha"},
            {"id": "team-beta", "name": "Beta"},
        ]
    )
    bracket["tournament_id"] = "tr-live"
    bracket["version"] = 4
    match_id = bracket["matches"]["W"][0]["id"]
    db = FakeDB(
        brackets=[bracket],
        cs2_servers=[
            {
                "id": "srv-1",
                "name": "Arena #1",
                "status": "live",
                "current_match_id": match_id,
                "current_tournament_id": "tr-live",
                "current_bracket_match_id": match_id,
            }
        ],
    )
    journal_calls = []

    async def journal(event_type, user_id, meta):
        journal_calls.append((event_type, user_id, meta))

    updated = _run(
        apply_manual_bracket_result(
            db,
            journal,
            "tr-live",
            match_id,
            "team-alpha",
            expected_version=4,
            actor_user_id="admin-1",
        )
    )

    resolved = updated["matches"]["W"][0]
    server = _run(db.cs2_servers.find_one({"id": "srv-1"}))

    assert resolved["winner_id"] == "team-alpha"
    assert resolved["result_source"] == "manual_report"
    assert resolved["launch_status"] == "finished"
    assert resolved["last_event"] == "manual_result"
    assert updated["version"] == 5
    assert server["status"] == "online"
    assert server["current_match_id"] is None
    assert server["current_bracket_match_id"] is None
    assert server["last_match_id"] == match_id
    assert journal_calls and journal_calls[0][0] == "bracket_result"
