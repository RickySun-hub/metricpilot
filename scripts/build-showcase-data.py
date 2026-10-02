#!/usr/bin/env python3
"""Publish an offline, sanitized snapshot of measured MetricPilot artifacts.

This script reads only the named local result artifacts. It does not import the
backend, read local configuration, regenerate evaluations, or call a provider.
Run it again after a live evaluation has written its terminal result.
"""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import tempfile


ROOT = Path(__file__).resolve().parents[1]
REPORT_FIELDS = (
    "question", "mode", "status", "summary", "retrieval", "evidence", "trace",
    "findings", "warnings", "metrics", "claims", "citations", "generation",
    "request_id", "model", "dataset",
)
METRIC_FIELDS = (
    "elapsed_ms", "model_calls", "tool_calls", "input_tokens", "output_tokens",
    "estimated_cost_usd", "cost_basis",
)
PRIVATE_KEYS = {
    "api_key", "access_token", "authorization", "password", "credentials",
    "secret", "headers", "request_headers", "error", "errors", "raw_response",
    "raw_provider_response", "provider_configuration", "provider_error",
    "provider_response", "last_provider_http_status", "uncertain_usage_calls",
}


def public_copy(value):
    """Copy public aggregates while dropping private operational metadata keys."""
    if isinstance(value, dict):
        return {
            key: public_copy(child)
            for key, child in value.items()
            if key.lower() not in PRIVATE_KEYS
            and not key.lower().startswith(("budget", "reservation", "reserved_", "provider_"))
        }
    if isinstance(value, list):
        return [public_copy(child) for child in value]
    return value


def pick(value, fields):
    return {field: public_copy(value[field]) for field in fields if field in value}


def sanitize_report(report):
    """Allowlist successful public reports, preserving recorded content verbatim."""
    if report.get("status") != "completed":
        raise ValueError("Only completed successful reports may be published as showcase records")
    result = pick(report, REPORT_FIELDS)
    result["metrics"] = pick(report["metrics"], METRIC_FIELDS)
    return result


def read_json(path):
    """Reject an artifact that changes during the read, rather than mixing runs."""
    before = path.stat()
    text = path.read_text(encoding="utf-8")
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError(f"Result artifact is still changing: {path.name}")
    return json.loads(text)


def source_path(path):
    return f"evals/results/{path.name}"


def case_reason(entry):
    """Describe the measured outcome without copying raw provider error text."""
    status = entry["status"]
    checks = entry.get("checks", {})
    if status.startswith("not_run"):
        return "Not attempted after the run stopped."
    if checks.get("whole_task_pass") is True:
        return "Whole-task checks passed in the recorded evaluation."
    if checks.get("whole_task_pass") is None and entry.get("automatic_pass"):
        return "Automatic checks passed; semantic review remains pending."
    if status == "verification_failed":
        return "Automatic grounding verification rejected this response."
    if status != "completed":
        return "The recorded attempt did not complete successfully."
    return "The recorded whole-task checks did not pass."


def summarize_live(path, data):
    summary = data["summary"]
    planned = data["planned_response_count"]
    attempted = data["attempted_response_count"]
    stopped = attempted < planned or data.get("budget_stop") or data.get("provider_stop")
    cases = [
        {
            "id": case["id"],
            "repeat": run["repeat"],
            "system": system,
            "status": entry["status"],
            "automatic_pass": entry["automatic_pass"],
            "whole_task_pass": entry.get("checks", {}).get("whole_task_pass"),
            "reason": case_reason(entry),
        }
        for run in data["runs"]
        for case in run["cases"]
        for system, entry in case["systems"].items()
    ]
    systems = [
        {
            "name": name,
            **pick(system, (
                "planned", "attempted", "automatic_passes", "whole_task_passes",
                "manual_reviews_pending", "estimated_cost_usd",
            )),
            "latency_ms": pick(system.get("latency_ms", {}), ("mean", "median", "p95")),
        }
        for name, system in data["summary_by_system"].items()
    ]
    stop = data.get("stop_reason")
    return {
        "id": path.stem,
        "run_at": data["run_at_utc"],
        "source_path": source_path(path),
        "track": data["track"],
        "scope": data["scope"],
        "status": "stopped" if stopped else data["execution_status"],
        "planned": planned,
        "attempted": attempted,
        "unrun": planned - attempted,
        "automatic_passes": sum(system["automatic_passes"] for system in systems),
        "estimated_cost_usd": summary["estimated_cost_usd"],
        "stop_reason": pick(stop, (
            "kind", "status", "consecutive_failures", "case_id", "repeat", "system", "policy",
        )) if isinstance(stop, dict) else None,
        "gate": pick(data["release_gate"], ("status", "target", "reason")),
        "systems": systems,
        "cases": cases,
    }


def build_showcase(results_dir, *, generated_at=None):
    """Return the dashboard schema using saved successful reports and summaries."""
    results_dir = Path(results_dir)
    smoke_path = results_dir / "live-smoke-20261002.json"
    retail_path = results_dir / "retail.json"
    development_path = results_dir / "live-development-v3_1-20261002.json"
    deterministic_path = results_dir / "deterministic-rag-20261002.json"
    retrieval_path = results_dir / "retrieval.json"
    smoke = read_json(smoke_path)
    retail = read_json(retail_path)
    development = read_json(development_path)
    if development.get("execution_status") != "completed" or not development.get("completed_at_utc"):
        raise ValueError("The recorded development sample must come from a terminal saved evaluation")
    live_retail = next(
        case["systems"]["agent"]
        for run in development["runs"]
        for case in run["cases"]
        if case["id"] == "retail-live-02"
    )
    live_retail_checks = live_retail["checks"]
    semantic_status = live_retail_checks["manual_semantic_review"]["status"]
    whole_task = live_retail_checks["whole_task_pass"]
    whole_task_note = "unscored" if whole_task is None else "passed" if whole_task else "not passed"
    automatic_note = "passed" if live_retail["automatic_pass"] else "not passed"
    deterministic = read_json(deterministic_path)
    retrieval = read_json(retrieval_path)
    smoke_day = datetime.strptime(re.search(r"(\d{8})", smoke_path.name).group(1), "%Y%m%d").date().isoformat()
    live_runs = []
    supplemental_runs = []
    supplemental_status = []
    for path in sorted(results_dir.glob("live-*.json")):
        if path.name.endswith(".review.json"):
            continue
        try:
            data = read_json(path)
        except (ValueError, OSError):
            continue
        if data.get("track") in {"retail", "adversarial"} and data.get("execution_status") == "execution_blocked":
            supplemental_status.append({
                "track": data["track"],
                "status": data["execution_status"],
                "planned": data["planned_response_count"],
                "recorded": data["recorded_response_count"],
                "source_path": source_path(path),
                "reason": data["stop_reason"]["note"],
            })
            continue
        if data.get("execution_status") != "completed" or not data.get("completed_at_utc"):
            continue
        if data.get("track") == "synthetic":
            live_runs.append(summarize_live(path, data))
        elif data.get("track") in {"retail", "adversarial"}:
            supplemental_runs.append(summarize_live(path, data))
    live_runs.sort(key=lambda run: datetime.fromisoformat(run["run_at"]))
    supplemental_runs.sort(key=lambda run: datetime.fromisoformat(run["run_at"]))
    return {
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "records": [
            {
                "id": "recorded-live-funnel",
                "title": "Ordered practice funnel",
                "subtitle": "Recorded live-model answer on synthetic data",
                "dataset": "synthetic",
                "recorded_at": smoke_day,
                "recorded_at_precision": "day",
                "source_path": source_path(smoke_path),
                "review_note": (
                    "One real-provider smoke, not a benchmark. AI-assisted review of this sample only; "
                    "not a human review. " + smoke["manual_review"]["notes"]
                ),
                "report": sanitize_report(smoke["response"]),
            },
            {
                "id": "recorded-live-retail",
                "title": "Retail sales · live model",
                "subtitle": "Recorded development-only live-model answer on public retail data",
                "dataset": "retail",
                "recorded_at": development["run_at_utc"],
                "recorded_at_precision": "timestamp",
                "source_path": source_path(development_path),
                "review_note": (
                    "Development-only recorded sample, not a benchmark. "
                    f"Automatic numeric/citation checks: {automatic_note}. "
                    f"Human semantic review status: {semantic_status}; whole-task outcome: {whole_task_note}."
                ),
                "report": sanitize_report(live_retail["response"]),
            },
            {
                "id": "recorded-retail-country",
                "title": "Retail sales · tools only",
                "subtitle": "Recorded deterministic analysis of public retail data",
                "dataset": "retail",
                "recorded_at": retail["run_at_utc"],
                "recorded_at_precision": "timestamp",
                "source_path": source_path(retail_path),
                "review_note": retail["scope"] + " " + retail["reference_method"],
                "report": sanitize_report(retail["execution"]),
            },
        ],
        "verification": {
            "deterministic": {
                "run_at": deterministic["run_at_utc"],
                "source_path": source_path(deterministic_path),
                "runs": [pick(run, ("repeat", "passed", "total")) for run in deterministic["runs"]],
                "passed": deterministic["passed"],
                "scope": deterministic["scope"],
            },
            "retrieval": {
                "source_path": source_path(retrieval_path),
                **pick(retrieval, (
                    "scope", "total", "semantic_top1_hits", "semantic_top3_hits",
                    "lexical_top1_hits", "lexical_top3_hits",
                )),
            },
            "retail": {
                "run_at": retail["run_at_utc"],
                "source_path": source_path(retail_path),
                **pick(retail, ("passed", "check_count", "scope")),
            },
            "live_runs": live_runs,
            "primary_live_run_id": live_runs[-1]["id"] if live_runs else None,
            "supplemental_runs": supplemental_runs,
            "supplemental_status": supplemental_status,
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, default=ROOT / "evals" / "results")
    parser.add_argument("--output", type=Path, default=ROOT / "app" / "data" / "showcase.json")
    args = parser.parse_args()
    data = build_showcase(args.results_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=args.output.parent, delete=False) as temporary:
        json.dump(data, temporary, ensure_ascii=False, indent=2, allow_nan=False)
        temporary.write("\n")
        temporary_path = temporary.name
    os.replace(temporary_path, args.output)
    print(f"Wrote {args.output}: {len(data['records'])} recorded reports, "
          f"{len(data['verification']['live_runs'])} terminal synthetic evaluations, "
          f"{len(data['verification']['supplemental_runs'])} terminal supplements, "
          f"{len(data['verification']['supplemental_status'])} blocked supplement manifests")


if __name__ == "__main__":
    main()
