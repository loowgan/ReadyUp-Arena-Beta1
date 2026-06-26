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
from server import CountdownStartReq, admin_cancel_tournament_countdown, admin_start_tournament_countdown


def _matches(doc, query):
    if not query:
        return True
    for key, expected in query.items():
        if doc.get(key) != expected:
            return False
    return True


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = deepcopy(docs or [])

    async def find_one(self, query=None, projection=None):
        for doc in self.docs:
            if _matches(doc, query or {}):
                if projection:
                    include = [key for key, flag in projection.items() if key != "_id" and bool(flag)]
                    if include:
                        return {key: doc.get(key) for key in include if key in doc}
                return deepcopy(doc)
        return None


class FakeDB:
    def __init__(self, *, tournaments=None):
        self.tournaments = FakeCollection(tournaments)


class FakeRedisState:
    def __init__(self, countdown=None):
        self.countdown = countdown
        self.deleted = False
        self.released = False

    async def get_countdown(self, tid):
        return deepcopy(self.countdown)

    async def del_countdown(self, tid):
        self.deleted = True
        self.countdown = None

    async def release_cd_lock(self, tid):
        self.released = True


class FakeHub:
    def __init__(self):
        self.events = []

    async def broadcast(self, tid, payload):
        self.events.append((tid, deepcopy(payload)))


def _run(coro):
    return asyncio.run(coro)


async def _noop(*args, **kwargs):
    return None


def test_admin_start_tournament_countdown_returns_started_payload_and_broadcasts():
    fake_db = FakeDB(tournaments=[{"id": "tr1", "name": "Beta Cup", "status": "registering"}])
    fake_hub = FakeHub()
    called = {}

    async def _fake_ensure(tournament_doc):
        called["ensured"] = tournament_doc["id"]
        return {"registered_effective": 2}

    async def _fake_start(tid, seconds, started_by):
        called["start"] = (tid, seconds, started_by)
        return True

    original_db = server.db
    original_hub = server.hub
    original_journal = server.journal
    original_ensure = server._ensure_tournament_can_start
    original_start = server.start_countdown
    server.db = fake_db
    server.hub = fake_hub
    server.journal = _noop
    server._ensure_tournament_can_start = _fake_ensure
    server.start_countdown = _fake_start
    try:
        payload = _run(
            admin_start_tournament_countdown(
                "tr1",
                CountdownStartReq(seconds=45),
                user={"id": "admin-1", "pseudo": "Loowgan", "email": "admin@example.com"},
            )
        )
    finally:
        server.db = original_db
        server.hub = original_hub
        server.journal = original_journal
        server._ensure_tournament_can_start = original_ensure
        server.start_countdown = original_start

    assert payload["ok"] is True
    assert payload["seconds"] == 45
    assert called["ensured"] == "tr1"
    assert called["start"] == ("tr1", 45, "Loowgan")
    assert fake_hub.events[0][0] == "tr1"


def test_admin_cancel_tournament_countdown_deletes_existing_state():
    fake_db = FakeDB(tournaments=[{"id": "tr1", "name": "Beta Cup"}])
    fake_hub = FakeHub()
    fake_rs = FakeRedisState(countdown={"deadline": "123", "started_by": "Admin"})

    original_db = server.db
    original_hub = server.hub
    original_rs = server.rs
    original_journal = server.journal
    server.db = fake_db
    server.hub = fake_hub
    server.rs = fake_rs
    server.journal = _noop
    try:
        payload = _run(
            admin_cancel_tournament_countdown(
                "tr1",
                user={"id": "admin-1", "pseudo": "Loowgan", "email": "admin@example.com"},
            )
        )
    finally:
        server.db = original_db
        server.hub = original_hub
        server.rs = original_rs
        server.journal = original_journal

    assert payload == {"ok": True, "tournament_id": "tr1", "cancelled": True}
    assert fake_rs.deleted is True
    assert fake_rs.released is True
    assert fake_hub.events[0][0] == "tr1"
