"""ChromaDB wrapper with sentence-transformer embeddings."""

from __future__ import annotations
from typing import Any
import chromadb
from chromadb.utils import embedding_functions

from pincer.config import CONFIG
from pincer.ingest.chunker import Chunk


class VectorStore:
    def __init__(self, reset: bool = False) -> None:
        self._client = chromadb.PersistentClient(path=CONFIG.chroma_path)
        self._ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=CONFIG.embedding_model
        )
        if reset:
            try:
                self._client.delete_collection(CONFIG.collection_name)
            except Exception:
                pass
        self._col = self._client.get_or_create_collection(
            name=CONFIG.collection_name,
            embedding_function=self._ef,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert(self, chunks: list[Chunk]) -> None:
        if not chunks:
            return
        self._col.upsert(
            ids=[c.doc_id for c in chunks],
            documents=[c.text for c in chunks],
            metadatas=[
                {
                    "source_type": c.source_type,
                    "pipeline": c.pipeline,
                    "tags": ",".join(c.tags),
                    "severity": c.severity,
                    "source_file": c.source_file,
                }
                for c in chunks
            ],
        )

    def query(
        self,
        text: str,
        top_k: int = CONFIG.top_k,
        where: dict[str, Any] | None = None,
    ) -> list[dict]:
        kwargs: dict[str, Any] = {
            "query_texts": [text],
            "n_results": top_k,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where

        result = self._col.query(**kwargs)
        docs = result["documents"][0]
        metas = result["metadatas"][0]
        dists = result["distances"][0]

        return [
            {
                "text": doc,
                "metadata": meta,
                "score": round(1 - dist, 4),  # cosine → similarity
            }
            for doc, meta, dist in zip(docs, metas, dists)
        ]
