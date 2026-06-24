"""Split corpus documents into overlapping chunks with source metadata."""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import re
import yaml


@dataclass
class Chunk:
    text: str
    doc_id: str
    source_type: str          # runbook | contract | incident
    pipeline: str             # "*" for generic runbooks
    tags: list[str] = field(default_factory=list)
    severity: str = ""
    source_file: str = ""


def _extract_frontmatter(text: str) -> tuple[dict, str]:
    """Pull YAML frontmatter from markdown, return (meta, body)."""
    match = re.match(r"^---\n(.*?)\n---\n?(.*)", text, re.DOTALL)
    if match:
        try:
            meta = yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError:
            meta = {}
        return meta, match.group(2).strip()
    return {}, text.strip()


def _sliding_chunks(text: str, size: int = 400, overlap: int = 80) -> list[str]:
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i : i + size])
        if chunk.strip():
            chunks.append(chunk)
        i += size - overlap
    return chunks or [text]


def chunk_markdown(path: Path, source_type: str) -> list[Chunk]:
    raw = path.read_text()
    meta, body = _extract_frontmatter(raw)
    pipeline = meta.get("pipeline", "*")
    tags = meta.get("tags", [])
    severity = meta.get("severity", "")

    return [
        Chunk(
            text=text,
            doc_id=f"{path.stem}:{i}",
            source_type=source_type,
            pipeline=pipeline,
            tags=tags,
            severity=severity,
            source_file=path.name,
        )
        for i, text in enumerate(_sliding_chunks(body))
    ]


def chunk_yaml_contract(path: Path) -> list[Chunk]:
    raw = path.read_text()
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError:
        data = {}

    pipeline = data.get("pipeline", path.stem)
    # Flatten the contract to a readable text block for embedding
    text = f"Data contract for pipeline: {pipeline}\n"
    for key, value in data.items():
        text += f"{key}: {value}\n"

    return [
        Chunk(
            text=text,
            doc_id=f"{path.stem}:0",
            source_type="contract",
            pipeline=pipeline,
            tags=["data-contract", "schema", "sla"],
            severity="",
            source_file=path.name,
        )
    ]
