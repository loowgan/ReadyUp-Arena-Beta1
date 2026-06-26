import asyncio
import os
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017/readyup_arena_test")

from fastapi import HTTPException

from server import _apply_reward_redemption_status_change


def _matches(doc, query):
    if not query:
        return True
    for key, expected in query.items():
        actual = doc.get(key)
        if isinstance(expected, dict):
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


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = deepcopy(docs or [])

    async def update_one(self, query, update):
        for doc in self.docs:
            if _matches(doc, query or {}):
                _apply_update(doc, update)
                return

    async def find_one(self, query=None, projection=None):
        for doc in self.docs:
            if _matches(doc, query or {}):
                return deepcopy(doc)
        return None


class FakeDB:
    def __init__(self, *, users=None, rewards=None, reward_redemptions=None):
        self.users = FakeCollection(users)
        self.rewards = FakeCollection(rewards)
        self.reward_redemptions = FakeCollection(reward_redemptions)


def _run(coro):
    return asyncio.run(coro)


def test_apply_reward_redemption_status_change_refunds_and_restocks_on_cancel():
    db = FakeDB(
        users=[{"id": "u1", "tokens": 120}],
        rewards=[{"id": "r1", "stock": 2}],
        reward_redemptions=[{"id": "rd1", "reward_id": "r1", "user_id": "u1", "cost_tokens": 80, "status": "pending"}],
    )

    updated = _run(
        _apply_reward_redemption_status_change(
            db,
            {"id": "rd1", "reward_id": "r1", "user_id": "u1", "cost_tokens": 80, "status": "pending"},
            "cancelled",
            "u1",
            "user",
        )
    )

    assert updated["status"] == "cancelled"
    assert updated["updated_by"] == "u1"
    assert updated["updated_by_role"] == "user"
    assert updated["cancelled_by"] == "u1"
    assert _run(db.users.find_one({"id": "u1"}))["tokens"] == 200
    assert _run(db.rewards.find_one({"id": "r1"}))["stock"] == 3
    assert _run(db.reward_redemptions.find_one({"id": "rd1"}))["status"] == "cancelled"


def test_apply_reward_redemption_status_change_rejects_cancelled_to_delivered():
    db = FakeDB(
        users=[{"id": "u1", "tokens": 200}],
        rewards=[{"id": "r1", "stock": 3}],
        reward_redemptions=[{"id": "rd1", "reward_id": "r1", "user_id": "u1", "cost_tokens": 80, "status": "cancelled"}],
    )

    try:
        _run(
            _apply_reward_redemption_status_change(
                db,
                {"id": "rd1", "reward_id": "r1", "user_id": "u1", "cost_tokens": 80, "status": "cancelled"},
                "delivered",
                "admin-1",
                "admin",
            )
        )
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "interdite" in str(exc.detail)
    else:
        raise AssertionError("Expected HTTPException for invalid reward redemption transition")
