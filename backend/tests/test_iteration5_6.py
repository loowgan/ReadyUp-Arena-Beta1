"""Backend tests for ReadyUp Arena Iteration 5/6:
- Mongo-backed catalogue (teams/players/tournaments/news)
- Tournament registration + state machine + Redis-scheduled auto-transition
- CS2 server CRUD + RCON + MatchZy webhook
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8000").rstrip("/")
API = f"{BASE_URL}/api"

TEST_EMAIL = os.environ.get("TEST_USER_EMAIL", "player@example.com")
TEST_PASSWORD = os.environ.get("TEST_USER_PASSWORD", "ChangeMe123!")
MATCHZY_SECRET = os.environ.get("MATCHZY_WEBHOOK_SECRET", "readyup-matchzy-secret")
REAL_CS2 = {
    "name": "TEST_real",
    "host": os.environ.get("TEST_REAL_CS2_HOST", ""),
    "port": int(os.environ.get("TEST_REAL_CS2_PORT", "30060")),
    "rcon_password": os.environ.get("TEST_REAL_CS2_RCON_PASSWORD", ""),
}


@pytest.fixture(scope="session")
def s():
    return requests.Session()


@pytest.fixture(scope="session")
def token(s):
    s.post(
        f"{API}/auth/register",
        json={"pseudo": "testuser", "email": TEST_EMAIL, "password": TEST_PASSWORD, "country": "FR"},
        timeout=15,
    )
    r = s.post(f"{API}/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="session")
def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


# ---------- Catalogue (Mongo-backed) ----------
class TestCatalogue:
    def test_teams_seeded(self, s):
        r = s.get(f"{API}/teams", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 8, f"expected >=8 teams, got {len(data)}"
        # validate shape
        t = data[0]
        for k in ("id", "name", "tag", "elo"):
            assert k in t, f"team missing {k}: {t}"

    def test_players_seeded(self, s):
        r = s.get(f"{API}/players", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 8
        p = data[0]
        assert "id" in p and "pseudo" in p

    def test_tournaments_seeded(self, s):
        r = s.get(f"{API}/tournaments", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 6
        ids = [t["id"] for t in data]
        assert "tr6" in ids, "tr6 must exist for registration test"

    def test_news_seeded(self, s):
        r = s.get(f"{API}/news", timeout=15)
        assert r.status_code == 200
        assert len(r.json()) >= 3

    def test_tournament_detail_shape(self, s):
        r = s.get(f"{API}/tournaments/tr6", timeout=15)
        assert r.status_code == 200
        t = r.json()
        for k in ("id", "name", "status", "teams_in", "solo_queue", "registrations_count"):
            assert k in t, f"missing {k}"
        assert isinstance(t["teams_in"], list)
        assert isinstance(t["solo_queue"], list)


# ---------- Tournament registration + state machine ----------
class TestTournament:
    def test_register_solo_on_tr6(self, s, auth_headers):
        # Ensure tr6 status is open/registering
        r0 = s.get(f"{API}/tournaments/tr6", timeout=15).json()
        assert r0["status"] in ("open", "registering"), f"tr6 not open: {r0['status']}"
        before = r0.get("registered", 0)
        r = s.post(f"{API}/tournaments/tr6/register",
                   json={"entity_type": "solo", "entity_name": "TestUser"},
                   headers=auth_headers, timeout=15)
        # could already be registered from a prior run -> 409 acceptable
        assert r.status_code in (200, 409), f"unexpected: {r.status_code} {r.text}"
        if r.status_code == 200:
            data = r.json()
            assert data["entity_type"] == "solo"
            assert data["entity_name"] == "TestUser"
            assert data["tournament_id"] == "tr6"
            # status & count check
            r2 = s.get(f"{API}/tournaments/tr6", timeout=15).json()
            assert r2.get("registered", 0) >= before + 1
            assert r2["status"] in ("registering", "starting", "live")

    def test_register_duplicate_409(self, s, auth_headers):
        # second call must 409 (we just registered, or already was)
        r = s.post(f"{API}/tournaments/tr6/register",
                   json={"entity_type": "solo", "entity_name": "TestUser"},
                   headers=auth_headers, timeout=15)
        assert r.status_code == 409, f"expected 409, got {r.status_code} {r.text}"

    def test_register_requires_auth(self, s):
        r = s.post(f"{API}/tournaments/tr6/register",
                   json={"entity_type": "solo", "entity_name": "Anon"}, timeout=15)
        assert r.status_code == 401

    def test_transition_state_machine(self, s, auth_headers):
        # Build a fresh tournament via direct insert is not exposed; instead use existing.
        # Pick a tournament with status 'open' that we can cycle.
        tournaments = s.get(f"{API}/tournaments", timeout=15).json()
        target = None
        for t in tournaments:
            if t["status"] == "open" and t["id"] != "tr6":
                target = t
                break
        if not target:
            # fallback: try tr1 or use any non-closed
            for t in tournaments:
                if t["status"] in ("open", "registering"):
                    target = t
                    break
        assert target, "no open/registering tournament for transition test"
        tid = target["id"]
        cur = target["status"]

        # Illegal: closed-state target unknown -> use known illegal: starting->open from current
        # Test bad state
        r_bad = s.post(f"{API}/tournaments/{tid}/transition",
                       json={"to": "bogus"}, headers=auth_headers, timeout=15)
        assert r_bad.status_code == 400

        # Walk to 'starting'
        if cur == "open":
            r1 = s.post(f"{API}/tournaments/{tid}/transition",
                        json={"to": "registering"}, headers=auth_headers, timeout=15)
            assert r1.status_code == 200, r1.text
            cur = "registering"
        if cur == "registering":
            r2 = s.post(f"{API}/tournaments/{tid}/transition",
                        json={"to": "starting"}, headers=auth_headers, timeout=15)
            assert r2.status_code == 200, r2.text
            cur = "starting"

        # Illegal transition starting -> open
        r3 = s.post(f"{API}/tournaments/{tid}/transition",
                    json={"to": "open"}, headers=auth_headers, timeout=15)
        assert r3.status_code == 409, f"expected 409 illegal: got {r3.status_code} {r3.text}"

        # Wait for auto go-live (~30s); poll up to 50s
        deadline = time.time() + 50
        new_status = "starting"
        while time.time() < deadline:
            tt = s.get(f"{API}/tournaments/{tid}", timeout=15).json()
            new_status = tt["status"]
            if new_status == "live":
                break
            time.sleep(3)
        assert new_status == "live", f"scheduler auto-transition failed; status={new_status}"

        # Cleanup: bring back to closed to avoid leaving it live forever
        s.post(f"{API}/tournaments/{tid}/transition",
               json={"to": "closed"}, headers=auth_headers, timeout=15)

    def test_register_on_closed_400(self, s, auth_headers):
        # Find any closed tournament
        tournaments = s.get(f"{API}/tournaments", timeout=15).json()
        closed = next((t for t in tournaments if t["status"] == "closed"), None)
        if not closed:
            pytest.skip("no closed tournament to test")
        r = s.post(f"{API}/tournaments/{closed['id']}/register",
                   json={"entity_type": "solo", "entity_name": "ShouldFail"},
                   headers=auth_headers, timeout=15)
        assert r.status_code == 400


# ---------- CS2 servers ----------
class TestCS2:
    created_ids = []

    def test_create_server_no_password_leak(self, s, auth_headers):
        payload = {"name": f"TEST_srv_{uuid.uuid4().hex[:6]}", "host": "127.0.0.1", "port": 27015, "rcon_password": "supersecret"}
        r = s.post(f"{API}/cs2/servers", json=payload, headers=auth_headers, timeout=15)
        assert r.status_code == 200, r.text
        srv = r.json()
        assert "rcon_password" not in srv, "rcon_password leaked!"
        assert srv["name"] == payload["name"]
        assert srv["host"] == payload["host"]
        TestCS2.created_ids.append(srv["id"])

    def test_list_servers_no_password(self, s):
        r = s.get(f"{API}/cs2/servers", timeout=15)
        assert r.status_code == 200
        for srv in r.json():
            assert "rcon_password" not in srv, f"rcon_password leaked in list: {srv}"

    def test_delete_server(self, s, auth_headers):
        if not TestCS2.created_ids:
            pytest.skip("no server created")
        sid = TestCS2.created_ids.pop(0)
        r = s.delete(f"{API}/cs2/servers/{sid}", headers=auth_headers, timeout=15)
        assert r.status_code == 200
        # verify gone
        r2 = s.get(f"{API}/cs2/servers", timeout=15).json()
        assert all(srv["id"] != sid for srv in r2)

    def test_rcon_real_server(self, s, auth_headers):
        if not REAL_CS2["host"] or not REAL_CS2["rcon_password"]:
            pytest.skip("Real CS2 server credentials not configured")
        # Find or create real server
        servers = s.get(f"{API}/cs2/servers", timeout=15).json()
        real = next((srv for srv in servers if srv["host"] == REAL_CS2["host"] and srv["port"] == REAL_CS2["port"]), None)
        if not real:
            r = s.post(f"{API}/cs2/servers", json=REAL_CS2, headers=auth_headers, timeout=15)
            assert r.status_code == 200, r.text
            real = r.json()
        sid = real["id"]
        # ping
        r = s.post(f"{API}/cs2/servers/{sid}/ping", headers=auth_headers, timeout=30)
        if r.status_code in (502, 504):
            pytest.skip(f"CS2 server intermittent ({r.status_code}): soft skip")
        assert r.status_code == 200, r.text
        body = r.json()
        assert "output" in body and isinstance(body["output"], str)
        # rcon status
        r2 = s.post(f"{API}/cs2/servers/{sid}/rcon", json={"command": "status"}, headers=auth_headers, timeout=30)
        if r2.status_code in (502, 504):
            pytest.skip(f"RCON status intermittent ({r2.status_code})")
        assert r2.status_code == 200, r2.text
        assert "output" in r2.json()


# ---------- MatchZy webhook ----------
class TestMatchZy:
    def test_webhook_requires_auth(self, s):
        r = s.post(f"{API}/cs2/webhooks/matchzy", json={"event": "test"}, timeout=15)
        assert r.status_code == 401

    def test_webhook_wrong_auth(self, s):
        r = s.post(f"{API}/cs2/webhooks/matchzy", json={"event": "test"},
                   headers={"Authorization": "wrong-secret"}, timeout=15)
        assert r.status_code == 401

    def test_webhook_accepts_with_secret(self, s):
        matchid = f"TEST_{uuid.uuid4().hex[:8]}"
        r = s.post(f"{API}/cs2/webhooks/matchzy",
                   json={"event": "map_start", "matchid": matchid},
                   headers={"Authorization": MATCHZY_SECRET}, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json().get("received") is True
        # verify it was stored
        r2 = s.get(f"{API}/cs2/events?matchid={matchid}", timeout=15)
        assert r2.status_code == 200
        events = r2.json()
        assert len(events) >= 1
        assert events[0]["matchid"] == matchid

    def test_events_list(self, s):
        r = s.get(f"{API}/cs2/events?limit=10", timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)
