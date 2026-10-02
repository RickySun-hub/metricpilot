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
    monkeypatch.setenv("METRICPILOT_TOTAL_CAP_USD", "5")

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
@pytest.mark.parametrize("value", ["nan", "inf", "-inf", "not-a-number", "", "0", "-0.01"])
def test_invalid_cap_is_rejected_before_quota_io(local_budget, monkeypatch, shared, variable, value):
    monkeypatch.setenv(variable, value)
    _forbid_quota_io(monkeypatch, shared)
    with pytest.raises(budget.BudgetError, match="^Invalid budget configuration$"):
        budget.reserve()
    assert not local_budget.exists()


def test_finite_configured_caps_cannot_raise_five_dollar_ceiling(local_budget, monkeypatch):
    monkeypatch.setenv("METRICPILOT_TOTAL_CAP_USD", "1000")
    monkeypatch.setenv("METRICPILOT_DAILY_CAP_USD", "1000")
    budget.reserve(client="earlier-spending")
    with sqlite3.connect(local_budget) as db:
        db.execute("UPDATE reservations SET day='2000-01-01', at=0, amount=4.98")

    budget.reserve(client="last-allowed")
    with pytest.raises(budget.BudgetError, match="budget or rate limit exhausted"):
        budget.reserve(client="over-ceiling")
    count, total = _stored_totals(local_budget)
    assert count == 2
    assert total == pytest.approx(5)


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


def test_snapshot_is_read_only_and_uses_safe_defaults(local_budget, monkeypatch):
    monkeypatch.delenv("METRICPILOT_TOTAL_CAP_USD")
    monkeypatch.delenv("METRICPILOT_DAILY_CAP_USD")
    snapshot = budget.budget_snapshot()
    assert snapshot["total_cap_usd"] == 5
    assert snapshot["daily_cap_usd"] == 1
    assert snapshot["total_reserved_usd"] == 0
    assert snapshot["daily_reserved_usd"] == 0
    assert snapshot["total_remaining_usd"] == 5
    assert snapshot["daily_remaining_usd"] == 1
    assert snapshot["reservation_usd"] == 0.02
    assert snapshot["storage_backend"] == "sqlite"
    assert not local_budget.exists()


def test_snapshot_reports_reserved_cost_not_provider_actuals(local_budget):
    budget.reserve(client="previous-day")
    with sqlite3.connect(local_budget) as db:
        db.execute("UPDATE reservations SET day='2000-01-01', at=0")
    budget.reserve(client="today")
    before = local_budget.read_bytes()
    snapshot = budget.budget_snapshot()
    assert snapshot["daily_reserved_usd"] == 0.02
    assert snapshot["total_reserved_usd"] == 0.04
    assert snapshot["daily_remaining_usd"] == 0.98
    assert snapshot["total_remaining_usd"] == 4.96
    assert local_budget.read_bytes() == before


def test_default_ledger_is_repository_local_and_ignored(local_budget, monkeypatch):
    monkeypatch.delenv("METRICPILOT_BUDGET_DB")
    root = Path(budget.__file__).resolve().parents[1]
    assert budget.DEFAULT_BUDGET_DB == root / "artifacts/local/metricpilot-budget-v1.sqlite"
    result = subprocess.run(
        ["git", "check-ignore", str(budget.DEFAULT_BUDGET_DB)], cwd=root,
        capture_output=True, text=True, check=True,
    )
    assert result.stdout.strip()


def test_reserve_creates_missing_persistent_parent_directories(local_budget, monkeypatch):
    nested = local_budget.parent / "local" / "quota" / "budget.sqlite"
    monkeypatch.setenv("METRICPILOT_BUDGET_DB", str(nested))
    budget.reserve()
    assert _stored_totals(nested) == (1, 0.02)


@pytest.mark.parametrize("shared", [False, True], ids=["local", "shared"])
def test_fractional_reservations_round_up_before_cap_comparison(local_budget, monkeypatch, shared):
    monkeypatch.setenv("METRICPILOT_TOTAL_CAP_USD", "0.0000009")
    _forbid_quota_io(monkeypatch, shared)
    with pytest.raises(budget.BudgetError, match="budget or rate limit exhausted"):
        budget.reserve(amount=0.0000001)


def test_storage_errors_fail_closed_with_budget_error(local_budget):
    local_budget.write_text("not a sqlite ledger")
    with pytest.raises(budget.BudgetError, match="Local quota.*unavailable"):
        budget.reserve()
    with pytest.raises(budget.BudgetError, match="Local quota.*unavailable"):
        budget.budget_snapshot()


def test_legacy_default_ledger_migrates_without_resetting_spend(local_budget, monkeypatch):
    budget.reserve(client="old-process")
    before = local_budget.read_bytes()
    target = local_budget.parent / "persistent" / "budget.sqlite"
    monkeypatch.setattr(budget, "LEGACY_BUDGET_DB", local_budget)
    monkeypatch.setattr(budget, "DEFAULT_BUDGET_DB", target)
    monkeypatch.delenv("METRICPILOT_BUDGET_DB")
    assert budget.budget_snapshot()["total_reserved_usd"] == 0.02
    assert not target.exists(), "Read-only snapshot must not run the migration"
    budget.reserve(client="new-process")
    assert _stored_totals(target) == (2, 0.04)
    assert budget.budget_snapshot()["total_reserved_usd"] == 0.04
    assert local_budget.read_bytes() == before


def test_changed_legacy_ledger_after_migration_fails_closed(local_budget, monkeypatch):
    budget.reserve(client="old-process")
    target = local_budget.parent / "persistent" / "budget.sqlite"
    monkeypatch.setattr(budget, "LEGACY_BUDGET_DB", local_budget)
    monkeypatch.setattr(budget, "DEFAULT_BUDGET_DB", target)
    monkeypatch.delenv("METRICPILOT_BUDGET_DB")
    budget.reserve(client="new-process")
    with sqlite3.connect(local_budget) as db:
        db.execute("INSERT INTO reservations VALUES ('2000-01-01', 'old-writer', 0, 0.02)")
    with pytest.raises(budget.BudgetError, match="Legacy.*changed|Ambiguous"):
        budget.reserve(client="would-overspend")
    with pytest.raises(budget.BudgetError, match="Legacy.*changed|Ambiguous"):
        budget.budget_snapshot()
    assert _stored_totals(target) == (2, 0.04)


def test_divergent_existing_ledgers_fail_closed(local_budget, monkeypatch):
    budget.reserve(client="legacy")
    target = local_budget.parent / "other.sqlite"
    monkeypatch.setenv("METRICPILOT_BUDGET_DB", str(target))
    budget.reserve(client="other")
    monkeypatch.setattr(budget, "LEGACY_BUDGET_DB", local_budget)
    monkeypatch.setattr(budget, "DEFAULT_BUDGET_DB", target)
    monkeypatch.delenv("METRICPILOT_BUDGET_DB")
    with pytest.raises(budget.BudgetError, match="Ambiguous"):
        budget.reserve()
    assert _stored_totals(target) == (1, 0.02)


def _use_mock_shared(monkeypatch, handler):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("UPSTASH_REDIS_REST_URL", "https://quota.invalid")
    monkeypatch.setenv("UPSTASH_REDIS_REST_TOKEN", "test-only-placeholder")
    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(budget.httpx, "post", client.post)
    return client


def test_shared_reservation_cannot_collide_with_lifetime_key(local_budget, monkeypatch):
    commands = []

    def quota(request):
        command = json.loads(request.content)
        commands.append(command)
        return httpx.Response(200, json={"result": 1})

    monkeypatch.setenv("METRICPILOT_DAILY_CAP_USD", "1000")
    monkeypatch.setenv("METRICPILOT_TOTAL_CAP_USD", "1000")
    with _use_mock_shared(monkeypatch, quota):
        budget.reserve(client="lifetime")
    command = commands[0]
    assert command[0] == "EVAL"
    assert len(set(command[3:6])) == 3
    assert command[4] == "metricpilot:v1:lifetime", "Preserve existing lifetime counter"
    assert command[-4:] == ["20000", "5000000", "5000000", "3"]
    assert not local_budget.exists()


def test_shared_snapshot_is_read_only_and_reports_existing_reservations(local_budget, monkeypatch):
    commands = []

    def quota(request):
        commands.append(json.loads(request.content))
        return httpx.Response(200, json={"result": ["40000", "4980000"]})

    with _use_mock_shared(monkeypatch, quota):
        snapshot = budget.budget_snapshot()
    assert commands == [["MGET", "metricpilot:v1:" + snapshot["day"], "metricpilot:v1:lifetime"]]
    assert snapshot["storage_backend"] == "redis"
    assert snapshot["daily_reserved_usd"] == 0.04
    assert snapshot["total_reserved_usd"] == 4.98
    assert snapshot["total_remaining_usd"] == 0.02
    assert not local_budget.exists()


@pytest.mark.parametrize("result", [None, {}, True, "1", -1])
def test_invalid_shared_admission_response_fails_closed(local_budget, monkeypatch, result):
    with _use_mock_shared(monkeypatch, lambda request: httpx.Response(200, json={"result": result})):
        with pytest.raises(budget.BudgetError, match="Shared quota service unavailable"):
            budget.reserve()
    assert not local_budget.exists()


@pytest.mark.parametrize("result", [None, {}, ["nan", "2"], ["-1", "2"], ["3", "2"], ["0.2", "2"], [True, 2]])
def test_invalid_shared_snapshot_fails_closed(local_budget, monkeypatch, result):
    with _use_mock_shared(monkeypatch, lambda request: httpx.Response(200, json={"result": result})):
        with pytest.raises(budget.BudgetError, match="Shared quota service unavailable"):
            budget.budget_snapshot()
    assert not local_budget.exists()


@pytest.mark.parametrize("method", ["reserve", "budget_snapshot"])
@pytest.mark.parametrize("payload", [{"error": "ERR mocked server error"}, {}, []])
def test_invalid_shared_envelope_fails_closed(local_budget, monkeypatch, method, payload):
    with _use_mock_shared(monkeypatch, lambda request: httpx.Response(200, json=payload)):
        with pytest.raises(budget.BudgetError, match="Shared quota service unavailable"):
            getattr(budget, method)()
    assert not local_budget.exists()


def test_local_exact_microdollars_allow_only_five_dollars(local_budget, monkeypatch):
    monkeypatch.setenv("METRICPILOT_DAILY_CAP_USD", "5")
    for index in range(250):
        budget.reserve(client=f"client-{index}")
    with pytest.raises(budget.BudgetError, match="budget or rate limit exhausted"):
        budget.reserve(amount=0.0000001, client="over-cap")
    assert budget.budget_snapshot()["total_reserved_usd"] == 5
    assert budget.budget_snapshot()["total_remaining_usd"] == 0


def test_submicrodollar_reservations_are_not_free(local_budget):
    budget.reserve(amount=0.0000001)
    assert budget.budget_snapshot()["total_reserved_usd"] == 0.000001
    assert _stored_totals(local_budget) == (1, 0.000001)


@pytest.mark.parametrize("amount", [-1, None, "nan", "inf", "not-a-number"])
def test_invalid_stored_amount_fails_closed(local_budget, amount):
    budget.reserve()
    with sqlite3.connect(local_budget) as db:
        db.execute("UPDATE reservations SET amount=?", [amount])
    with pytest.raises(budget.BudgetError, match="Local quota ledger unavailable"):
        budget.reserve()
    with pytest.raises(budget.BudgetError, match="Local quota ledger unavailable"):
        budget.budget_snapshot()


def test_concurrent_legacy_migration_imports_history_exactly_once(local_budget, monkeypatch):
    budget.reserve(client="legacy")
    target = local_budget.parent / "persistent" / "budget.sqlite"
    monkeypatch.setattr(budget, "LEGACY_BUDGET_DB", local_budget)
    monkeypatch.setattr(budget, "DEFAULT_BUDGET_DB", target)
    monkeypatch.delenv("METRICPILOT_BUDGET_DB")
    monkeypatch.setenv("METRICPILOT_TOTAL_CAP_USD", "0.10")
    start = Barrier(12)

    def attempt(index):
        start.wait(timeout=15)
        try:
            budget.reserve(client=f"migrate-{index}")
        except budget.BudgetError:
            return False
        return True

    with ThreadPoolExecutor(max_workers=12) as executor:
        assert sum(executor.map(attempt, range(12))) == 4
    count, total = _stored_totals(target)
    assert count == 5
    assert total == pytest.approx(0.10)
    assert _stored_totals(local_budget) == (1, 0.02)


def test_default_ledger_survives_new_processes_and_working_directories(local_budget, monkeypatch):
    # Copy only this module to an isolated repo so the real project ledger remains
    # untouched. No env override selects the ledger in either subprocess.
    root = local_budget.parent / "isolated-repo"
    (root / "backend").mkdir(parents=True)
    (root / "backend" / "__init__.py").write_text("")
    (root / "backend" / "budget.py").write_bytes(Path(budget.__file__).read_bytes())
    other_cwd = root / "other-cwd"
    other_cwd.mkdir()
    env = {"PYTHONPATH": str(root), "METRICPILOT_TOTAL_CAP_USD": "0.02",
           "METRICPILOT_DAILY_CAP_USD": "1", "TMPDIR": str(root)}
    first = subprocess.run(
        [sys.executable, "-c", "from backend.budget import reserve; reserve()"],
        cwd=root, env=env, capture_output=True, text=True, check=True, timeout=20,
    )
    assert not first.stderr
    second = subprocess.run(
        [sys.executable, "-c", "from backend.budget import reserve; reserve()"],
        cwd=other_cwd, env=env, capture_output=True, text=True, timeout=20,
    )
    assert second.returncode != 0
    assert "Live request budget or rate limit exhausted" in second.stderr
    assert _stored_totals(root / "artifacts/local/metricpilot-budget-v1.sqlite") == (1, 0.02)


def test_configured_shared_quota_is_used_outside_vercel(local_budget, monkeypatch):
    commands = []

    def quota(request):
        command = json.loads(request.content)
        commands.append(command)
        result = 1 if command[0] == "EVAL" else ["20000", "20000"]
        return httpx.Response(200, json={"result": result})

    with _use_mock_shared(monkeypatch, quota):
        monkeypatch.delenv("VERCEL")
        budget.reserve(client="local-evaluation")
        snapshot = budget.budget_snapshot()
    assert [command[0] for command in commands] == ["EVAL", "MGET"]
    assert commands[0][4] == commands[1][2] == "metricpilot:v1:lifetime"
    assert snapshot["storage_backend"] == "redis"
    assert snapshot["total_reserved_usd"] == 0.02
    assert not local_budget.exists(), "Configured shared accounting must never fall back to SQLite"


@pytest.mark.parametrize("configuration", [
    {"UPSTASH_REDIS_REST_URL": "https://quota.invalid"},
    {"UPSTASH_REDIS_REST_TOKEN": "test-only-placeholder"},
    {"UPSTASH_REDIS_REST_URL": ""},
    {"UPSTASH_REDIS_REST_TOKEN": ""},
    {"UPSTASH_REDIS_REST_URL": "", "UPSTASH_REDIS_REST_TOKEN": ""},
])
def test_partial_shared_configuration_fails_closed_outside_vercel(local_budget, monkeypatch, configuration):
    for name, value in configuration.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-placeholder")
    monkeypatch.setenv("METRICPILOT_ENABLE_LIVE", "1")
    assert not budget.live_available()
    for operation in (budget.reserve, budget.budget_snapshot):
        with pytest.raises(budget.BudgetError, match="requires durable shared quota accounting"):
            operation()
    assert not local_budget.exists()
