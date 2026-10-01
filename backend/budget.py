"""Reserve cost before calls. Local SQLite or atomic shared Redis for public live mode."""
from __future__ import annotations

import math
import os
import sqlite3
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx


class BudgetError(ValueError):
    pass


def live_available() -> bool:
    return bool(os.getenv("OPENAI_API_KEY") and os.getenv("METRICPILOT_ENABLE_LIVE") == "1" and
                (not os.getenv("VERCEL") or (os.getenv("UPSTASH_REDIS_REST_URL") and os.getenv("UPSTASH_REDIS_REST_TOKEN"))))


def reserve(amount: float = 0.02, client: str = "local") -> None:
    """Conservative per-request reservation; no refund avoids concurrent overspend."""
    if not math.isfinite(amount) or amount <= 0 or amount > 0.02:
        raise BudgetError("Invalid reservation")
    day = datetime.now(timezone.utc).date().isoformat()
    try:
        total_cap = float(os.getenv("METRICPILOT_TOTAL_CAP_USD", "30"))
        daily_cap = float(os.getenv("METRICPILOT_DAILY_CAP_USD", "1"))
    except ValueError:
        raise BudgetError("Invalid budget configuration") from None
    # Validate before clamping: NaN defeats comparisons and infinity is not approval.
    if not math.isfinite(total_cap) or not math.isfinite(daily_cap):
        raise BudgetError("Invalid budget configuration")
    # The configured cap can be lower, never silently higher than the approved $30 ceiling.
    total_cap = min(total_cap, 30)
    daily_cap = min(daily_cap, total_cap)
    url, token = os.getenv("UPSTASH_REDIS_REST_URL"), os.getenv("UPSTASH_REDIS_REST_TOKEN")
    if os.getenv("VERCEL"):
        if not url or not token:
            raise BudgetError("Public live mode requires durable shared quota accounting")
        script = """local a=tonumber(ARGV[1]); local d=tonumber(redis.call('GET',KEYS[1]) or '0');
local t=tonumber(redis.call('GET',KEYS[2]) or '0'); local r=tonumber(redis.call('GET',KEYS[3]) or '0');
if d+a>tonumber(ARGV[2]) or t+a>tonumber(ARGV[3]) or r>=tonumber(ARGV[4]) then return 0 end;
redis.call('INCRBY',KEYS[1],a); redis.call('INCRBY',KEYS[2],a);
redis.call('INCR',KEYS[3]); redis.call('EXPIRE',KEYS[3],60); return 1"""
        namespace = "metricpilot:v1:"
        command = ["EVAL", script, "3", namespace+day, namespace+"lifetime", namespace+client,
                   str(round(amount*1000000)), str(round(daily_cap*1000000)), str(round(total_cap*1000000)), "3"]
        try:
            response = httpx.post(url, headers={"Authorization": "Bearer "+token}, json=command, timeout=5)
            response.raise_for_status()
            if response.json().get("result") != 1:
                raise BudgetError("Live request budget or rate limit exhausted")
        except httpx.HTTPError as exc:
            raise BudgetError("Shared quota service unavailable; live calls disabled") from exc
        return
    path = Path(os.getenv("METRICPILOT_BUDGET_DB", str(Path(tempfile.gettempdir())/"metricpilot-budget-v1.sqlite")))
    with sqlite3.connect(path, timeout=10) as db:
        db.execute("CREATE TABLE IF NOT EXISTS reservations(day TEXT, client TEXT, at REAL, amount REAL)")
        db.execute("BEGIN IMMEDIATE")
        daily, total = db.execute("SELECT COALESCE(SUM(CASE WHEN day=? THEN amount ELSE 0 END),0),COALESCE(SUM(amount),0) FROM reservations", [day]).fetchone()
        recent = db.execute("SELECT COUNT(*) FROM reservations WHERE client=? AND at>?", [client, time.time()-60]).fetchone()[0]
        if daily+amount > daily_cap+1e-9 or total+amount > total_cap+1e-9 or recent >= 3:
            raise BudgetError("Live request budget or rate limit exhausted")
        db.execute("INSERT INTO reservations VALUES (?,?,?,?)", [day, client, time.time(), amount])
