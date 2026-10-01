"""Bounded LangGraph controller with explicitly distinct deterministic/live modes."""
from __future__ import annotations

import re
import time
import uuid
from threading import Lock
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from .budget import BudgetError, live_available, reserve
from .data import default_dataset
from .provider import MODEL, choose_action
from .retrieval import retrieve
from .tools import Analytics, ToolError, default_analytics

TOOLS_LOCK = Lock()
REQUEST_TIMEOUT_SECONDS = 45


class DatasetUnavailableError(RuntimeError):
    """Bundled data could not be loaded; expose only a safe API message."""


def _timeout():
    return {"status": "timed_out", "summary": "Request deadline reached.", "findings": []}


class State(TypedDict, total=False):
    question: str
    mode: str
    status: str
    summary: str
    retrieval: list
    evidence: list
    trace: list
    findings: list
    warnings: list
    metrics: dict
    action: dict
    started: float


def _boundary(question: str):
    q = question.lower()
    if re.search(r"\b(delete|drop|insert|update|shell|exec|password|secret|filesystem|postal_code|zip_code|revenue|retention)\b", q) or ";" in q:
        return "unsupported", "This request is outside the allowlisted analytical scope. No executable SQL or code is accepted."
    if "engagement" in q:
        return "needs_clarification", "Engagement is undefined. Choose seven-day activation, the ordered practice funnel, or a named onboarding experiment."
    experiment_names = re.findall(r"onboarding_[a-z0-9_]+", q)
    if any(name not in ("onboarding_valid", "onboarding_srm") for name in experiment_names):
        return "unsupported", "The requested experiment is not defined in this dataset."
    # Date/calendar generalization is not silently inferred from our fixed demo periods.
    if re.search(r"\b(20\d\d-\d\d-\d\d|yesterday|today|last month|next week)\b", q):
        return "unsupported", "The demo supports the documented September 1–8 and September 8–15 signup cohorts only."
    if "experiment" in q and not experiment_names:
        return "needs_clarification", "Choose onboarding_valid or onboarding_srm so the experiment contract is explicit."
    if not any(word in q for word in ("activation", "funnel", "signup", "practice", "onboarding_")):
        return "unsupported", "Supported tasks: activation change, ordered practice funnel, or a named onboarding experiment."
    return None


def _deterministic_action(state):
    q = state["question"].lower()
    done = [e["tool"] for e in state["evidence"]]
    common = {"segment": "signup_device" if "device" in q else "acquisition_channel", "experiment_id": "onboarding_srm" if "onboarding_srm" in q else "onboarding_valid"}
    if "onboarding_" in q:
        action = "check_experiment" if not done else "finish"
    elif "funnel" in q or ("signup" in q and "activation" not in q):
        action = "analyze_funnel" if not done else "finish"
    else:
        action = "compare_metric" if not done else "decompose_change" if "decompose_change" not in done else "finish"
    return {**common, "action": action, "reason": "Rule-based controller; no LLM invocation."}


def _findings(evidence):
    values = []
    def add(item, label, path, unit="pp", scale=1):
        result = item["result"]
        for key in path.split("."):
            result = result[key]
        if result is not None:
            values.append({"label": label, "value": result*scale, "unit": unit, "evidence_id": item["id"], "field_path": path, "scale": scale})
    for e in evidence:
        if e["tool"] == "compare_metric":
            add(e, "Before activation", "before.rate", "%", 100)
            add(e, "After activation", "after.rate", "%", 100)
            add(e, "Activation change", "delta_pp")
        elif e["tool"] == "decompose_change":
            add(e, "Mix contribution", "mix_pp")
            add(e, "Within-group contribution", "within_pp")
        elif e["tool"] == "analyze_funnel":
            add(e, "Before completion", "before.completion_rate", "%", 100)
            add(e, "After completion", "after.completion_rate", "%", 100)
            add(e, "Before starts", "before.start_rate", "%", 100)
            add(e, "After starts", "after.start_rate", "%", 100)
        elif e["tool"] == "check_experiment":
            add(e, "SRM p-value", "srm_pvalue", "p")
            if e["result"]["status"] == "valid":
                add(e, "Treatment − control", "effect_pp")
                add(e, "95% interval lower", "ci_low_pp")
                add(e, "95% interval upper", "ci_high_pp")
    return values


def validate_findings(findings, evidence):
    lookup = {e["id"]: e for e in evidence}
    for f in findings:
        if f["evidence_id"] not in lookup:
            raise ToolError("Unresolved evidence reference")
        value = lookup[f["evidence_id"]]["result"]
        for key in f["field_path"].split("."):
            value = value[key]
        if abs(f["value"]-value*f["scale"]) > 1e-9:
            raise ToolError("Report value does not match evidence")


def run_analysis(question: str, mode: str = "deterministic", dataset: dict | None = None, client: str = "local") -> dict:
    begun = time.perf_counter()
    deadline = begun + REQUEST_TIMEOUT_SECONDS
    metrics = {"elapsed_ms": 0, "model_calls": 0, "tool_calls": 0, "input_tokens": 0, "output_tokens": 0, "estimated_cost_usd": 0}
    state = {"question": question, "mode": mode, "status": "running", "summary": "", "evidence": [], "retrieval": [],
             "trace": [], "findings": [], "warnings": [], "metrics": metrics, "started": begun}
    try:
        data = dataset if dataset is not None else default_dataset()
    except Exception as exc:
        raise DatasetUnavailableError("The synthetic dataset is unavailable. Please try again later.") from exc
    engine = None
    try:
        if not isinstance(question, str) or not 3 <= len(question) <= 1000:
            raise ToolError("Question must contain 3–1000 characters")
        if mode not in ("deterministic", "live"):
            raise ToolError("Unknown execution mode")
        boundary = _boundary(question)
        if boundary:
            state["status"], state["summary"] = boundary
        else:
            if mode == "live":
                if not live_available():
                    raise BudgetError("Live mode is not enabled or lacks durable public quota accounting")
                reserve(client=client)
            engine = Analytics(data) if dataset is not None else default_analytics()
            def retrieval_node(s):
                documents = retrieve(s["question"])
                method = documents[0]["method"] if documents else "none"
                return {"retrieval": documents, "trace": s["trace"] + [{"step": "retrieve", "detail": "Retrieved versioned metric contracts using "+method+"."}]}
            def decide(s):
                if time.perf_counter() >= deadline:
                    return _timeout()
                if s["mode"] == "live":
                    if s["metrics"]["model_calls"] >= 6:
                        return {"status": "budget_exceeded", "summary": "Model-call limit reached."}
                    action, usage = choose_action(s)
                    updated = dict(s["metrics"])
                    updated["model_calls"] += 1
                    updated["input_tokens"] += usage.get("prompt_tokens", 0)
                    updated["output_tokens"] += usage.get("completion_tokens", 0)
                    updated["estimated_cost_usd"] = updated["input_tokens"]*0.4/1000000+updated["output_tokens"]*1.6/1000000
                    if updated["estimated_cost_usd"] > 0.015:
                        return {"metrics": updated, "status": "budget_exceeded", "summary": "Per-request model cost limit reached."}
                else:
                    action, updated = _deterministic_action(s), s["metrics"]
                # A provider response may arrive after the request deadline. Keep its
                # usage accounting, but never execute the late action or report success.
                if time.perf_counter() >= deadline:
                    return {**_timeout(), "metrics": updated}
                if action["action"] in ("clarify", "unsupported"):
                    return {"metrics": updated, "status": "needs_clarification" if action["action"] == "clarify" else "unsupported", "summary": "The model could not resolve a supported analytical task."}
                if action["action"] != "finish" and len(s["evidence"]) >= 5:
                    return {"metrics": updated, "status": "budget_exceeded", "summary": "Tool-call limit reached."}
                return {"metrics": updated, "action": action, "trace": s["trace"] + [{"step": "select", "detail": action["action"]+": "+action["reason"][:200]}]}
            def execute(s):
                action = s["action"]
                name = action["action"]
                if name not in ("compare_metric", "analyze_funnel", "decompose_change", "check_experiment"):
                    raise ToolError("Disallowed tool")
                args = {"segment": action["segment"]} if name == "decompose_change" else {"experiment_id": action["experiment_id"]} if name == "check_experiment" else {}
                if any(e["tool"] == name and all(e["args"].get(k) == v for k,v in args.items()) for e in s["evidence"]):
                    raise ToolError("Repeated identical tool call rejected")
                remaining = deadline - time.perf_counter()
                if remaining <= 0 or not TOOLS_LOCK.acquire(timeout=remaining):
                    return _timeout()
                try:
                    if time.perf_counter() >= deadline:
                        return _timeout()
                    evidence = getattr(engine, name)(**args)
                finally:
                    TOOLS_LOCK.release()
                updated = {**s["metrics"], "tool_calls": s["metrics"]["tool_calls"]+1}
                return {"evidence": s["evidence"]+[evidence], "metrics": updated,
                        "trace": s["trace"]+[{"step": "execute", "detail": name+" completed; evidence "+evidence["id"]}]}
            def report(s):
                if time.perf_counter() >= deadline:
                    return _timeout()
                if not s["evidence"]:
                    return {"status": "verification_failed", "summary": "No analytical evidence was produced."}
                findings = _findings(s["evidence"])
                validate_findings(findings, s["evidence"])
                if time.perf_counter() >= deadline:
                    return _timeout()
                warnings = [w for e in s["evidence"] for w in e["warnings"]]
                last = s["evidence"][-1]
                if last["tool"] == "check_experiment":
                    summary = last["result"]["conclusion"]
                    status = "invalid_data" if last["result"]["status"] == "invalid" else "completed"
                elif last["tool"] == "decompose_change":
                    result = last["result"]
                    summary = f"Activation changed by {result['delta_pp']:+.2f} percentage points. Mix contribution: {result['mix_pp']:+.2f} pp; within-group contribution: {result['within_pp']:+.2f} pp. This explains the rate arithmetically, not causally."
                    status = "completed"
                elif last["tool"] == "analyze_funnel":
                    summary = "Compared mature signup cohorts using ordered, session-matched practice events. Inspect both signup-to-step and conditional completion rates."
                    status = "completed"
                else:
                    summary = "Compared seven-day activation on mature signup cohorts. More evidence is needed to explain the change."
                    status = "completed"
                    warnings.append("The model ended before a decomposition; do not claim an explanation of the change.")
                return {"summary": summary, "status": status, "findings": findings, "warnings": warnings,
                        "trace": s["trace"]+[{"step": "verify", "detail": "Numeric claims match evidence fields. Narrative is generated from deterministic templates."}]}
            graph = StateGraph(State)
            for name, fn in (("retrieve", retrieval_node), ("decide", decide), ("execute", execute), ("report", report)):
                graph.add_node(name, fn)
            graph.add_edge(START, "retrieve")
            graph.add_edge("retrieve", "decide")
            graph.add_conditional_edges("decide", lambda s: END if s["status"] != "running" else "report" if s["action"]["action"] == "finish" else "execute")
            graph.add_edge("execute", "decide")
            graph.add_edge("report", END)
            state = dict(graph.compile().invoke(state, {"recursion_limit": 20}))
    except BudgetError as exc:
        state.update(status="budget_exceeded", summary=str(exc))
    except ToolError as exc:
        state.update(status="invalid_data", summary=str(exc))
    except Exception:
        state.update(status="provider_error" if mode == "live" else "invalid_data", summary="Execution failed; no verified report is available.")
    finally:
        if dataset is not None and engine is not None:
            engine.close()
    finished = time.perf_counter()
    if state["status"] == "completed" and finished >= deadline:
        state.update(_timeout())
    state["metrics"]["elapsed_ms"] = round((finished-begun)*1000, 2)
    state.pop("started", None)
    state.pop("action", None)
    return {**state, "request_id": uuid.uuid4().hex, "model": MODEL if mode == "live" else None,
            "dataset": {"hash": data.get("hash", "custom"), "users": len(data["users"]), "events": len(data["events"]),
                        "label": data.get("label", "Synthetic fixture"), "cutoff": data["cutoff"]}}
