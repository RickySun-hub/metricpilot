"""Same-origin FastAPI API for local development and Vercel Python functions."""
import hashlib
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal

load_dotenv(Path(__file__).resolve().parent.parent / ".env.local", override=False)

from backend.agent import DatasetUnavailableError, run_analysis
from backend.budget import live_available

app = FastAPI(title="MetricPilot", version="0.1.0", docs_url="/api/docs", openapi_url="/api/openapi.json")


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=3, max_length=1000)
    mode: Literal["deterministic", "live"] = "deterministic"
    dataset: Literal["demo"] = "demo"


class RetailAnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=3, max_length=1000)
    mode: Literal["deterministic", "live"] = "deterministic"


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "0.1.0", "live_enabled": live_available(),
            "deterministic_enabled": True, "retrieval": "minilm_cosine_similarity" if (Path(__file__).resolve().parent.parent/"models/minilm/manifest.json").exists() else "lexical_term_retrieval", "data": "synthetic"}


def client_key(request: Request) -> str:
    # Do not store public IPs: use a scoped hash for shared per-client quotas.
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    client = forwarded if os.getenv("VERCEL") else request.client.host if request.client else "unknown"
    return hashlib.sha256((os.getenv("METRICPILOT_CLIENT_SALT", "metricpilot-demo")+client).encode()).hexdigest()[:20]


@app.post("/api/analyze")
def analyze(body: AnalysisRequest, request: Request):
    try:
        return run_analysis(body.question, body.mode, client=client_key(request))
    except DatasetUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/retail/analyze")
def analyze_retail(body: RetailAnalysisRequest, request: Request):
    from backend.retail import run_retail_analysis
    try:
        return run_retail_analysis(body.question, mode=body.mode, client=client_key(request))
    except DatasetUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/evaluation")
def evaluation():
    file = Path(__file__).resolve().parent.parent / "evals" / "results" / "deterministic.json"
    if file.exists():
        payload = json.loads(file.read_text(encoding="utf-8"))
        # Serve the small measured summary, not fixture data or a claim of live model quality.
        return payload
    return {"status": "not_evaluated", "mode": "deterministic", "message": "No measured evaluation is published yet."}
