"""Real local quota accounting and mocked outages; no paid or Redis requests."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from threading import Barrier

import httpx
import pytest

import backend.budget as budget


@pytest.fixture
def local_budget(tmp_path, monkeypatch):
    """Every test owns its database, caps, and network boundary."""
    path = tmp_path / "budget.sqlite"
    for name in ("VERCEL", "OPENAI_API_KEY", "METRICPILOT_ENABLE_LIVE",
                 "UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("METRICPILOT_BUDGET_DB", str(path))
    monkeypatch.setenv("METRICPILOT_DAILY_CAP_USD", "1")
    monkeypatch.setenv("METRICPILOT_TOTAL_CAP_USD", "30")

    def unexpected_network(*args, **kwargs):
        pytest.fail("Budget tests must not make network requests")

    monkeypatch.setattr(budget.httpx, "post", unexpected_network)
    return path


def _reserve_in_new_process(path, clients):
    # An independent interpreter proves persistence, rather than module state.
    script = """
import json, sys
from backend import budget
def no_network(*args, **kwargs):
    raise AssertionError('No network requests are permitted')
budget.httpx.post = no_network
outcomes = []
for client in json.loads(sys.argv[1]):
    try:
        budget.reserve(client=client)
    except budget.BudgetError:
        outcomes.append('rejected')
    else:
        outcomes.append('reserved')
print(json.dumps(outcomes))
"""
    # Do not inherit live-mode settings or credentials into the subprocess.
    env = {name: os.environ[name] for name in (
        "METRICPILOT_DAILY_CAP_USD", "METRICPILOT_TOTAL_CAP_USD")}
    env["METRICPILOT_BUDGET_DB"] = str(path)
    result = subprocess.run(
        [sys.executable, "-c", script, json.dumps(clients)],
        cwd=Path(__file__).resolve().parents[1], env=env,
        capture_output=True, text=True, timeout=20, check=True,
    )
    return json.loads(result.stdout)


def _stored_totals(path):
    with sqlite3.connect(path) as db:
        return db.execute("SELECT COUNT(*), SUM(amount) FROM reservations").fetchone()


def _forbid_quota_io(monkeypatch, shared):
    if shared:
        monkeypatch.setenv("VERCEL", "1")
        monkeypatch.setenv("UPSTASH_REDIS_REST_URL", "https://quota.invalid")
        monkeypatch.setenv("UPSTASH_REDIS_REST_TOKEN", "test-only-placeholder")

    def forbidden(*args, **kwargs):
        pytest.fail("Invalid quota inputs must fail before storage or network access")

    monkeypatch.setattr(budget.sqlite3, "connect", forbidden)
    monkeypatch.setattr(budget.httpx, "post", forbidden)


@pytest.mark.parametrize("shared", [False, True], ids=["local", "shared"])
@pytest.mark.parametrize("amount", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_reservation_is_rejected_before_quota_io(local_budget, monkeypatch, shared, amount):
    _forbid_quota_io(monkeypatch, shared)
    with pytest.raises(budget.BudgetError, match="^Invalid reservation$"):
        budget.reserve(amount=amount)
    assert not local_budget.exists()


@pytest.mark.parametrize("shared", [False, True], ids=["local", "shared"])
@pytest.mark.parametrize("variable", ["METRICPILOT_DAILY_CAP_USD", "METRICPILOT_TOTAL_CAP_USD"])
@pytest.mark.parametrize("value", ["nan", "inf", "-inf", "not-a-number", ""])
def test_invalid_cap_is_rejected_before_quota_io(local_budget, monkeypatch, shared, variable, value):
    monkeypatch.setenv(variable, value)
    _forbid_quota_io(monkeypatch, shared)
    with pytest.raises(budget.BudgetError, match="^Invalid budget configuration$"):
        budget.reserve()
    assert not local_budget.exists()


def test_finite_configured_caps_cannot_raise_thirty_dollar_ceiling(local_budget, monkeypatch):
    monkeypatch.setenv("METRICPILOT_TOTAL_CAP_USD", "1000")
    monkeypatch.setenv("METRICPILOT_DAILY_CAP_USD", "1000")
    budget.reserve(client="earlier-spending")
    with sqlite3.connect(local_budget) as db:
        db.execute("UPDATE reservations SET day='2000-01-01', at=0, amount=29.98")

    budget.reserve(client="last-allowed")
    with pytest.raises(budget.BudgetError, match="budget or rate limit exhausted"):
        budget.reserve(client="over-ceiling")
    count, total = _stored_totals(local_budget)
    assert count == 2
    assert total == pytest.approx(30)


@pytest.mark.parametrize("cap", ["daily", "lifetime"])
def test_budget_cap_survives_process_restart(local_budget, monkeypatch, cap):
    variable = "METRICPILOT_DAILY_CAP_USD" if cap == "daily" else "METRICPILOT_TOTAL_CAP_USD"
    monkeypatch.setenv(variable, "0.04")
    assert _reserve_in_new_process(local_budget, ["first", "second"]) == ["reserved"] * 2

    if cap == "lifetime":
        # Previous-day spending must still consume lifetime allowance.
        with sqlite3.connect(local_budget) as db:
            db.execute("UPDATE reservations SET day='2000-01-01', at=0")

    assert _reserve_in_new_process(local_budget, ["after-restart"]) == ["rejected"]
    count, total = _stored_totals(local_budget)
    assert count == 2
    assert total == pytest.approx(0.04)


def test_client_rate_limit_survives_process_restart(local_budget):
    assert _reserve_in_new_process(local_budget, ["same-client"] * 3) == ["reserved"] * 3
    assert _reserve_in_new_process(local_budget, ["same-client", "another-client"]) == [
        "rejected", "reserved",
    ]
    count, total = _stored_totals(local_budget)
    assert count == 4
    assert total == pytest.approx(0.08)


@pytest.mark.parametrize("limit, expected", [("daily", 4), ("lifetime", 3), ("client", 3)])
def test_concurrent_reservations_are_atomic(local_budget, monkeypatch, limit, expected):
    prior_count = 0
    if limit in ("daily", "lifetime"):
        monkeypatch.setenv("METRICPILOT_DAILY_CAP_USD", "0.08")
        monkeypatch.setenv("METRICPILOT_TOTAL_CAP_USD", "0.10")
    if limit == "lifetime":
        # Only three new reservations fit overall, although four fit today.
        for _ in range(2):
            budget.reserve(client="previous-day")
        with sqlite3.connect(local_budget) as db:
            db.execute("UPDATE reservations SET day='2000-01-01', at=0")
        prior_count = 2

    attempts = 16
    start = Barrier(attempts)

    def reserve(index):
        start.wait(timeout=15)
        client = "same-client" if limit == "client" else f"client-{index}"
        try:
            budget.reserve(client=client)
        except budget.BudgetError:
            return False
        return True

    # Each call opens its own SQLite connection. Simultaneous readers must not
    # all approve against the same stale balance or client request count.
    with ThreadPoolExecutor(max_workers=attempts) as executor:
        accepted = list(executor.map(reserve, range(attempts)))
    assert sum(accepted) == expected
    count, total = _stored_totals(local_budget)
    assert count == prior_count + expected
    assert total == pytest.approx((prior_count + expected) * 0.02)


@pytest.mark.parametrize("failure", ["timeout", "connection", "http_503"])
def test_shared_quota_outage_stops_before_live_provider(local_budget, monkeypatch, failure):
    import backend.agent as agent

    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("UPSTASH_REDIS_REST_URL", "https://quota.invalid")
    monkeypatch.setenv("UPSTASH_REDIS_REST_TOKEN", "test-only-placeholder")
    monkeypatch.setattr(agent, "live_available", lambda: True)

    def forbidden_execution(*args, **kwargs):
        pytest.fail("A quota outage must stop before analytical tools or the model run")

    monkeypatch.setattr(agent, "choose_action", forbidden_execution)
    monkeypatch.setattr(agent, "Analytics", forbidden_execution)
    monkeypatch.setattr(agent, "retrieve", forbidden_execution)

    def unavailable(request):
        if failure == "timeout":
            raise httpx.ReadTimeout("Mock quota timeout", request=request)
        if failure == "connection":
            raise httpx.ConnectError("Mock quota connection failure", request=request)
        return httpx.Response(503, json={"error": "Mock unavailable"})

    with httpx.Client(transport=httpx.MockTransport(unavailable)) as client:
        monkeypatch.setattr(budget.httpx, "post", client.post)
        report = agent.run_analysis(
            "Investigate activation", mode="live",
            dataset={"users": [], "events": [], "cutoff": "2026-09-30"},
        )

    assert report["status"] == "budget_exceeded"
    assert "Shared quota service unavailable" in report["summary"]
    assert report["metrics"]["model_calls"] == 0
    assert report["metrics"]["tool_calls"] == 0
    assert report["metrics"]["estimated_cost_usd"] == 0
    assert report["evidence"] == []
    assert report["findings"] == []
    assert not local_budget.exists(), "Public mode must not fall back to a local quota"
