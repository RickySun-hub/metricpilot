# Local embedding assets

`minilm/` contains the pinned quantized ONNX export of Xenova/all-MiniLM-L6-v2, its tokenizer, SHA-256 provenance manifest and Apache-2.0 license. Original model: sentence-transformers/all-MiniLM-L6-v2. Attribution and model card: https://huggingface.co/Xenova/all-MiniLM-L6-v2

Inference uses CPU ONNX Runtime, attention-mask-aware mean pooling and unit normalization. Document/query matching uses cosine similarity over 384-dimensional vectors. There is no external embedding request, paid API, GPU allocation or fine-tuning.

Regenerate the assets using `python -m backend.download_embedding_model`. The revision is pinned in that script. These upstream pretrained weights were not trained by this project's owner.
