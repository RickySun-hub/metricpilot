"""Small labeled semantic-retrieval check against a lexical baseline (development set)."""
import hashlib
import json
from pathlib import Path

from backend.retrieval import lexical_retrieve, retrieve

CASES = [
    ("What share of new accounts finish a rehearsal within a week?", "activation"),
    ("How many people move from signup through starting to finishing practice?", "funnel"),
    ("Can changing acquisition proportions explain the overall conversion change?", "mix_shift"),
    ("Did the randomized groups receive equal numbers of assigned users?", "srm"),
    ("How should we interpret an effect range that contains zero?", "confidence"),
    ("Which cohorts have finished their entire observation period?", "windows"),
    ("Are these customer records from a real business?", "synthetic"),
    ("May the model execute arbitrary SQL or access local files?", "safety"),
    ("Can I calculate engagement or retention with this demo?", "scope"),
    ("What is the predeclared outcome and randomization unit for this A/B test?", "experiment"),
]


def main():
    rows = []
    for query, expected in CASES:
        semantic, lexical = retrieve(query), lexical_retrieve(query)
        rows.append({"query": query, "expected": expected, "semantic_top3": [r["id"] for r in semantic],
                     "lexical_top3": [r["id"] for r in lexical], "semantic_method": semantic[0]["method"]})
    summary = {"scope": "10 labeled development retrieval queries; not a held-out model benchmark or generalization claim.",
               "cases": rows, "semantic_top1_hits": sum(r["expected"] == r["semantic_top3"][0] for r in rows),
               "semantic_top3_hits": sum(r["expected"] in r["semantic_top3"] for r in rows),
               "lexical_top1_hits": sum(r["expected"] == r["lexical_top3"][0] for r in rows),
               "lexical_top3_hits": sum(r["expected"] in r["lexical_top3"] for r in rows), "total": len(rows),
               "contract_sha256": hashlib.sha256(Path("contracts/metrics.json").read_bytes()).hexdigest()}
    target = Path("evals/results/retrieval.json")
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(summary, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({k:v for k,v in summary.items() if k != "cases"}, indent=2))


if __name__ == "__main__":
    main()
