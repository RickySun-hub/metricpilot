"""Conservative durable reservations; local SQLite or shared Redis in public mode.

Reservations are never refunded, including provider failures. They bound spend rather
than reporting provider invoices. Keep the same ledger for every run of this project;
removing it or switching quota stores discards the accounting history. A local ledger
cannot enforce a global limit across independent machines or disposable deployments.
"""
from __future__ import annotations

from contextlib import ExitStack, closing, contextmanager
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_FLOOR
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import tempfile
import time

import httpx


HARD_TOTAL_CAP_USD = 5.0
DEFAULT_RESERVATION_USD = 0.02
DEFAULT_BUDGET_DB = Path(__file__).resolve().parents[1] / "artifacts/local/metricpilot-budget-v1.sqlite"
LEGACY_BUDGET_DB = Path(tempfile.gettempdir()) / "metricpilot-budget-v1.sqlite"
_MICRO_USD = 1_000_000
_NAMESPACE = "metricpilot:v1:"
_EXHAUSTED = "Live request budget or rate limit exhausted"


class BudgetError(ValueError):
    pass


def _uses_shared_quota() -> bool:
    # Explicit shared configuration selects one store for both local evaluations
    # and deployed requests. Even empty/partial configuration must fail closed.
    return bool(os.getenv("VERCEL") or "UPSTASH_REDIS_REST_URL" in os.environ
                or "UPSTASH_REDIS_REST_TOKEN" in os.environ)


def live_available() -> bool:
    return bool(os.getenv("OPENAI_API_KEY") and os.getenv("METRICPILOT_ENABLE_LIVE") == "1" and
                (not _uses_shared_quota() or (os.getenv("UPSTASH_REDIS_REST_URL") and os.getenv("UPSTASH_REDIS_REST_TOKEN"))))


def _caps() -> tuple[int, int]:
    try:
        total = Decimal(os.getenv("METRICPILOT_TOTAL_CAP_USD", str(HARD_TOTAL_CAP_USD)))
        daily = Decimal(os.getenv("METRICPILOT_DAILY_CAP_USD", "1"))
    except InvalidOperation:
        raise BudgetError("Invalid budget configuration") from None
    # Validate before clamping: NaN defeats comparisons; nonpositive caps are invalid.
    if not total.is_finite() or not daily.is_finite() or total <= 0 or daily <= 0:
        raise BudgetError("Invalid budget configuration")
    total = min(total, Decimal(str(HARD_TOTAL_CAP_USD)))
    daily = min(daily, total)
    # Rounding caps down and reservations up cannot authorize a fractional overrun.
    return (int((daily * _MICRO_USD).to_integral_value(rounding=ROUND_FLOOR)),
            int((total * _MICRO_USD).to_integral_value(rounding=ROUND_FLOOR)))


def _reservation_microusd(amount: float) -> int:
    try:
        value = Decimal(str(amount))
    except InvalidOperation:
        raise BudgetError("Invalid reservation") from None
    if not value.is_finite() or value <= 0 or value > Decimal(str(DEFAULT_RESERVATION_USD)):
        raise BudgetError("Invalid reservation")
    return int((value * _MICRO_USD).to_integral_value(rounding=ROUND_CEILING))


def _totals(rows: list, day: str) -> tuple[int, int]:
    daily = total = 0
    for row_day, client, at, amount in rows:
        try:
            value = Decimal(str(amount))
            valid = (value.is_finite() and value > 0 and isinstance(row_day, str)
                     and isinstance(client, str) and math.isfinite(at))
        except (InvalidOperation, TypeError):
            valid = False
        if not valid:
            raise BudgetError("Local quota ledger unavailable; invalid reservation history")
        # Existing REAL-valued ledgers remain compatible; sum exact integer units.
        units = int((value * _MICRO_USD).to_integral_value(rounding=ROUND_CEILING))
        total += units
        if row_day == day:
            daily += units
    return daily, total


def _read_rows(db: sqlite3.Connection) -> list:
    return db.execute("SELECT day, client, at, amount FROM reservations ORDER BY rowid").fetchall()


def _fingerprint(rows: list) -> str:
    return hashlib.sha256(json.dumps(rows, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _legacy_history(path: Path, stack: ExitStack) -> list | None:
    if path != DEFAULT_BUDGET_DB.resolve() or path == LEGACY_BUDGET_DB.resolve() or not LEGACY_BUDGET_DB.exists():
        return None
    legacy = stack.enter_context(closing(sqlite3.connect(
        LEGACY_BUDGET_DB.resolve().as_uri() + "?mode=ro", uri=True, timeout=10,
    )))
    # Hold the legacy read transaction through the target transaction. Migration
    # preserves the source, and future source changes are detected and fail closed.
    legacy.execute("BEGIN")
    rows = _read_rows(legacy)
    _totals(rows, "")
    return rows


def _reconcile_legacy(db: sqlite3.Connection, rows: list, legacy: list | None, *, writable: bool) -> list:
    if legacy is None:
        return rows
    has_metadata = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='budget_metadata'").fetchone()
    imported = db.execute("SELECT value FROM budget_metadata WHERE key='legacy_fingerprint'").fetchone() if has_metadata else None
    fingerprint = _fingerprint(legacy)
    if imported:
        if imported[0] != fingerprint:
            raise BudgetError("Legacy quota ledger changed after migration; reconcile spending before live calls")
        return rows
    if rows and _fingerprint(rows) != fingerprint:
        raise BudgetError("Ambiguous local quota ledgers; reconcile spending before live calls")
    if writable:
        if not rows:
            db.executemany("INSERT INTO reservations VALUES (?,?,?,?)", legacy)
        db.execute("CREATE TABLE IF NOT EXISTS budget_metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        db.execute("INSERT INTO budget_metadata VALUES ('legacy_fingerprint', ?)", [fingerprint])
    return rows or legacy


@contextmanager
def _local_history(*, writable: bool):
    """Open one serialized transaction; a snapshot never creates files or schema."""
    path = Path(os.getenv("METRICPILOT_BUDGET_DB", str(DEFAULT_BUDGET_DB))).expanduser().resolve()
    try:
        with ExitStack() as stack:
            if not writable and not path.exists():
                yield None, _legacy_history(path, stack) or []
                return
            if writable:
                path.parent.mkdir(parents=True, exist_ok=True)
                db = stack.enter_context(closing(sqlite3.connect(path, timeout=10)))
                db.execute("BEGIN IMMEDIATE")
                db.execute("CREATE TABLE IF NOT EXISTS reservations(day TEXT, client TEXT, at REAL, amount REAL)")
            else:
                db = stack.enter_context(closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=10)))
                db.execute("BEGIN")
            rows = _read_rows(db)
            _totals(rows, "")
            rows = _reconcile_legacy(db, rows, _legacy_history(path, stack), writable=writable)
            yield db, rows
            if writable:
                db.commit()
    except (sqlite3.Error, OSError) as exc:
        raise BudgetError("Local quota ledger unavailable; live calls disabled") from exc


def _shared_request(command: list):
    url, token = os.getenv("UPSTASH_REDIS_REST_URL"), os.getenv("UPSTASH_REDIS_REST_TOKEN")
    if not url or not token:
        raise BudgetError("Public live mode requires durable shared quota accounting")
    try:
        response = httpx.post(url, headers={"Authorization": "Bearer " + token}, json=command, timeout=5)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or "error" in payload or "result" not in payload:
            raise ValueError("Invalid quota response")
        return payload["result"]
    except (httpx.HTTPError, ValueError) as exc:
        raise BudgetError("Shared quota service unavailable; live calls disabled") from exc


def reserve(amount: float = DEFAULT_RESERVATION_USD, client: str = "local") -> None:
    """Reserve before any provider attempt; no refunds prevent concurrent overspend."""
    units = _reservation_microusd(amount)
    daily_cap, total_cap = _caps()
    if units > daily_cap or units > total_cap:
        raise BudgetError(_EXHAUSTED)
    day = datetime.now(timezone.utc).date().isoformat()
    if _uses_shared_quota():
        script = """local a=tonumber(ARGV[1]); local d=tonumber(redis.call('GET',KEYS[1]) or '0');
local t=tonumber(redis.call('GET',KEYS[2]) or '0'); local r=tonumber(redis.call('GET',KEYS[3]) or '0');
if not d or not t or not r or d<0 or t<d or r<0 then return -1 end;
if d+a>tonumber(ARGV[2]) or t+a>tonumber(ARGV[3]) or r>=tonumber(ARGV[4]) then return 0 end;
redis.call('INCRBY',KEYS[1],a); redis.call('INCRBY',KEYS[2],a);
redis.call('INCR',KEYS[3]); redis.call('EXPIRE',KEYS[3],60); return 1"""
        command = ["EVAL", script, "3", _NAMESPACE + day, _NAMESPACE + "lifetime", _NAMESPACE + "client:" + client,
                   str(units), str(daily_cap), str(total_cap), "3"]
        result = _shared_request(command)
        if type(result) is not int or result not in (0, 1):
            raise BudgetError("Shared quota service unavailable; live calls disabled")
        if result == 0:
            raise BudgetError(_EXHAUSTED)
        return
    with _local_history(writable=True) as (db, rows):
        daily, total = _totals(rows, day)
        now = time.time()
        recent = sum(row[1] == client and row[2] > now - 60 for row in rows)
        if daily + units > daily_cap or total + units > total_cap or recent >= 3:
            raise BudgetError(_EXHAUSTED)
        db.execute("INSERT INTO reservations VALUES (?,?,?,?)", [day, client, now, units / _MICRO_USD])


def budget_snapshot() -> dict:
    """Read reserved allowances without reserving, creating, or migrating a ledger.

    Totals are conservative reservations, not provider-billed costs. This is only
    an observation; reserve() still performs the atomic admission check. Explicit
    shared configuration or public mode selects Redis without a local fallback.
    """
    daily_cap, total_cap = _caps()
    day = datetime.now(timezone.utc).date().isoformat()
    if _uses_shared_quota():
        result = _shared_request(["MGET", _NAMESPACE + day, _NAMESPACE + "lifetime"])
        try:
            if not isinstance(result, list) or len(result) != 2:
                raise ValueError("Invalid quota balances")
            values = [Decimal(str(value)) if value is not None else Decimal(0) for value in result]
            if any(not value.is_finite() or value < 0 or value != value.to_integral_value() for value in values):
                raise ValueError("Invalid quota balances")
            daily, total = map(int, values)
            if daily > total:
                raise ValueError("Invalid quota balances")
        except (ValueError, InvalidOperation):
            raise BudgetError("Shared quota service unavailable; live calls disabled") from None
        storage_backend = "redis"
    else:
        with _local_history(writable=False) as (_, rows):
            daily, total = _totals(rows, day)
        storage_backend = "sqlite"
    return {
        "day": day,
        "storage_backend": storage_backend,
        "reservation_usd": DEFAULT_RESERVATION_USD,
        "daily_cap_usd": daily_cap / _MICRO_USD,
        "total_cap_usd": total_cap / _MICRO_USD,
        "daily_reserved_usd": daily / _MICRO_USD,
        "total_reserved_usd": total / _MICRO_USD,
        "daily_remaining_usd": max(0, daily_cap - daily) / _MICRO_USD,
        "total_remaining_usd": max(0, total_cap - total) / _MICRO_USD,
    }
