import asyncio
import os
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017/readyup_arena_test")

import server
from server import TeamMemberAddReq, admin_add_team_member, admin_search_users


def _matches(doc, query):
    if not query:
        return True
    for key, expected in query.items():
        actual = doc.get(key)
        if isinstance(expected, dict):
            if "$ne" in expected and actual == expected["$ne"]:
                return False
            continue
        if actual != expected:
            return False
    return True


def _apply_update(doc, update):
    if "$set" in update:
        for key, value in update["$set"].items():
            doc[key] = value


class FakeCursor:
    def __init__(self, docs):
        self.docs = deepcopy(docs)

    async def to_list(self, limit):
        if limit is None:
            return deepcopy(self.docs)
        return deepcopy(self.docs[:limit])

    def sort(self, *args, **kwargs):
        return self


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = deepcopy(docs or [])

    def find(self, query=None, projection=None):
        rows = [doc for doc in self.docs if _matches(doc, query or {})]
        if projection:
            rows = [_project_doc(doc, projection) for doc in rows]
        return FakeCursor(rows)

    async def find_one(self, query=None, projection=None):
        for doc in self.docs:
            if _matches(doc, query or {}):
                if projection:
                    return deepcopy(_project_doc(doc, projection))
                return deepcopy(doc)
        return None

    async def update_one(self, query, update):
        for doc in self.docs:
            if _matches(doc, query or {}):
                _apply_update(doc, update)
                return

    async def update_many(self, query, update):
        for doc in self.docs:
            if _matches(doc, query or {}):
                _apply_update(doc, update)

    async def count_documents(self, query=None):
        return len([doc for doc in self.docs if _matches(doc, query or {})])


class FakeDB:
    def __init__(self, *, users=None, teams=None, players=None, team_applications=None):
        self.users = FakeCollection(users)
        self.teams = FakeCollection(teams)
        self.players = FakeCollection(players)
        self.team_applications = FakeCollection(team_applications)


def _project_doc(doc, projection):
    include_keys = [key for key, flag in projection.items() if key != "_id" and bool(flag)]
    exclude_keys = {key for key, flag in projection.items() if key != "_id" and not bool(flag)}
    if include_keys:
        return {key: doc.get(key) for key in include_keys if key in doc}
    return {key: value for key, value in doc.items() if key not in exclude_keys}


def _run(coro):
    return asyncio.run(coro)


async def _noop_journal(*args, **kwargs):
    return None


def test_admin_search_users_returns_only_available_matching_profiles():
    fake_db = FakeDB(
        users=[
            {"id": "u-free", "pseudo": "LoganPrime", "email": "logan@example.com", "steam_id": "7656", "steam_verified": True, "team_id": None},
            {"id": "u-busy", "pseudo": "LoganLocked", "email": "locked@example.com", "steam_id": "1234", "steam_verified": True, "team_id": "team-1"},
            {"id": "u-other", "pseudo": "NoMatch", "email": "nomatch@example.com", "steam_id": "9999", "steam_verified": False, "team_id": None},
        ]
    )
    original_db = server.db
    server.db = fake_db
    try:
        results = _run(admin_search_users(q="logan", limit=10, available_only=True))
    finally:
        server.db = original_db

    assert [item["id"] for item in results] == ["u-free"]
    assert results[0]["steam_verified"] is True


def test_admin_add_team_member_attaches_user_to_team_and_returns_updated_roster():
    fake_db = FakeDB(
        users=[
            {"id": "u-free", "pseudo": "FreshPlayer", "email": "fresh@example.com", "steam_id": "7656119", "steam_verified": True, "team_id": None, "team_role": None, "country": "FR"},
        ],
        teams=[
            {"id": "team-1", "name": "Ready Squad", "tag": "RSQ", "country": "FR", "logo_color": "#FF4600", "language": "FR", "recruitment_status": "open", "members_limit": 7, "captain_user_id": None, "captain_pseudo": None},
        ],
        players=[],
        team_applications=[],
    )
    original_db = server.db
    original_journal = server.journal
    server.db = fake_db
    server.journal = _noop_journal
    try:
        team = _run(
            admin_add_team_member(
                "team-1",
                TeamMemberAddReq(user_id="u-free", role="member"),
                admin={"id": "admin-1", "email": "admin@example.com"},
            )
        )
    finally:
        server.db = original_db
        server.journal = original_journal

    assert team["id"] == "team-1"
    assert team["members_count"] == 1
    assert team["members"][0]["id"] == "u-free"
    updated_user = _run(fake_db.users.find_one({"id": "u-free"}))
    assert updated_user["team_id"] == "team-1"
    assert updated_user["team_role"] == "member"
