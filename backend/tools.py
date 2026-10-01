"""Allowlisted analytics. The model never supplies SQL identifiers or executable SQL."""
from __future__ import annotations

import csv
import tempfile
import time
import uuid
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path

import duckdb

from .data import AFTER, BEFORE, dataset_hash, default_dataset, validate_dataset
from .statistics import newcombe, srm_pvalue


class ToolError(ValueError):
    pass


COHORT_SQL = """WITH starts AS (
  SELECT e.user_id, e.practice_session_id, MIN(e.event_at) AS started_at
  FROM events e JOIN users u USING(user_id)
  WHERE e.event_type='practice_start' AND e.practice_session_id <> ''
    AND e.event_at >= u.signup_at AND e.event_at < u.signup_at + INTERVAL 7 DAY
  GROUP BY e.user_id, e.practice_session_id
), completions AS (
  SELECT DISTINCT e.user_id FROM events e
  JOIN starts s ON e.user_id=s.user_id AND e.practice_session_id=s.practice_session_id
  JOIN users u ON e.user_id=u.user_id
  WHERE e.event_type='practice_complete' AND e.event_at >= s.started_at
    AND e.event_at < u.signup_at + INTERVAL 7 DAY
), cohort AS (
  SELECT u.*, CASE WHEN EXISTS(SELECT 1 FROM starts s WHERE s.user_id=u.user_id) THEN 1 ELSE 0 END AS started,
    CASE WHEN c.user_id IS NOT NULL THEN 1 ELSE 0 END AS completed
  FROM users u LEFT JOIN completions c USING(user_id)
  WHERE u.signup_at >= CAST(? AS TIMESTAMP) AND u.signup_at < CAST(? AS TIMESTAMP)
    AND u.signup_at + INTERVAL 7 DAY <= CAST(? AS TIMESTAMP)
) """


class Analytics:
    def __init__(self, dataset: dict | None = None):
        self.data = dataset if dataset is not None else default_dataset()
        try:
            validate_dataset(self.data)
        except ValueError as exc:
            raise ToolError(str(exc)) from exc
        self.hash = self.data.get("hash") or dataset_hash(self.data)
        self.db = duckdb.connect(":memory:")
        self.db.execute("SET threads=1")
        # CSV import avoids per-row insert latency and infers no types from untrusted input.
        schemas = {"users": "user_id VARCHAR, signup_at TIMESTAMP, acquisition_channel VARCHAR, signup_device VARCHAR",
                   "events": "event_id VARCHAR, user_id VARCHAR, event_at TIMESTAMP, event_type VARCHAR, practice_session_id VARCHAR",
                   "experiment_assignments": "experiment_id VARCHAR, user_id VARCHAR, variant VARCHAR, assigned_at TIMESTAMP, expected_allocation DOUBLE"}
        with tempfile.TemporaryDirectory(prefix="metricpilot-") as directory:
            for table, schema in schemas.items():
                self.db.execute(f"CREATE TABLE {table} ({schema})")
                rows = self.data[table]
                if rows:
                    file = Path(directory) / f"{table}.csv"
                    fields = [part.strip().split()[0] for part in schema.split(",")]
                    with file.open("w", newline="", encoding="utf-8") as f:
                        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
                        writer.writeheader()
                        writer.writerows(rows)
                    self.db.execute(f"COPY {table} FROM ? (HEADER, DELIMITER ',')", [str(file)])
        # Runtime analytical SQL is fixed and SELECT-only; no public arbitrary query interface.
        self.db.execute("SET enable_external_access=false")

    def close(self):
        self.db.close()

    def _windows(self, before=BEFORE, after=AFTER):
        try:
            b0, b1, a0, a1 = map(datetime.fromisoformat, (*before, *after))
            cutoff = datetime.fromisoformat(self.data["cutoff"])
        except (TypeError, ValueError) as exc:
            raise ToolError("Invalid ISO windows") from exc
        if not (b0 < b1 <= a0 < a1) or a1 - a0 > timedelta(days=31) or b1 - b0 > timedelta(days=31):
            raise ToolError("Use ordered, non-overlapping windows of at most 31 days")
        if a1 + timedelta(days=7) > cutoff:
            raise ToolError("Comparison contains an immature cohort")
        return before, after

    def _record(self, tool, args, sql, result, started, warnings=None):
        return {"id": f"ev_{uuid.uuid4().hex[:10]}", "tool": tool, "args": args, "sql": sql,
                "result": result, "warnings": warnings or [], "elapsed_ms": round((time.perf_counter()-started)*1000, 2),
                "dataset_hash": self.hash, "contract_version": "1.0"}

    def _counts(self, window):
        sql = COHORT_SQL + "SELECT COUNT(*) denominator, COALESCE(SUM(started),0) started, COALESCE(SUM(completed),0) numerator FROM cohort"
        n, started, completed = self.db.execute(sql, [*window, self.data["cutoff"]]).fetchone()
        if not n:
            raise ToolError("No eligible users in comparison window")
        return {"numerator": completed, "denominator": n, "rate": completed/n, "started": started}, sql

    def compare_metric(self, before=BEFORE, after=AFTER):
        start = time.perf_counter()
        self._windows(before, after)
        b, sql = self._counts(before)
        a, _ = self._counts(after)
        return self._record("compare_metric", {"metric": "activation", "before": before, "after": after, "cutoff": self.data["cutoff"]}, sql,
                            {"before": b, "after": a, "delta_pp": (a["rate"]-b["rate"])*100}, start)

    def analyze_funnel(self, before=BEFORE, after=AFTER):
        start = time.perf_counter()
        self._windows(before, after)
        b, sql = self._counts(before)
        a, _ = self._counts(after)
        def funnel(c):
            return {"users": c["denominator"], "started": c["started"], "completed": c["numerator"],
                    "start_rate": c["started"]/c["denominator"], "completion_rate": c["rate"],
                    "conditional_completion_rate": c["numerator"]/c["started"] if c["started"] else None}
        return self._record("analyze_funnel", {"before": before, "after": after, "cutoff": self.data["cutoff"]}, sql,
                            {"before": funnel(b), "after": funnel(a)}, start)

    def decompose_change(self, segment="acquisition_channel", before=BEFORE, after=AFTER):
        start = time.perf_counter()
        self._windows(before, after)
        if segment not in ("acquisition_channel", "signup_device"):
            raise ToolError("Unsupported segmentation dimension")
        sql = COHORT_SQL + f"SELECT {segment}, COUNT(*), COALESCE(SUM(completed),0) FROM cohort GROUP BY {segment} ORDER BY {segment}"
        groups = [{g: (n, c) for g, n, c in self.db.execute(sql, [*w, self.data["cutoff"]]).fetchall()} for w in (before, after)]
        if set(groups[0]) != set(groups[1]) or not groups[0]:
            raise ToolError("A segment has no denominator in one period")
        totals = [sum(n for n, _ in group.values()) for group in groups]
        rows = []
        for g in sorted(groups[0]):
            (nb, cb), (na, ca) = groups[0][g], groups[1][g]
            wb, wa, rb, ra = nb/totals[0], na/totals[1], cb/nb, ca/na
            rows.append({"segment": g, "before_rate": rb, "after_rate": ra, "before_weight": wb, "after_weight": wa,
                         "mix_pp": (wa-wb)*(ra+rb)/2*100, "within_pp": (ra-rb)*(wa+wb)/2*100})
        mix, within = sum(r["mix_pp"] for r in rows), sum(r["within_pp"] for r in rows)
        return self._record("decompose_change", {"segment": segment, "before": before, "after": after, "cutoff": self.data["cutoff"]}, sql,
                            {"segments": rows, "mix_pp": mix, "within_pp": within, "delta_pp": mix+within}, start,
                            ["Descriptive accounting decomposition; not a causal estimate."])

    def check_experiment(self, experiment_id="onboarding_valid"):
        start = time.perf_counter()
        if experiment_id not in ("onboarding_valid", "onboarding_srm"):
            raise ToolError("Unknown experiment")
        sql = """WITH eligible AS (
 SELECT a.* FROM experiment_assignments a WHERE experiment_id=?
 AND assigned_at + INTERVAL 7 DAY <= CAST(? AS TIMESTAMP)
), outcomes AS (
 SELECT a.user_id, a.variant, MAX(CASE WHEN e.event_type='practice_complete'
 AND e.event_at >= a.assigned_at AND e.event_at < a.assigned_at + INTERVAL 7 DAY THEN 1 ELSE 0 END) success
 FROM eligible a LEFT JOIN events e ON e.user_id=a.user_id GROUP BY a.user_id,a.variant
) SELECT variant,COUNT(*),SUM(success) FROM outcomes GROUP BY variant"""
        rows = {v: {"n": n, "successes": c, "rate": c/n} for v, n, c in self.db.execute(sql, [experiment_id, self.data["cutoff"]]).fetchall()}
        if set(rows) != {"control", "treatment"}:
            raise ToolError("Missing experiment variant or mature assignments")
        c, t = rows["control"], rows["treatment"]
        p = srm_pvalue(c["n"], t["n"])
        invalid = p < 0.001
        low, high = newcombe(c["successes"], c["n"], t["successes"], t["n"])
        result = {"experiment_id": experiment_id, "status": "invalid" if invalid else "valid", "control": c, "treatment": t,
                  "srm_pvalue": p, "srm_threshold": 0.001, "effect_pp": (t["rate"]-c["rate"])*100,
                  "ci_low_pp": None if invalid else low*100, "ci_high_pp": None if invalid else high*100,
                  "conclusion": "Assignment imbalance: investigate before interpreting effect." if invalid else
                  "Inconclusive: the interval includes zero; this is not proof of no effect." if low <= 0 <= high else
                  "The interval excludes zero; assess practical value and guardrails before a rollout."}
        return self._record("check_experiment", {"experiment_id": experiment_id, "cutoff": self.data["cutoff"]}, sql, result, start,
                            ["Fixed-horizon, one binary outcome; unmeasured guardrails prevent an automatic ship decision."])


@lru_cache(maxsize=1)
def default_analytics():
    return Analytics()
