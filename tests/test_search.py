"""Integration test: ingest sample corpus, run a search, verify results."""

import pytest
from pathlib import Path

# Skip if chromadb or sentence-transformers not installed
pytest.importorskip("chromadb")
pytest.importorskip("sentence_transformers")

from pincer.retrieve.store import VectorStore
from pincer.retrieve.search import search
from pincer.ingest.loader import load_corpus


CORPUS = Path(__file__).parent.parent / "corpus"


@pytest.fixture(scope="module")
def store(tmp_path_factory):
    import os
    tmp = tmp_path_factory.mktemp("chroma")
    os.environ["PINCER_CHROMA_PATH"] = str(tmp)

    # Patch CONFIG to use tmp path
    import pincer.config as cfg
    original = cfg.CONFIG.chroma_path
    cfg.CONFIG.chroma_path = str(tmp)

    s = VectorStore(reset=True)
    load_corpus(CORPUS, s)
    yield s
    cfg.CONFIG.chroma_path = original


def test_search_returns_results(store):
    results = search("pipeline failure row count drop", store)
    assert len(results) > 0


def test_search_by_pipeline(store):
    results = search("schema drift", store, pipeline_filter="orders-fact")
    assert all(r.pipeline in ("orders-fact", "*") for r in results)


def test_runbook_source_type_filter(store):
    results = search("triage steps", store, source_types=["runbook"])
    assert all(r.source_type == "runbook" for r in results)


def test_scores_between_zero_and_one(store):
    results = search("SLA breach upstream dependency", store)
    assert all(0.0 <= r.score <= 1.0 for r in results)
