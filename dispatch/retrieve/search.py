"""Semantic search with metadata-filtered retrieval."""

from __future__ import annotations
from dataclasses import dataclass

from dispatch.retrieve.store import VectorStore
from dispatch.config import CONFIG


@dataclass
class SearchResult:
    text: str
    source_type: str
    source_file: str
    pipeline: str
    score: float


def search(
    query: str,
    store: VectorStore,
    pipeline_filter: str | None = None,
    source_types: list[str] | None = None,
    top_k: int = CONFIG.top_k,
) -> list[SearchResult]:
    """
    Retrieve relevant chunks.

    Applies metadata filters before semantic scoring so results are always
    scoped to the relevant pipeline and document types — not just
    topically similar text from unrelated pipelines.
    """
    where: dict | None = None

    conditions = []
    if pipeline_filter:
        # Match either the specific pipeline or generic "*" runbooks
        conditions.append({"$or": [
            {"pipeline": {"$eq": pipeline_filter}},
            {"pipeline": {"$eq": "*"}},
        ]})
    if source_types:
        conditions.append({"source_type": {"$in": source_types}})

    if len(conditions) == 1:
        where = conditions[0]
    elif len(conditions) > 1:
        where = {"$and": conditions}

    raw = store.query(query, top_k=top_k, where=where)

    return [
        SearchResult(
            text=r["text"],
            source_type=r["metadata"]["source_type"],
            source_file=r["metadata"]["source_file"],
            pipeline=r["metadata"]["pipeline"],
            score=r["score"],
        )
        for r in raw
    ]
