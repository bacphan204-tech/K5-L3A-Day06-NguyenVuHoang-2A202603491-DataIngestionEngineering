"""Persistent Chroma cosine search with explicit metadata filters."""
from pathlib import Path


class ChromaStore:
    def __init__(self, path: Path, dimensions: int):
        import chromadb
        from chromadb.config import Settings
        self.client = chromadb.PersistentClient(path=str(path), settings=Settings(anonymized_telemetry=False))
        self.dimensions = dimensions

    def collection(self, strategy):
        if strategy not in ("A", "B", "C"):
            raise ValueError("Unknown strategy")
        return self.client.get_or_create_collection("economics_" + strategy.lower(),
            metadata={"hnsw:space": "cosine"}, embedding_function=None)

    def upsert(self, strategy, chunks, vectors):
        if len(chunks) != len(vectors) or any(len(v) != self.dimensions for v in vectors):
            raise ValueError("Vector count/dimensions mismatch")
        collection = self.collection(strategy)
        old_ids = set(collection.get()["ids"])
        for start in range(0, len(chunks), 100):
            batch = chunks[start:start + 100]
            collection.upsert(ids=[c.chunk_id for c in batch],
                embeddings=vectors[start:start + 100], documents=[c.text for c in batch],
                metadatas=[{**c.metadata, "document_id": c.document_id, "source": c.source, "page": c.page} for c in batch])
        obsolete = old_ids - {c.chunk_id for c in chunks}
        if obsolete:
            collection.delete(ids=sorted(obsolete))
        if collection.count() != len(chunks):
            raise RuntimeError("Collection count mismatch")
        return {"count": collection.count(), "obsolete_removed": len(obsolete)}

    def search(self, strategy, query_vector, top_k=3, filters=None):
        if len(query_vector) != self.dimensions:
            raise ValueError("Query dimensions mismatch")
        if filters and (set(filters) != {"chapter"} or filters["chapter"] not in (3, 4)):
            raise ValueError("Only validated chapter 3/4 filters are supported")
        collection = self.collection(strategy)
        if not collection.count():
            raise RuntimeError("Collection is empty; ingest first")
        result = collection.query(query_embeddings=[query_vector],
            n_results=min(top_k, collection.count()), where=filters or None,
            include=["documents", "metadatas", "distances"])
        return [{"chunk_id": cid, "text": text, "score": 1.0 - distance,
                 "distance": distance, "metadata": metadata}
                for cid, text, distance, metadata in zip(result["ids"][0],
                    result["documents"][0], result["distances"][0], result["metadatas"][0])]
