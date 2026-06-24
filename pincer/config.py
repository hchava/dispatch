from pydantic import BaseModel, Field
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent


class Config(BaseModel):
    model: str = "claude-sonnet-4-6"
    embedding_model: str = "all-MiniLM-L6-v2"
    chroma_path: str = str(REPO_ROOT / ".chroma")
    collection_name: str = "pincer"
    top_k: int = 5
    confidence_threshold: float = 0.70
    max_retrieval_rounds: int = 3


CONFIG = Config()
