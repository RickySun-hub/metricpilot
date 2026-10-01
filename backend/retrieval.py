"""CPU semantic retrieval with a measured lexical baseline; no paid embedding API."""
import hashlib
import json
import math
import re
import tempfile
import os
from collections import Counter
from pathlib import Path
from functools import lru_cache

DOCUMENTS = json.loads((Path(__file__).resolve().parent.parent / "contracts" / "metrics.json").read_text(encoding="utf-8"))


def tokens(text):
    return re.findall(r"[a-z0-9_]+", text.lower())


def lexical_retrieve(question: str, k: int = 3) -> list[dict]:
    counts = [Counter(tokens(doc["title"] + " " + doc["text"])) for doc in DOCUMENTS]
    query = Counter(tokens(question))
    vocabulary = set(query)
    idf = {word: math.log(1 + len(DOCUMENTS)/(1+sum(word in count for count in counts))) for word in vocabulary}
    results = []
    for doc, count in zip(DOCUMENTS, counts):
        score = sum(idf[word] * count[word]/(count[word]+1.2) for word in vocabulary)
        results.append({**doc, "score": round(score, 4), "version": "1.0", "method": "lexical_term_retrieval"})
    return sorted(results, key=lambda doc: (-doc["score"], doc["id"]))[:k]


class Embedder:
    def __init__(self):
        import onnxruntime as ort
        from .wordpiece import WordPiece
        folder = Path(__file__).resolve().parent.parent / "models" / "minilm"
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        model_path = folder / "model.onnx"
        if not model_path.exists():
            # The public serverless bundle omits the large weight file. Fetch only the
            # fixed, attributed public model asset, then enforce its recorded checksum.
            import httpx
            model_path = Path(tempfile.gettempdir()) / ("metricpilot-"+manifest["revision"]+".onnx")
            if not model_path.exists():
                url = "https://huggingface.co/Xenova/all-MiniLM-L6-v2/resolve/"+manifest["revision"]+"/onnx/model_quantized.onnx"
                response = httpx.get(url, follow_redirects=True, timeout=25)
                response.raise_for_status()
                temporary = model_path.with_suffix("."+str(os.getpid())+".tmp")
                temporary.write_bytes(response.content)
                temporary.replace(model_path)
        for entry in manifest["files"]:
            file = model_path if entry["file"] == "model.onnx" else folder/entry["file"]
            if hashlib.sha256(file.read_bytes()).hexdigest() != entry["sha256"]:
                raise ValueError("Embedding asset checksum mismatch")
        tokenizer_spec = json.loads((folder/"tokenizer.json").read_text(encoding="utf-8"))
        self.tokenizer = WordPiece(tokenizer_spec["model"]["vocab"])
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        self.session = ort.InferenceSession(str(model_path), sess_options=options, providers=["CPUExecutionProvider"])
        self.vectors = self.encode([doc["title"]+". "+doc["text"] for doc in DOCUMENTS])

    def encode(self, texts):
        import numpy as np
        encoded = [self.tokenizer.encode(text) for text in texts]
        length = max(map(len, encoded))
        feeds = {"input_ids": np.asarray([ids+[0]*(length-len(ids)) for ids in encoded], dtype=np.int64),
                 "attention_mask": np.asarray([[1]*len(ids)+[0]*(length-len(ids)) for ids in encoded], dtype=np.int64),
                 "token_type_ids": np.zeros((len(texts),length), dtype=np.int64)}
        names = {i.name for i in self.session.get_inputs()}
        states = self.session.run(None, {k:v for k,v in feeds.items() if k in names})[0]
        mask = feeds["attention_mask"][..., None]
        mean = (states*mask).sum(axis=1)/mask.sum(axis=1)
        return mean / np.maximum(np.linalg.norm(mean, axis=1, keepdims=True), 1e-12)


@lru_cache(maxsize=1)
def embedder():
    return Embedder()


def retrieve(question: str, k: int = 3) -> list[dict]:
    # Missing assets have a visible fallback, not an invented semantic score.
    folder = Path(__file__).resolve().parent.parent / "models" / "minilm"
    if not (folder/"manifest.json").exists():
        return lexical_retrieve(question, k)
    model = embedder()
    similarities = (model.vectors @ model.encode([question])[0]).tolist()
    ranked = sorted(range(len(DOCUMENTS)), key=lambda i: (-similarities[i], DOCUMENTS[i]["id"]))[:k]
    return [{**DOCUMENTS[i], "score": round(similarities[i], 4), "version": "1.0", "method": "minilm_cosine_similarity"} for i in ranked]
