import asyncio
import os
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017/readyup_arena_test")

from server import _build_admin_overview


def _matches(doc, query):
    if not query:
        return True
    for key, expected in query.items():
        actual = doc.get(key)
        if isinstance(expected, dict):
            if "$in" in expected and actual not in expected["$in"]:
                return False
            if "$gt" in expected and not (actual is not None and actual > expected["$gt"]):
                return False
            continue
        if actual != expected:
            return False
    return True


class FakeCursor:
    def __init__(self, docs):
        self.docs = deepcopy(docs)

    async def to_list(self, limit):
        if limit is None:
            return deepcopy(self.docs)
        return deepcopy(self.docs[:limit])


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = deepcopy(docs or [])

    def find(self, query=None, projection=None):
        return FakeCursor([doc for doc in self.docs if _matches(doc, query or {})])

    async def count_documents(self, query=None):
        return len([doc for doc in self.docs if _matches(doc, query or {})])


class FakeDB:
    def __init__(self, **collections):
        self.cards = FakeCollection(collections.get("cards"))
        self.match_reports = FakeCollection(collections.get("match_reports"))
        self.tournaments = FakeCollection(collections.get("tournaments"))
        self.fun_matches = FakeCollection(collections.get("fun_matches"))
        self.announcements = FakeCollection(collections.get("announcements"))
        self.contests = FakeCollection(collections.get("contests"))
        self.rewards = FakeCollection(collections.get("rewards"))
        self.reward_redemptions = FakeCollection(collections.get("reward_redemptions"))
        self.news = FakeCollection(collections.get("news"))
        self.users = FakeCollection(collections.get("users"))
        self.teams = FakeCollection(collections.get("teams"))
        self.duels = FakeCollection(collections.get("duels"))


def _run(coro):
    return asyncio.run(coro)


def test_build_admin_overview_groups_content_moderation_and_competition():
    db = FakeDB(
        cards=[
            {"id": "c1", "status": "active", "severity": "yellow"},
            {"id": "c2", "status": "active", "severity": "red"},
            {"id": "c3", "status": "revoked", "severity": "yellow"},
        ],
        match_reports=[
            {"id": "r1", "status": "open", "source": "cs2_chat"},
            {"id": "r2", "status": "acknowledged", "source": "manual"},
            {"id": "r3", "status": "resolved", "source": "cs2_chat"},
        ],
        tournaments=[
            {"id": "t1", "status": "live"},
            {"id": "t2", "status": "registering"},
            {"id": "t3", "status": "closed"},
        ],
        fun_matches=[
            {"id": "f1", "status": "open"},
            {"id": "f2", "status": "ready"},
            {"id": "f3", "status": "waiting_server"},
            {"id": "f4", "status": "live"},
        ],
        announcements=[
            {"id": "a1", "is_active": True, "starts_at": "2026-06-20T10:00:00+00:00", "ends_at": "2026-06-25T10:00:00+00:00"},
            {"id": "a2", "is_active": False, "starts_at": "2026-06-20T10:00:00+00:00", "ends_at": "2026-06-25T10:00:00+00:00"},
        ],
        contests=[
            {"id": "co1", "is_active": True, "starts_at": "2026-06-21T10:00:00+00:00", "ends_at": "2026-06-23T10:00:00+00:00"},
            {"id": "co2", "is_active": True, "starts_at": "2026-06-24T10:00:00+00:00", "ends_at": "2026-06-30T10:00:00+00:00"},
        ],
        rewards=[
            {"id": "rw1", "is_active": True},
            {"id": "rw2", "is_active": False},
        ],
        reward_redemptions=[
            {"id": "rd1", "status": "pending"},
            {"id": "rd2", "status": "delivered"},
        ],
        news=[
            {"id": "n1", "date": "2026-06-20T10:00:00+00:00"},
            {"id": "n2", "date": "2026-06-24T10:00:00+00:00"},
        ],
        users=[{"id": "u1"}, {"id": "u2"}, {"id": "u3"}],
        teams=[{"id": "tm1"}, {"id": "tm2"}],
        duels=[
            {"id": "d1", "status": "live"},
            {"id": "d2", "status": "ready"},
            {"id": "d3", "status": "closed"},
        ],
    )

    overview = _run(_build_admin_overview(db, now_iso="2026-06-22T12:00:00+00:00"))

    assert overview["moderation"] == {
        "cards_active": 2,
        "cards_yellow": 1,
        "cards_red": 1,
        "reports_open": 1,
        "reports_acknowledged": 1,
        "reports_from_cs2": 1,
    }
    assert overview["content"] == {
        "news_total": 2,
        "news_scheduled": 1,
        "news_published": 1,
        "announcements_total": 2,
        "announcements_live": 1,
        "contests_total": 2,
        "contests_live": 1,
    }
    assert overview["community"] == {
        "users_total": 3,
        "teams_total": 2,
    }
    assert overview["store"] == {
        "rewards_total": 2,
        "rewards_active": 1,
        "redemptions_pending": 1,
    }
    assert overview["competition"] == {
        "tournaments_active": 2,
        "tournaments_live": 1,
        "duels_active": 2,
        "fun_matches_open": 1,
        "fun_matches_ready": 1,
        "fun_matches_waiting_server": 1,
        "fun_matches_live": 1,
    }
    assert overview["generated_at"] == "2026-06-22T12:00:00+00:00"
