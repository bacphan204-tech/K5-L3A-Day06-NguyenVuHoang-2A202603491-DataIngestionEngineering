"""Real local multilingual E5 embeddings; never substitute mock vectors."""
import os
import json
from pathlib import Path


class MyEmbedder:
    def __init__(self, model_name="intfloat/multilingual-e5-small", revision=None):
        os.environ.setdefault("HF_HOME", str(Path(__file__).resolve().parents[2] / ".local/huggingface"))
        os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
        from sentence_transformers import SentenceTransformer
        import torch
        torch.set_num_threads(min(4, os.cpu_count() or 1))
        self.model_name = model_name
        local = Path(__file__).resolve().parents[2] / ".local/models/multilingual-e5-small"
        info = local / "download_info.json"
        if info.exists() and json.loads(info.read_text(encoding="utf-8")) == {"model": model_name, "revision": revision}:
            self.model = SentenceTransformer(str(local), device="cpu", local_files_only=True)
        else:
            self.model = SentenceTransformer(model_name, revision=revision, device="cpu")
        self.model.max_seq_length = 512
        self.dimensions = self.model.get_sentence_embedding_dimension()
        self.revision = getattr(self.model[0].auto_model.config, "_commit_hash", None) or revision

    def token_lengths(self, texts, prefix):
        return [len(ids) for ids in self.model.tokenizer([prefix + t for t in texts], truncation=False)["input_ids"]]

    def embed_documents(self, texts):
        if max(self.token_lengths(texts, "passage: "), default=0) > 512:
            raise ValueError("Document exceeds 512 tokens; do not silently truncate")
        return self.model.encode(["passage: " + t for t in texts], batch_size=16,
            normalize_embeddings=True, show_progress_bar=True).tolist()

    def embed_query(self, question):
        if self.token_lengths([question], "query: ")[0] > 512:
            raise ValueError("Query exceeds model token limit")
        return self.model.encode("query: " + question, normalize_embeddings=True).tolist()
