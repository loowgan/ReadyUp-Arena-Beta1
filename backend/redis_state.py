"""Redis-backed state for ReadyUp Arena (Iteration 5).

- Authoritative WS countdowns persisted as a target deadline timestamp so they
  survive backend reboots (remaining seconds are recomputed from the deadline).
- A lightweight Redis sorted-set job queue used by the tournament state machine
  to schedule auto-transitions (e.g. registering -> starting at starts_at).
"""
import os
import json
import redis.asyncio as aioredis

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
r = aioredis.from_url(REDIS_URL, decode_responses=True)

CD_PREFIX = "rua:countdown:"
JOBS_KEY = "rua:jobs"


# ---------- Countdowns ----------
async def set_countdown(tid: str, deadline_ts: float, phase: str, started_by: str):
    await r.hset(CD_PREFIX + tid, mapping={
        "deadline": str(deadline_ts), "phase": phase, "started_by": started_by,
    })


async def get_countdown(tid: str):
    d = await r.hgetall(CD_PREFIX + tid)
    return d or None


async def del_countdown(tid: str):
    await r.delete(CD_PREFIX + tid)


async def active_countdowns():
    keys = await r.keys(CD_PREFIX + "*")
    return [k[len(CD_PREFIX):] for k in keys]


# ---------- Job queue (sorted set scored by run-at unix ts) ----------
async def schedule_job(run_at_ts: float, job: dict):
    await r.zadd(JOBS_KEY, {json.dumps(job): run_at_ts})


async def pop_due_jobs(now_ts: float):
    items = await r.zrangebyscore(JOBS_KEY, 0, now_ts)
    if items:
        await r.zrem(JOBS_KEY, *items)
    return [json.loads(i) for i in items]


async def ping() -> bool:
    try:
        return await r.ping()
    except Exception:
        return False


# ---------- Per-tournament countdown lock (multi-replica safe) ----------
LOCK_PREFIX = "rua:cdlock:"

async def acquire_cd_lock(tid: str, ttl: int = 5) -> bool:
    return bool(await r.set(LOCK_PREFIX + tid, "1", nx=True, ex=ttl))

async def refresh_cd_lock(tid: str, ttl: int = 5):
    await r.expire(LOCK_PREFIX + tid, ttl)

async def release_cd_lock(tid: str):
    await r.delete(LOCK_PREFIX + tid)
