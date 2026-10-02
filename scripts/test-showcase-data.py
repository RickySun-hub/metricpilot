#!/usr/bin/env python3
"""Offline regression checks for the public, recorded dashboard data."""

import copy
from datetime import datetime
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "evals" / "results"
BUILD_SCRIPT = ROOT / "scripts" / "build-showcase-data.py"
GENERATED_AT = "2026-10-02T06:00:00+00:00"
REPORT_FIELDS = {
    "question", "mode", "status", "summary", "retrieval", "evidence", "trace",
    "findings", "warnings", "metrics", "claims", "citations", "generation",
    "request_id", "model", "dataset",
}
METRIC_FIELDS = {
    "elapsed_ms", "model_calls", "tool_calls", "input_tokens", "output_tokens",
    "estimated_cost_usd", "cost_basis",
}
FORBIDDEN_KEYS = {
    "budget_before", "budget_after", "reservation", "reservation_usd",
    "reserved_request_usd", "reserved_model_cost_usd", "provider_configuration",
    "provider_error", "raw_response", "raw_provider_response", "api_key",
    "access_token", "authorization", "password",
}


def read_source(name):
    return json.loads((RESULTS / name).read_text())


def development_retail_entry():
    source = read_source("live-development-v3_1-20261002.json")
    return next(case["systems"]["agent"] for run in source["runs"]
                for case in run["cases"] if case["id"] == "retail-live-02")


def all_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from all_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from all_keys(child)


class ShowcaseDataTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(BUILD_SCRIPT.exists(), "The offline showcase builder is missing")
        spec = importlib.util.spec_from_file_location("showcase_builder", BUILD_SCRIPT)
        self.builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.builder)

    def build(self, directory=RESULTS):
        return self.builder.build_showcase(directory, generated_at=GENERATED_AT)

    def test_report_allowlist_preserves_actual_claims_sql_and_values(self):
        data = self.build()
        self.assertEqual(data["generated_at"], GENERATED_AT)
        self.assertEqual(len(data["records"]), 3)
        for record, filename, source in zip(
            data["records"],
            ["live-smoke-20261002.json", "live-development-v3_1-20261002.json", "retail.json"],
            [read_source("live-smoke-20261002.json")["response"], development_retail_entry()["response"], read_source("retail.json")["execution"]],
        ):
            report = record["report"]
            self.assertEqual(set(report), REPORT_FIELDS)
            self.assertEqual(set(report["metrics"]), set(source["metrics"]) & METRIC_FIELDS)
            for key in REPORT_FIELDS - {"metrics"}:
                self.assertEqual(report[key], source[key], key)
            for key in report["metrics"]:
                self.assertEqual(report["metrics"][key], source["metrics"][key])
            self.assertEqual(record["source_path"], f"evals/results/{filename}")
        self.assertEqual(data["records"][0]["report"]["evidence"][0]["result"]["before"]["completed"], 3373)
        self.assertEqual(data["records"][2]["report"]["evidence"][0]["result"]["delta_gbp"], 354517.03)

    def test_citation_targets_and_finding_paths_exist(self):
        for record in self.build()["records"]:
            report = record["report"]
            evidence = {item["id"]: item for item in report["evidence"]}
            contracts = {item["id"] for item in report["retrieval"]}
            for citation in report["citations"]:
                target = evidence if citation["kind"] == "evidence" else contracts
                self.assertIn(citation["id"], target)
            for claim in report["claims"]:
                self.assertTrue(set(claim["evidence_ids"]) <= evidence.keys())
                self.assertTrue(set(claim["contract_ids"]) <= contracts)
            for finding in report["findings"]:
                value = evidence[finding["evidence_id"]]["result"]
                for part in finding["field_path"].split("."):
                    value = value[int(part)] if isinstance(value, list) else value[part]
                self.assertAlmostEqual(value * finding["scale"], finding["value"])

    def test_smoke_date_is_day_precision_without_invented_time(self):
        smoke, _, retail = self.build()["records"]
        self.assertEqual(smoke["recorded_at"], "2026-10-02")
        self.assertEqual(smoke["recorded_at_precision"], "day")
        self.assertEqual(retail["recorded_at"], read_source("retail.json")["run_at_utc"])
        self.assertEqual(retail["recorded_at_precision"], "timestamp")
        self.assertIn("AI-assisted", smoke["review_note"])
        self.assertIn("not a human review", smoke["review_note"])
        self.assertIn("not a benchmark", smoke["review_note"])

    def test_no_sensitive_ledger_or_provider_fields_are_published(self):
        self.assertFalse(set(all_keys(self.build())) & FORBIDDEN_KEYS)
        source = copy.deepcopy(read_source("live-smoke-20261002.json")["response"])
        for key in FORBIDDEN_KEYS:
            source[key] = "PRIVATE_MARKER"
            source["dataset"][key] = "PRIVATE_MARKER"
            source["evidence"][0]["result"][key] = "PRIVATE_MARKER"
            source["metrics"][key] = "PRIVATE_MARKER"
        source["unapproved_top_level"] = "PRIVATE_MARKER"
        source["metrics"]["unapproved_metric"] = "PRIVATE_MARKER"
        sanitized = self.builder.sanitize_report(source)
        self.assertFalse(set(all_keys(sanitized)) & FORBIDDEN_KEYS)
        self.assertNotIn("PRIVATE_MARKER", json.dumps(sanitized))
        self.assertEqual(set(sanitized), REPORT_FIELDS)

    def test_failed_response_cannot_become_successful_showcase(self):
        source = copy.deepcopy(read_source("live-smoke-20261002.json")["response"])
        source["status"] = "provider_error"
        source["summary"] = "PRIVATE_PROVIDER_ERROR"
        with self.assertRaises(ValueError):
            self.builder.sanitize_report(source)

    def test_successful_boundary_is_not_described_as_failed(self):
        reason = self.builder.case_reason({
            "status": "clarification_required",
            "automatic_pass": True,
            "checks": {"whole_task_pass": True},
        })
        self.assertEqual(reason, "Whole-task checks passed in the recorded evaluation.")

    def test_development_live_retail_record_is_exact_and_clearly_scoped(self):
        data = self.build()
        self.assertEqual([record["id"] for record in data["records"]], [
            "recorded-live-funnel", "recorded-live-retail", "recorded-retail-country",
        ])
        record = data["records"][1]
        source = read_source("live-development-v3_1-20261002.json")
        entry = development_retail_entry()
        report = entry["response"]
        self.assertEqual(record["title"], "Retail sales · live model")
        self.assertEqual(record["dataset"], "retail")
        self.assertEqual(record["source_path"], "evals/results/live-development-v3_1-20261002.json")
        self.assertEqual(record["recorded_at"], source["run_at_utc"])
        self.assertEqual(record["recorded_at_precision"], "timestamp")
        self.assertIn("Development-only", record["review_note"])
        self.assertIn("not a benchmark", record["review_note"])
        self.assertIn("Human semantic review status: required", record["review_note"])
        self.assertIn("unscored", record["review_note"])
        for key in REPORT_FIELDS - {"metrics"}:
            self.assertEqual(record["report"][key], report[key], key)
        self.assertEqual(record["report"]["generation"]["schema_version"], "3.1")
        self.assertEqual(record["report"]["generation"]["numeric_validation_scope"], report["generation"]["numeric_validation_scope"])
        self.assertEqual(data["records"][2]["title"], "Retail sales · tools only")
        self.assertTrue(all("development" not in run["source_path"] for run in data["verification"]["live_runs"]))

    def test_unfinished_development_sample_is_not_published(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for filename in ["live-smoke-20261002.json", "retail.json", "deterministic-rag-20261002.json", "retrieval.json"]:
                (root / filename).write_text((RESULTS / filename).read_text())
            development = read_source("live-development-v3_1-20261002.json")
            development["execution_status"] = "running"
            (root / "live-development-v3_1-20261002.json").write_text(json.dumps(development))
            with self.assertRaises(ValueError):
                self.build(root)

    def test_verification_measures_are_copied_with_separate_scopes(self):
        verification = self.build()["verification"]
        deterministic = read_source("deterministic-rag-20261002.json")
        self.assertEqual(verification["deterministic"]["runs"], [
            {key: run[key] for key in ["repeat", "passed", "total"]}
            for run in deterministic["runs"]
        ])
        self.assertEqual(verification["deterministic"]["passed"], deterministic["passed"])
        self.assertEqual(verification["deterministic"]["scope"], deterministic["scope"])
        retrieval = read_source("retrieval.json")
        for key in ["scope", "total", "semantic_top1_hits", "semantic_top3_hits", "lexical_top1_hits", "lexical_top3_hits"]:
            self.assertEqual(verification["retrieval"][key], retrieval[key])
        retail = read_source("retail.json")
        self.assertEqual(verification["retail"]["check_count"], retail["check_count"])
        self.assertEqual(verification["retail"]["passed"], retail["passed"])

    def test_every_completed_live_artifact_is_linked_without_review_templates(self):
        expected = set()
        for path in RESULTS.glob("live-synthetic-*.json"):
            try:
                artifact = json.loads(path.read_text())
            except json.JSONDecodeError:
                continue
            if artifact.get("execution_status") == "completed" and artifact.get("completed_at_utc"):
                expected.add(f"evals/results/{path.name}")
        live_runs = self.build()["verification"]["live_runs"]
        self.assertEqual({run["source_path"] for run in live_runs}, expected)
        for run in live_runs:
            self.assertFalse(run["source_path"].endswith(".review.json"))

    def test_stopped_attempt_is_not_reported_as_passed(self):
        source = read_source("live-synthetic-20261002.json")
        run = next(run for run in self.build()["verification"]["live_runs"]
                   if run["source_path"] == "evals/results/live-synthetic-20261002.json")
        self.assertEqual(run["status"], "stopped")
        self.assertEqual(run["planned"], 180)
        self.assertEqual(run["attempted"], 9)
        self.assertEqual(run["gate"], source["release_gate"])
        self.assertNotEqual(run["gate"]["status"], "passed")
        self.assertEqual(run["stop_reason"], source["stop_reason"])
        self.assertEqual(run["estimated_cost_usd"], source["summary"]["estimated_cost_usd"])
        self.assertEqual(sum(system["automatic_passes"] for system in run["systems"]), 3)
        self.assertEqual(sum(system["whole_task_passes"] for system in run["systems"]), 0)
        self.assertEqual(sum(system["manual_reviews_pending"] for system in run["systems"]), 3)
        self.assertEqual(len(run["cases"]), 180)
        self.assertEqual(sum(not case["status"].startswith("not_run") for case in run["cases"]), 9)
        self.assertTrue(any(case["whole_task_pass"] is None for case in run["cases"]))
        self.assertTrue(all(case["whole_task_pass"] is not True for case in run["cases"]))
        for system in run["systems"]:
            self.assertEqual(system["latency_ms"], source["summary_by_system"][system["name"]]["latency_ms"])

    def test_latest_terminal_synthetic_run_is_explicit_primary_without_retry_totals(self):
        verification = self.build()["verification"]
        self.assertIn("primary_live_run_id", list(verification))
        self.assertEqual(verification["primary_live_run_id"], "live-synthetic-v3-20261002")
        runs = verification["live_runs"]
        self.assertEqual({run["id"] for run in runs}, {
            "live-synthetic-20261002", "live-synthetic-v2-resumed-20261002",
            "live-synthetic-v3-20261002",
        })
        primary = next(run for run in runs if run["id"] == verification["primary_live_run_id"])
        self.assertEqual(primary["id"], max(runs, key=lambda run: datetime.fromisoformat(run["run_at"]))["id"])
        self.assertEqual(primary["planned"], 180)
        self.assertEqual(primary["attempted"], 10)
        self.assertEqual(primary["automatic_passes"], 7)
        self.assertEqual(primary["unrun"], 170)
        self.assertEqual(len(primary["cases"]), 180)
        self.assertEqual(sum(case["status"] == "verification_failed" for case in primary["cases"]), 3)

    def test_each_live_summary_has_its_own_track_scope_and_measured_counts(self):
        verification = self.build()["verification"]
        self.assertIn("supplemental_runs", list(verification))
        for run in verification["live_runs"] + verification["supplemental_runs"]:
            source = read_source(Path(run["source_path"]).name)
            self.assertEqual(run["track"], source["track"])
            self.assertEqual(run["scope"], source["scope"])
            self.assertEqual(run["unrun"], source["planned_response_count"] - source["attempted_response_count"])
            self.assertEqual(run["automatic_passes"], sum(system["automatic_passes"] for system in source["summary_by_system"].values()))
            self.assertEqual(len(run["cases"]), run["planned"])

    def test_supplements_include_only_terminal_retail_and_adversarial_tracks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for filename in ["live-smoke-20261002.json", "retail.json", "deterministic-rag-20261002.json", "retrieval.json", "live-development-v3_1-20261002.json"]:
                (root / filename).write_text((RESULTS / filename).read_text())
            for track, status in [("retail", "completed"), ("adversarial", "completed"), ("retail", "running"), ("development", "completed"), ("unknown", "completed")]:
                source = read_source("live-synthetic-v3-20261002.json")
                source["track"] = track
                source["execution_status"] = status
                (root / f"live-fixture-{track}-{status}.json").write_text(json.dumps(source))
            verification = self.build(root)["verification"]
            self.assertIn("supplemental_runs", list(verification))
            supplements = verification["supplemental_runs"]
            self.assertEqual({run["track"] for run in supplements}, {"retail", "adversarial"})
            self.assertEqual(len(supplements), 2)
            self.assertEqual(verification["live_runs"], [])
            self.assertIsNone(verification["primary_live_run_id"])
            self.assertTrue(all(run["automatic_passes"] == 7 for run in supplements))
            self.assertFalse(set(all_keys(verification)) & FORBIDDEN_KEYS)

    def test_primary_selection_uses_timestamp_not_filename_or_string_order(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for filename in ["live-smoke-20261002.json", "retail.json", "deterministic-rag-20261002.json", "retrieval.json", "live-development-v3_1-20261002.json"]:
                (root / filename).write_text((RESULTS / filename).read_text())
            for name, run_at in [("a-latest", "2026-10-02T07:00:00+00:00"), ("z-earlier", "2026-10-02T10:00:00+04:00")]:
                source = read_source("live-synthetic-v3-20261002.json")
                source["run_at_utc"] = run_at
                (root / f"live-synthetic-{name}.json").write_text(json.dumps(source))
            verification = self.build(root)["verification"]
            self.assertEqual(verification.get("primary_live_run_id"), "live-synthetic-a-latest")

    def test_blocked_supplements_publish_only_recorded_status_metadata(self):
        verification = self.build()["verification"]
        self.assertIn("supplemental_status", list(verification))
        statuses = verification["supplemental_status"]
        self.assertEqual({status["track"] for status in statuses}, {"retail", "adversarial"})
        self.assertEqual(len(statuses), 2)
        self.assertEqual(verification["supplemental_runs"], [])
        for status in statuses:
            self.assertEqual(set(status), {"track", "status", "planned", "recorded", "source_path", "reason"})
            source = read_source(f"live-{status['track']}-v3-20261002.json")
            self.assertEqual(status["source_path"], f"evals/results/live-{status['track']}-v3-20261002.json")
            self.assertEqual(status["status"], "execution_blocked")
            self.assertEqual(status["planned"], source["planned_response_count"])
            self.assertEqual(status["recorded"], source["recorded_response_count"])
            self.assertEqual(status["recorded"], 0)
            self.assertEqual(status["reason"], source["stop_reason"]["note"])
            self.assertNotIn("attempted", status)
            self.assertNotIn("model_calls", status)
        self.assertEqual({status["track"]: status["planned"] for status in statuses}, {"retail": 8, "adversarial": 12})
        self.assertFalse(set(all_keys(statuses)) & FORBIDDEN_KEYS)

    def test_in_progress_and_invalid_live_files_are_skipped(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for filename in ["live-smoke-20261002.json", "retail.json", "deterministic-rag-20261002.json", "retrieval.json", "live-development-v3_1-20261002.json"]:
                (root / filename).write_text((RESULTS / filename).read_text())
            (root / "live-synthetic-invalid.json").write_text('{"unfinished":')
            running = copy.deepcopy(read_source("live-synthetic-20261002.json"))
            running["execution_status"] = "running"
            (root / "live-synthetic-running.json").write_text(json.dumps(running))
            unfinished = copy.deepcopy(running)
            unfinished["execution_status"] = "completed"
            unfinished.pop("completed_at_utc")
            (root / "live-synthetic-unfinished.json").write_text(json.dumps(unfinished))
            self.assertEqual(self.build(root)["verification"]["live_runs"], [])

    def test_generated_artifact_matches_current_sources(self):
        path = ROOT / "app" / "data" / "showcase.json"
        self.assertTrue(path.exists(), "The generated static showcase artifact is missing")
        actual = json.loads(path.read_text())
        expected = self.builder.build_showcase(RESULTS, generated_at=actual["generated_at"])
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
