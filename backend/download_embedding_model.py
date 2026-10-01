"""Download pinned public Apache-2.0 ONNX assets; never call a paid inference API."""
import hashlib
import json
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent


def main():
    revision = "751bff37182d3f1213fa05d7196b954e230abad9"
    folder = ROOT / "models" / "minilm"
    folder.mkdir(parents=True, exist_ok=True)
    entries = []
    for source, target in (("onnx/model_quantized.onnx", "model.onnx"), ("tokenizer.json", "tokenizer.json")):
        response = httpx.get(f"https://huggingface.co/Xenova/all-MiniLM-L6-v2/resolve/{revision}/{source}", follow_redirects=True, timeout=120)
        response.raise_for_status()
        file = folder / target
        file.write_bytes(response.content)
        entries.append({"source": source, "file": target, "bytes": len(response.content), "sha256": hashlib.sha256(response.content).hexdigest()})
    license_response = httpx.get("https://www.apache.org/licenses/LICENSE-2.0.txt", timeout=30)
    license_response.raise_for_status()
    (folder / "LICENSE").write_bytes(license_response.content)
    manifest = {"model": "Xenova/all-MiniLM-L6-v2", "revision": revision, "license": "Apache-2.0", "files": entries}
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
