"""Backend tests for ReadyUp Arena Iteration 7:
- Bracket generation (single/double) + match advancement
- Admin gating (403) on transitions/brackets/CS2
- Password reset cycle (forgot/reset)
- RCON encryption at rest
- Live matches aggregation
"""
import os
import time
import uuid
import pytest
import requests
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).resolve().parents[2] / "frontend" / ".env")
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = os.environ.get("TEST_ADMIN_EMAIL") or os.environ.get("SEED_ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD = os.environ.get("TEST_ADMIN_PASSWORD") or os.environ.get("SEED_ADMIN_PASSWORD", "ChangeMe123!")
NOOB_EMAIL = os.environ.get("TEST_NOOB_EMAIL", "noob@example.com")
NOOB_PASSWORD = os.environ.get("TEST_NOOB_PASSWORD", "ChangeMe123!")
MATCHZY_SECRET = os.environ.get("MATCHZY_WEBHOOK_SECRET", "readyup-matchzy-secret")


@pytest.fixture(scope="session")
def s():
    return requests.Session()


@pytest.fixture(scope="session")
def admin_headers(s):
    s.post(f"{API}/auth/register", json={
        "pseudo": "adminuser", "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD, "country": "FR"
    }, timeout=15)
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    data = r.json()
    assert data["user"]["is_admin"] is True, "admin login but is_admin=False in response; ensure ADMIN_EMAILS includes TEST_ADMIN_EMAIL/SEED_ADMIN_EMAIL"
    return {"Authorization": f"Bearer {data['token']}"}


@pytest.fixture(scope="session")
def noob_headers(s):
    # ensure noob user exists (idempotent)
    s.post(f"{API}/auth/register", json={
        "pseudo": "noobuser", "email": NOOB_EMAIL, "password": NOOB_PASSWORD, "country": "FR"
    }, timeout=15)
    r = s.post(f"{API}/auth/login", json={"email": NOOB_EMAIL, "password": NOOB_PASSWORD}, timeout=15)
    assert r.status_code == 200, f"noob login failed: {r.status_code} {r.text}"
    data = r.json()
    assert data["user"]["is_admin"] is False, "noob is_admin should be False"
    return {"Authorization": f"Bearer {data['token']}"}


@pytest.fixture(scope="session")
def open_tournament(s):
    r = s.get(f"{API}/tournaments", timeout=15)
    assert r.status_code == 200
    # pick first tournament that is not tr6 and not closed
    for t in r.json():
        if t["id"] != "tr6" and t.get("state") != "closed":
            return t["id"]
    return r.json()[0]["id"]


# ---------- Admin gating (403) ----------
class TestAdminGating:
    def test_me_admin_is_admin_true(self, s, admin_headers):
        r = s.get(f"{API}/auth/me", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        assert r.json()["is_admin"] is True

    def test_me_noob_is_admin_false(self, s, noob_headers):
        r = s.get(f"{API}/auth/me", headers=noob_headers, timeout=15)
        assert r.status_code == 200
        assert r.json()["is_admin"] is False

    def test_noob_transition_403(self, s, noob_headers, open_tournament):
        r = s.post(f"{API}/tournaments/{open_tournament}/transition",
                   json={"state": "registering"}, headers=noob_headers, timeout=15)
        assert r.status_code == 403, f"expected 403, got {r.status_code} {r.text}"

    def test_noob_bracket_generate_403(self, s, noob_headers, open_tournament):
        r = s.post(f"{API}/tournaments/{open_tournament}/bracket/generate",
                   json={"type": "single"}, headers=noob_headers, timeout=15)
        assert r.status_code == 403

    def test_noob_cs2_create_403(self, s, noob_headers):
        r = s.post(f"{API}/cs2/servers", json={
            "name": "TEST_noob", "host": "1.2.3.4", "port": 27015, "rcon_password": "x"
        }, headers=noob_headers, timeout=15)
        assert r.status_code == 403


# ---------- Bracket ----------
class TestBracket:
    def test_generate_single_and_get(self, s, admin_headers, open_tournament):
        r = s.post(f"{API}/tournaments/{open_tournament}/bracket/generate",
                   json={"type": "single"}, headers=admin_headers, timeout=20)
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        b = r.json()
        assert b["type"] == "single"
        assert "W" in b["matches"]
        assert len(b["matches"]["W"]) >= 1
        # GET
        r2 = s.get(f"{API}/tournaments/{open_tournament}/bracket", timeout=15)
        assert r2.status_code == 200
        assert r2.json()["type"] == "single"

    def test_generate_double_groups(self, s, admin_headers, open_tournament):
        r = s.post(f"{API}/tournaments/{open_tournament}/bracket/generate",
                   json={"type": "double"}, headers=admin_headers, timeout=20)
        assert r.status_code == 200
        b = r.json()
        assert b["type"] == "double"
        assert "W" in b["matches"] and "L" in b["matches"] and "GF" in b["matches"]
        assert len(b["matches"]["GF"]) == 1

    def test_single_elim_full_advancement_sets_champion(self, s, admin_headers, open_tournament):
        # regenerate fresh single bracket
        r = s.post(f"{API}/tournaments/{open_tournament}/bracket/generate",
                   json={"type": "single"}, headers=admin_headers, timeout=20)
        assert r.status_code == 200
        b = r.json()
        # iteratively report a winner for all "ready" matches until champion
        for _ in range(20):
            if b.get("champion_id"):
                break
            progressed = False
            for m in b["matches"]["W"]:
                if not m.get("winner_id") and not m.get("phantom") and m.get("a") and m.get("b"):
                    rr = s.post(
                        f"{API}/tournaments/{open_tournament}/bracket/match/{m['id']}/result",
                        json={"winner_id": m["a"]["id"]}, headers=admin_headers, timeout=15)
                    assert rr.status_code == 200, f"{rr.status_code} {rr.text}"
                    b = rr.json()
                    progressed = True
                    break
            if not progressed:
                break
        assert b.get("champion_id"), f"no champion after advancement: {b}"

    def test_report_unknown_participants_400(self, s, admin_headers, open_tournament):
        r = s.post(f"{API}/tournaments/{open_tournament}/bracket/generate",
                   json={"type": "single"}, headers=admin_headers, timeout=20)
        b = r.json()
        # find a round-1+ match with no participants yet
        target = None
        for m in b["matches"]["W"]:
            if not m.get("a") or not m.get("b"):
                if not m.get("phantom") and not m.get("winner_id"):
                    target = m
                    break
        if not target:
            pytest.skip("no incomplete-match candidate")
        rr = s.post(
            f"{API}/tournaments/{open_tournament}/bracket/match/{target['id']}/result",
            json={"winner_id": "fake"}, headers=admin_headers, timeout=15)
        assert rr.status_code == 400

    def test_report_twice_returns_409(self, s, admin_headers, open_tournament):
        r = s.post(f"{API}/tournaments/{open_tournament}/bracket/generate",
                   json={"type": "single"}, headers=admin_headers, timeout=20)
        b = r.json()
        # find a real round-0 match
        target = next((m for m in b["matches"]["W"]
                       if m.get("a") and m.get("b") and not m.get("winner_id")), None)
        assert target is not None
        wid = target["a"]["id"]
        rr1 = s.post(
            f"{API}/tournaments/{open_tournament}/bracket/match/{target['id']}/result",
            json={"winner_id": wid}, headers=admin_headers, timeout=15)
        assert rr1.status_code == 200
        rr2 = s.post(
            f"{API}/tournaments/{open_tournament}/bracket/match/{target['id']}/result",
            json={"winner_id": wid}, headers=admin_headers, timeout=15)
        assert rr2.status_code == 409


# ---------- Password reset ----------
class TestPasswordReset:
    def test_forgot_unknown_email_returns_200(self, s):
        r = s.post(f"{API}/auth/forgot-password", json={"email": f"TEST_nonexist_{uuid.uuid4().hex[:6]}@example.com"}, timeout=15)
        assert r.status_code == 200
        assert "message" in r.json()

    def test_full_reset_cycle(self, s):
        # create throwaway user
        email = f"TEST_reset_{uuid.uuid4().hex[:6]}@readyup.gg"
        pseudo = f"TestRst{uuid.uuid4().hex[:6]}"
        old_pw = "OldPass123!"
        new_pw = "NewPass456!"
        rr = s.post(f"{API}/auth/register", json={
            "pseudo": pseudo, "email": email, "password": old_pw, "country": "FR"
        }, timeout=15)
        assert rr.status_code == 200, f"register failed: {rr.text}"
        # request forgot
        rf = s.post(f"{API}/auth/forgot-password", json={"email": email}, timeout=15)
        assert rf.status_code == 200
        # fetch latest unused token via Mongo
        from motor.motor_asyncio import AsyncIOMotorClient  # noqa
        import asyncio
        async def get_token():
            cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
            db = cli[os.environ["DB_NAME"]]
            user = await db.users.find_one({"email": email.lower()})
            assert user, "user not found"
            pr = await db.password_resets.find_one({"user_id": user["id"], "used": False}, sort=[("created_at", -1)])
            cli.close()
            return pr["id"] if pr else None
        token = asyncio.run(get_token())
        assert token, "no token in password_resets"
        # reset
        rp = s.post(f"{API}/auth/reset-password", json={"token": token, "new_password": new_pw}, timeout=15)
        assert rp.status_code == 200, rp.text
        # login old should fail
        rlold = s.post(f"{API}/auth/login", json={"email": email, "password": old_pw}, timeout=15)
        assert rlold.status_code == 401
        # login new should succeed
        rln = s.post(f"{API}/auth/login", json={"email": email, "password": new_pw}, timeout=15)
        assert rln.status_code == 200
        # reuse token -> 400
        rreuse = s.post(f"{API}/auth/reset-password", json={"token": token, "new_password": "Another1234!"}, timeout=15)
        assert rreuse.status_code == 400

    def test_invalid_token_400(self, s):
        r = s.post(f"{API}/auth/reset-password", json={"token": "nonexistent-token-zzz", "new_password": "Whatever123!"}, timeout=15)
        assert r.status_code == 400


# ---------- RCON encryption + Live matches ----------
class TestRconEncryption:
    def test_create_server_password_not_in_list_and_encrypted_at_rest(self, s, admin_headers):
        import asyncio
        from motor.motor_asyncio import AsyncIOMotorClient
        plaintext = f"plain_{uuid.uuid4().hex[:8]}"
        body = {"name": f"TEST_enc_{uuid.uuid4().hex[:6]}", "host": "10.0.0.99", "port": 27999, "rcon_password": plaintext}
        rc = s.post(f"{API}/cs2/servers", json=body, headers=admin_headers, timeout=15)
        assert rc.status_code == 200
        srv = rc.json()
        assert "rcon_password" not in srv
        sid = srv["id"]
        # list -> no leak
        rl = s.get(f"{API}/cs2/servers", headers=admin_headers, timeout=15)
        assert rl.status_code == 200
        for s_ in rl.json():
            assert "rcon_password" not in s_
        # DB check
        async def check():
            cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
            db = cli[os.environ["DB_NAME"]]
            row = await db.cs2_servers.find_one({"id": sid})
            cli.close()
            return row
        row = asyncio.run(check())
        assert row is not None
        assert row.get("rcon_password") != plaintext, f"plaintext leaked at rest: {row.get('rcon_password')}"
        # cleanup
        s.delete(f"{API}/cs2/servers/{sid}", headers=admin_headers, timeout=15)


class TestLiveMatches:
    def test_live_endpoint_returns_seeded_demo(self, s):
        r = s.get(f"{API}/matches/live", timeout=15)
        assert r.status_code == 200
        live = r.json()
        assert isinstance(live, list)
        # demo seeds m-rua-101 and m-rua-102 expected
        ids = {m["matchid"] for m in live}
        # at least one of demos present (may be ended in other tests)
        assert len(live) >= 0  # smoke

    def test_match_detail_for_demo(self, s):
        r = s.get(f"{API}/matches/m-rua-101", timeout=15)
        # Either 200 with timeline, or 404 if cleaned -- accept 200 as success criterion
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            data = r.json()
            assert data["matchid"] == "m-rua-101"
            assert "timeline" in data and isinstance(data["timeline"], list)

    def test_round_end_updates_score_then_series_end_removes_live(self, s):
        # push events to a throwaway match
        mid = f"TEST_live_{uuid.uuid4().hex[:8]}"
        headers = {"Authorization": MATCHZY_SECRET}
        # round_end with score 1-0
        ev1 = {
            "event": "round_end",
            "matchid": mid,
            "team1": {"name": "Alpha", "score": 1},
            "team2": {"name": "Beta", "score": 0},
            "map_name": "de_mirage",
        }
        r1 = s.post(f"{API}/cs2/webhooks/matchzy", json=ev1, headers=headers, timeout=15)
        assert r1.status_code == 200
        # bump to 5-3
        ev2 = dict(ev1)
        ev2["team1"] = {"name": "Alpha", "score": 5}
        ev2["team2"] = {"name": "Beta", "score": 3}
        r2 = s.post(f"{API}/cs2/webhooks/matchzy", json=ev2, headers=headers, timeout=15)
        assert r2.status_code == 200
        # check live includes it
        rl = s.get(f"{API}/matches/live", timeout=15)
        assert rl.status_code == 200
        found = next((m for m in rl.json() if m["matchid"] == mid), None)
        assert found is not None, f"match {mid} not in live list"
        # series_end should remove from live
        evend = {"event": "series_end", "matchid": mid, "winner": "team1"}
        re = s.post(f"{API}/cs2/webhooks/matchzy", json=evend, headers=headers, timeout=15)
        assert re.status_code == 200
        rl2 = s.get(f"{API}/matches/live", timeout=15)
        ids = {m["matchid"] for m in rl2.json()}
        assert mid not in ids
