"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _env(key: str, default: str | None = None) -> str:
    value = os.environ.get(key, default)
    if value is None:
        raise ValueError(f"Missing required environment variable: {key}")
    return value


def _env_int(key: str, default: int = 0) -> int:
    return int(os.environ.get(key, str(default)))


def _env_float(key: str, default: float = 0.0) -> float:
    return float(os.environ.get(key, str(default)))


def _env_bool(key: str, default: bool = False) -> bool:
    return os.environ.get(key, str(default)).lower() in ("true", "1", "yes")


@dataclass(frozen=True)
class AppConfig:
    # Database
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "rbac_rag_db"
    db_user: str = "postgres"
    db_password: str = ""

    # LLM
    use_claude_api: bool = True
    claude_model: str = "claude-sonnet-4-20250514"
    local_model_name: str = "Qwen/Qwen2.5-1.5B-Instruct"
    ollama_host: str = "http://localhost:11434"
    llm_max_tokens: int = 512
    use_llm_router: bool = True
    llm_router_max_tokens: int = 700

    # RAG
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embedding_dim: int = 384
    chunk_size: int = 200
    chunk_overlap: int = 50
    rag_top_k: int = 3
    similarity_threshold: float = 0.3

    # MCP
    mcp_host: str = "localhost"
    mcp_port: int = 8000
    mcp_transport: str = "stdio"

    @classmethod
    def from_env(cls) -> AppConfig:
        return cls(
            db_host=_env("DB_HOST", "localhost"),
            db_port=_env_int("DB_PORT", 5432),
            db_name=_env("DB_NAME", "rbac_rag_db"),
            db_user=_env("DB_USER", "postgres"),
            db_password=_env("DB_PASSWORD", ""),
            use_claude_api=_env_bool("USE_CLAUDE_API", True),
            claude_model=_env("CLAUDE_MODEL", "claude-sonnet-4-20250514"),
            local_model_name=_env("LOCAL_MODEL_NAME", "Qwen/Qwen2.5-1.5B-Instruct"),
            ollama_host=_env("OLLAMA_HOST", "http://localhost:11434"),
            llm_max_tokens=_env_int("LLM_MAX_TOKENS", 512),
            use_llm_router=_env_bool("USE_LLM_ROUTER", True),
            llm_router_max_tokens=_env_int("LLM_ROUTER_MAX_TOKENS", 700),
            embedding_model=_env(
                "EMBEDDING_MODEL",
                "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            ),
            embedding_dim=_env_int("EMBEDDING_DIM", 384),
            chunk_size=_env_int("CHUNK_SIZE", 200),
            chunk_overlap=_env_int("CHUNK_OVERLAP", 50),
            rag_top_k=_env_int("RAG_TOP_K", 3),
            similarity_threshold=_env_float("SIMILARITY_THRESHOLD", 0.3),
            mcp_host=_env("MCP_HOST", "localhost"),
            mcp_port=_env_int("MCP_PORT", 8000),
            mcp_transport=_env("MCP_TRANSPORT", "stdio"),
        )
