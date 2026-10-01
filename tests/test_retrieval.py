import pytest
from backend.retrieval import embedder, lexical_retrieve, retrieve


def test_local_embedding_similarity_and_shape():
    model = embedder()
    vectors = model.encode(["user conversion", "user conversion", "filesystem access"])
    assert vectors.shape == (3, 384)
    assert float(vectors[0] @ vectors[1]) == pytest.approx(1, abs=1e-5)
    assert float(vectors[0] @ vectors[2]) < .9


def test_retrieval_returns_versioned_contracts_not_permissions():
    results = retrieve("Did the assigned groups follow equal randomization?")
    assert "srm" in {r["id"] for r in results}
    assert all(r["method"] == "minilm_cosine_similarity" and r["version"] == "1.0" for r in results)
    assert all(-1 <= r["score"] <= 1 for r in results)
    assert lexical_retrieve("activation")[0]["id"] == "activation"


def test_wordpiece_matches_pinned_upstream_tokenizer():
    from pathlib import Path
    from tokenizers import Tokenizer
    from backend.retrieval import DOCUMENTS
    reference = Tokenizer.from_file(str(Path("models/minilm/tokenizer.json")))
    reference.no_padding()
    reference.enable_truncation(max_length=256)
    texts = [doc["title"]+". "+doc["text"] for doc in DOCUMENTS] + [
        "Why did activation fall between the two weeks?", "onboarding_valid: 95% CI",
        "café conversion", "September 1–8 UTC", "Where did the signup to practice completion funnel change?",
        "Is experiment onboarding_srm trustworthy?", "Should we ship onboarding_valid?",
    ]
    for text in texts:
        assert embedder().tokenizer.encode(text) == reference.encode(text).ids
