"""Load a corpus directory into ChromaDB."""

from __future__ import annotations
from pathlib import Path
import click

from dispatch.ingest.chunker import chunk_markdown, chunk_yaml_contract, Chunk
from dispatch.retrieve.store import VectorStore


def load_corpus(corpus_dir: Path, store: VectorStore) -> int:
    chunks: list[Chunk] = []

    for runbook in (corpus_dir / "runbooks").glob("*.md"):
        chunks.extend(chunk_markdown(runbook, source_type="runbook"))

    for contract in (corpus_dir / "contracts").glob("*.yaml"):
        chunks.extend(chunk_yaml_contract(contract))

    for incident in (corpus_dir / "incidents").glob("*.md"):
        chunks.extend(chunk_markdown(incident, source_type="incident"))

    for pattern in (corpus_dir / "code_patterns").glob("*.md"):
        chunks.extend(chunk_markdown(pattern, source_type="code_pattern"))

    for example in (corpus_dir / "validation_examples").glob("*.md"):
        chunks.extend(chunk_markdown(example, source_type="validation_example"))

    store.upsert(chunks)
    return len(chunks)


@click.command()
@click.option("--corpus", default="corpus", help="Path to corpus directory")
@click.option("--reset", is_flag=True, help="Wipe and rebuild the vector store")
def main(corpus: str, reset: bool) -> None:
    from dispatch.retrieve.store import VectorStore
    from rich.console import Console

    console = Console()
    store = VectorStore(reset=reset)
    corpus_path = Path(corpus)

    if not corpus_path.exists():
        console.print(f"[red]Corpus directory not found: {corpus_path}[/red]")
        raise SystemExit(1)

    n = load_corpus(corpus_path, store)
    console.print(f"[green]Loaded {n} chunks from {corpus_path}[/green]")


if __name__ == "__main__":
    main()
