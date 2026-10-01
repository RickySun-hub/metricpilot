"""Reproducible synthetic SaaS data; no real product/user records."""
from __future__ import annotations

import hashlib
import json
import random
from collections import defaultdict
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BEFORE = ("2026-09-01", "2026-09-08")
AFTER = ("2026-09-08", "2026-09-15")
CUTOFF = "2026-09-30T00:00:00"


def dataset_hash(data: dict) -> str:
    payload = {k: data[k] for k in ("users", "events", "experiment_assignments", "cutoff", "seed")}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def generate_dataset(seed: int = 20260930, users: int = 12000) -> dict:
    if users < 20 or users > 50000 or users % 2:
        raise ValueError("users must be an even integer between 20 and 50000")
    rng = random.Random(seed)
    people, events, assignments = [], [], []
    daily = defaultdict(lambda: [0, 0])
    for period in range(2):
        half = users // 2
        ids = list(range(period * half, (period + 1) * half))
        channel_ids = ids.copy()
        rng.shuffle(channel_ids)
        organic = set(channel_ids[:round(half * (0.8 if period == 0 else 0.2))])
        assignment_ids = ids.copy()
        rng.shuffle(assignment_ids)
        controls = set(assignment_ids[:half // 2 if period == 0 else round(half * 0.75)])
        for i in ids:
            uid = f"u_{i:05d}"
            signup = datetime(2026, 9, 1 + period * 7) + timedelta(seconds=rng.randrange(7 * 86400))
            channel = "organic" if i in organic else "paid"
            person = {"user_id": uid, "signup_at": signup.isoformat(), "acquisition_channel": channel,
                      "signup_device": "mobile" if rng.random() < 0.55 else "desktop"}
            people.append(person)
            def event(kind: str, timestamp: datetime, session: str = "") -> None:
                events.append({"event_id": f"e_{len(events):07d}", "user_id": uid,
                               "event_at": timestamp.isoformat(), "event_type": kind,
                               "practice_session_id": session})
            event("signup", signup)
            event("page_view", signup + timedelta(minutes=1))
            event("page_view", signup + timedelta(minutes=2))
            started = rng.random() < (0.9 if channel == "organic" else 0.65)
            completed = started and rng.random() < ((0.65 if channel == "organic" else 0.2) + period * 0.02) / (0.9 if channel == "organic" else 0.65)
            if started:
                start = signup + timedelta(hours=rng.randint(1, 36))
                event("practice_start", start, f"s_{uid}")
                if completed:
                    event("practice_complete", start + timedelta(minutes=rng.randint(10, 90)), f"s_{uid}")
            assignments.append({"experiment_id": "onboarding_valid" if period == 0 else "onboarding_srm",
                                "user_id": uid, "variant": "control" if i in controls else "treatment",
                                "assigned_at": signup.isoformat(), "expected_allocation": 0.5})
            bucket = daily[(signup.date().isoformat(), channel)]
            bucket[0] += int(completed)
            bucket[1] += 1
    result = {"users": people, "events": events, "experiment_assignments": assignments,
              "metric_daily": [{"date": day, "metric_id": "activation", "segment": channel,
                                "numerator": n, "denominator": d, "contract_version": "1.0"}
                               for (day, channel), (n, d) in sorted(daily.items())],
              "cutoff": CUTOFF, "seed": seed, "label": "Synthetic interview-preparation SaaS"}
    result["hash"] = dataset_hash(result)
    return result


def validate_dataset(data: dict) -> None:
    people = {u["user_id"]: u for u in data["users"]}
    if len(people) != len(data["users"]):
        raise ValueError("Duplicate user identity")
    event_ids = set()
    for e in data["events"]:
        if e["event_id"] in event_ids or e["user_id"] not in people:
            raise ValueError("Duplicate event or missing referenced user")
        event_ids.add(e["event_id"])
        if datetime.fromisoformat(e["event_at"]) < datetime.fromisoformat(people[e["user_id"]]["signup_at"]):
            raise ValueError("Event precedes signup")
    pairs = set()
    for a in data["experiment_assignments"]:
        pair = (a["experiment_id"], a["user_id"])
        if pair in pairs or a["user_id"] not in people or a["variant"] not in ("control", "treatment"):
            raise ValueError("Invalid or contaminated experiment assignment")
        if a["expected_allocation"] != 0.5:
            raise ValueError("Only the predeclared 50:50 allocation is supported")
        if datetime.fromisoformat(a["assigned_at"]) < datetime.fromisoformat(people[a["user_id"]]["signup_at"]):
            raise ValueError("Assignment precedes signup")
        pairs.add(pair)


@lru_cache(maxsize=1)
def default_dataset() -> dict:
    path = ROOT / "data" / "demo.json.gz"
    if path.exists():
        import gzip
        with gzip.open(path, "rt", encoding="utf-8") as f:
            data = json.load(f)
        if data["hash"] != dataset_hash(data):
            raise ValueError("Bundled dataset hash mismatch")
        return data
    return generate_dataset()


if __name__ == "__main__":
    import gzip
    data = generate_dataset()
    validate_dataset(data)
    target = ROOT / "data"
    target.mkdir(exist_ok=True)
    with (target / "demo.json.gz").open("wb") as output:
        with gzip.GzipFile(fileobj=output, mode="wb", mtime=0) as compressed:
            compressed.write(json.dumps(data, separators=(",", ":")).encode())
    manifest = {k: data[k] for k in ("hash", "cutoff", "seed", "label")}
    manifest.update({"users": len(data["users"]), "events": len(data["events"]),
                     "assignments": len(data["experiment_assignments"]), "generator": "backend/data.py"})
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
