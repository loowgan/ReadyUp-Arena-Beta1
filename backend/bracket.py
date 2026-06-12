"""Tournament bracket generation + advancement (single & double elimination).

Pure-logic helpers (no DB) plus a small router factory. Entrants are dicts
{"id": str, "name": str}. Brackets are JSON-serialisable dicts persisted in the
`brackets` collection keyed by tournament_id.
"""
import math
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _new_match(group: str, rnd: int, index: int, a=None, b=None) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "group": group,          # "W" winners, "L" losers, "GF" grand final
        "round": rnd,
        "index": index,
        "a": a, "b": b,
        "a_name": a["name"] if a else None,
        "b_name": b["name"] if b else None,
        "winner_id": None,
        "win_to": None,          # {"match": id, "slot": "a"|"b"}
        "loser_to": None,        # winners-bracket losers drop here (double elim)
    }


def _seed_order(size: int):
    """Standard tournament seed positions (1-based) for a bracket of `size`."""
    seeds = [1]
    while len(seeds) < size:
        length = len(seeds) * 2
        seeds = [x for s in seeds for x in (s, length + 1 - s)]
    return seeds


def _pad(entrants: List[dict]):
    size = 1
    while size < max(len(entrants), 2):
        size *= 2
    m = len(entrants)
    padded = [entrants[s - 1] if s <= m else None for s in _seed_order(size)]
    return padded, size


def _index(bracket: dict):
    return {m["id"]: m for grp in bracket["matches"].values() for m in grp}


def _place(by_id: dict, target, entity: dict):
    if not target or not entity:
        return
    m = by_id.get(target["match"])
    if not m:
        return
    m[target["slot"]] = entity
    m[target["slot"] + "_name"] = entity["name"]


def _feeders(bracket: dict):
    """(match_id, slot) -> (source_match_id, 'win'|'lose')."""
    fmap = {}
    for grp in bracket["matches"].values():
        for m in grp:
            for tgt, kind in ((m.get("win_to"), "win"), (m.get("loser_to"), "lose")):
                if tgt:
                    fmap[(tgt["match"], tgt["slot"])] = (m["id"], kind)
    return fmap


def _loser_entity(m: dict):
    if not m["winner_id"]:
        return None
    return m["b"] if (m["a"] and m["a"]["id"] == m["winner_id"]) else m["a"]


def _slot_state(by_id, fmap, m, slot):
    """Return (ready, entity_or_None) for a match slot, resolving feeders/byes."""
    if m[slot] is not None:
        return True, m[slot]
    key = (m["id"], slot)
    if key not in fmap:
        # round-0 slot left empty == confirmed bye
        return True, None
    src_id, kind = fmap[key]
    src = by_id.get(src_id)
    if not src:
        return False, None
    if src.get("phantom"):
        return True, None
    if src["winner_id"]:
        if kind == "win":
            w = src["a"] if (src["a"] and src["a"]["id"] == src["winner_id"]) else src["b"]
            return True, w
        return True, _loser_entity(src)
    return False, None


def _resolve(bracket, by_id, m, winner_id, auto=False):
    a, b = m["a"], m["b"]
    winner = a if (a and a["id"] == winner_id) else b if (b and b["id"] == winner_id) else None
    if not winner:
        raise HTTPException(400, "Le gagnant doit être l'un des participants du match")
    loser = b if winner is a else a
    m["winner_id"] = winner_id
    m["resolved_auto"] = auto
    _place(by_id, m["win_to"], winner)
    if m.get("loser_to") and loser:
        _place(by_id, m["loser_to"], loser)


def _settle(bracket: dict):
    """Materialise every determinable placement and auto-advance byes/phantoms."""
    by_id = _index(bracket)
    fmap = _feeders(bracket)
    changed = True
    while changed:
        changed = False
        for grp in bracket["matches"].values():
            for m in grp:
                if m["winner_id"] or m.get("phantom"):
                    continue
                a_ready, a_val = _slot_state(by_id, fmap, m, "a")
                b_ready, b_val = _slot_state(by_id, fmap, m, "b")
                if not (a_ready and b_ready):
                    continue
                if a_val and m["a"] is None:
                    m["a"] = a_val; m["a_name"] = a_val["name"]; changed = True
                if b_val and m["b"] is None:
                    m["b"] = b_val; m["b_name"] = b_val["name"]; changed = True
                if a_val and b_val:
                    continue  # real match, await manual result
                if not a_val and not b_val:
                    m["phantom"] = True; changed = True; continue
                _resolve(bracket, by_id, m, (a_val or b_val)["id"], auto=True); changed = True
    if bracket["type"] == "single":
        bracket["champion_id"] = bracket["matches"]["W"][-1]["winner_id"]
    else:
        bracket["champion_id"] = bracket["matches"]["GF"][0]["winner_id"]


# ---------------- Single elimination ----------------
def generate_single(entrants: List[dict]) -> dict:
    padded, size = _pad(entrants)
    k = int(math.log2(size))
    rounds = []
    r0 = []
    for i in range(0, size, 2):
        r0.append(_new_match("W", 0, len(r0), padded[i], padded[i + 1]))
    rounds.append(r0)
    prev = r0
    for rnd in range(1, k):
        cur = [_new_match("W", rnd, j) for j in range(len(prev) // 2)]
        for i, src in enumerate(prev):
            src["win_to"] = {"match": cur[i // 2]["id"], "slot": "a" if i % 2 == 0 else "b"}
        rounds.append(cur)
        prev = cur
    bracket = {"type": "single", "size": size, "matches": {"W": [m for r in rounds for m in r]},
               "rounds": {"W": len(rounds)}, "created_at": _now_iso(), "champion_id": None}
    _settle(bracket)
    return bracket


# ---------------- Double elimination ----------------
def generate_double(entrants: List[dict]) -> dict:
    padded, size = _pad(entrants)
    k = int(math.log2(size))
    # Winners bracket
    W = []
    rounds_w = []
    r0 = [_new_match("W", 0, j, padded[2 * j], padded[2 * j + 1]) for j in range(size // 2)]
    rounds_w.append(r0)
    prev = r0
    for rnd in range(1, k):
        cur = [_new_match("W", rnd, j) for j in range(len(prev) // 2)]
        for i, src in enumerate(prev):
            src["win_to"] = {"match": cur[i // 2]["id"], "slot": "a" if i % 2 == 0 else "b"}
        rounds_w.append(cur)
        prev = cur
    for r in rounds_w:
        W.extend(r)

    # Losers bracket: 2k-2 rounds (k>=2). For k==1 there is no LB.
    L = []
    rounds_l = []
    if k >= 2:
        # LB round 1: losers of W round 0 -> size/4 matches
        lb1 = [_new_match("L", 0, j) for j in range(size // 4 or 1)]
        rounds_l.append(lb1)
        prev_l = lb1
        total_lb_rounds = 2 * k - 2
        for r in range(1, total_lb_rounds):
            if r % 2 == 1:
                # minor: winners of prev LB vs losers from a WB round -> same count as prev
                cnt = len(prev_l)
            else:
                # major: winners of prev LB play each other -> halve
                cnt = max(len(prev_l) // 2, 1)
            cur = [_new_match("L", r, j) for j in range(cnt)]
            rounds_l.append(cur)
            prev_l = cur
        for r in rounds_l:
            L.extend(r)

        # Link LB winners forward
        for ri in range(len(rounds_l) - 1):
            cur = rounds_l[ri]; nxt = rounds_l[ri + 1]
            nxt_is_minor = ((ri + 1) % 2 == 1)
            for i, m in enumerate(cur):
                if nxt_is_minor:
                    # winners keep position, drop into slot 'a' (WB loser fills 'b')
                    m["win_to"] = {"match": nxt[i]["id"], "slot": "a"}
                else:
                    m["win_to"] = {"match": nxt[i // 2]["id"], "slot": "a" if i % 2 == 0 else "b"}

        # WB round-0 losers -> LB round 0 (pair them)
        for i, m in enumerate(rounds_w[0]):
            m["loser_to"] = {"match": rounds_l[0][i // 2]["id"], "slot": "a" if i % 2 == 0 else "b"}
        # WB round r (r>=1) losers -> LB minor round (2r-1), slot 'b'
        for wr in range(1, k):
            lb_round = 2 * wr - 1
            if lb_round < len(rounds_l):
                for i, m in enumerate(rounds_w[wr]):
                    if i < len(rounds_l[lb_round]):
                        m["loser_to"] = {"match": rounds_l[lb_round][i]["id"], "slot": "b"}

    # Grand final: WB final winner vs LB final winner
    gf = _new_match("GF", 0, 0)
    W[-1]["win_to"] = {"match": gf["id"], "slot": "a"}   # WB champion
    if L:
        rounds_l[-1][-1]["win_to"] = {"match": gf["id"], "slot": "b"}

    bracket = {"type": "double", "size": size,
               "matches": {"W": W, "L": L, "GF": [gf]},
               "rounds": {"W": len(rounds_w), "L": len(rounds_l)},
               "created_at": _now_iso(), "champion_id": None}
    _settle(bracket)
    return bracket


def report_match(bracket: dict, match_id: str, winner_id: str) -> dict:
    by_id = _index(bracket)
    m = by_id.get(match_id)
    if not m:
        raise HTTPException(404, "Match introuvable dans le bracket")
    if not m["a"] or not m["b"]:
        raise HTTPException(400, "Les deux participants ne sont pas encore connus")
    if m["winner_id"]:
        raise HTTPException(409, "Résultat déjà saisi pour ce match")
    _resolve(bracket, by_id, m, winner_id)
    _settle(bracket)
    return bracket


def build_bracket_router(db, get_admin_user, journal):
    router = APIRouter(prefix="/api/tournaments")

    async def _entrants(tid: str) -> List[dict]:
        regs = await db.tournament_registrations.find(
            {"tournament_id": tid, "entity_type": "team"}, {"_id": 0}).sort("created_at", 1).to_list(200)
        entrants = [{"id": r.get("entity_id") or r["id"], "name": r["entity_name"]} for r in regs]
        if len(entrants) < 2:
            # fallback to seeded teams for a usable demo bracket
            teams = await db.teams.find({}, {"_id": 0}).sort("elo", -1).to_list(8)
            entrants = [{"id": t["id"], "name": t["name"]} for t in teams]
        return entrants

    class GenReq(BaseModel):
        type: str = Field(default="single", pattern="^(single|double)$")

    @router.post("/{tid}/bracket/generate")
    async def generate(tid: str, req: GenReq, admin=Depends(get_admin_user)):
        t = await db.tournaments.find_one({"id": tid})
        if not t:
            raise HTTPException(404, "Tournoi introuvable")
        entrants = await _entrants(tid)
        bracket = generate_double(entrants) if req.type == "double" else generate_single(entrants)
        bracket["tournament_id"] = tid
        bracket["version"] = 0
        await db.brackets.replace_one({"tournament_id": tid}, bracket, upsert=True)
        await journal("bracket_generated", admin["id"], {"tournament_id": tid, "type": req.type, "entrants": len(entrants)})
        return {k: v for k, v in bracket.items() if k != "_id"}

    @router.get("/{tid}/bracket")
    async def get_bracket(tid: str):
        b = await db.brackets.find_one({"tournament_id": tid}, {"_id": 0})
        if not b:
            raise HTTPException(404, "Aucun bracket généré pour ce tournoi")
        return b

    class ResultReq(BaseModel):
        winner_id: str
        expected_version: Optional[int] = None

    @router.post("/{tid}/bracket/match/{match_id}/result")
    async def set_result(tid: str, match_id: str, req: ResultReq, admin=Depends(get_admin_user)):
        raw = await db.brackets.find_one({"tournament_id": tid})
        if not raw:
            raise HTTPException(404, "Aucun bracket généré")
        has_version = "version" in raw
        current_version = raw.get("version", 0)
        # Optimistic concurrency: reject stale client submissions early
        if req.expected_version is not None and req.expected_version != current_version:
            raise HTTPException(409, "Le bracket a été modifié par un autre administrateur. Rechargez et réessayez.")
        b = {k: v for k, v in raw.items() if k != "_id"}
        report_match(b, match_id, req.winner_id)
        b["version"] = current_version + 1
        # Conditional write guarded by the version we read (multi-admin safe)
        flt = {"tournament_id": tid, "version": current_version} if has_version \
            else {"tournament_id": tid, "version": {"$exists": False}}
        res = await db.brackets.replace_one(flt, b)
        if res.matched_count == 0:
            raise HTTPException(409, "Le bracket a été modifié par un autre administrateur. Rechargez et réessayez.")
        await journal("bracket_result", admin["id"], {"tournament_id": tid, "match": match_id, "winner": req.winner_id, "version": b["version"]})
        return b

    return router
