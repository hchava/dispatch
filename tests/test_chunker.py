from pathlib import Path
import textwrap
import pytest

from dispatch.ingest.chunker import chunk_markdown, chunk_yaml_contract, _extract_frontmatter


def test_frontmatter_extraction():
    text = "---\npipeline: orders-fact\ntags: [a, b]\n---\nBody text here."
    meta, body = _extract_frontmatter(text)
    assert meta["pipeline"] == "orders-fact"
    assert meta["tags"] == ["a", "b"]
    assert body == "Body text here."


def test_no_frontmatter():
    text = "Just a plain document."
    meta, body = _extract_frontmatter(text)
    assert meta == {}
    assert body == "Just a plain document."


def test_chunk_markdown(tmp_path):
    content = textwrap.dedent("""\
        ---
        pipeline: orders-fact
        tags: [row-count-drop]
        severity: P1
        ---
        First section of the runbook with important triage steps.
        Second line with more details about the procedure.
    """)
    f = tmp_path / "runbook.md"
    f.write_text(content)
    chunks = chunk_markdown(f, source_type="runbook")
    assert len(chunks) >= 1
    assert chunks[0].source_type == "runbook"
    assert chunks[0].pipeline == "orders-fact"
    assert chunks[0].severity == "P1"


def test_chunk_yaml_contract(tmp_path):
    content = "pipeline: orders-fact\nowner: data-platform\nsla: daily by 08:00 UTC\n"
    f = tmp_path / "orders-fact.yaml"
    f.write_text(content)
    chunks = chunk_yaml_contract(f)
    assert len(chunks) == 1
    assert chunks[0].source_type == "contract"
    assert chunks[0].pipeline == "orders-fact"
    assert "orders-fact" in chunks[0].text
