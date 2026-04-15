#!/usr/bin/env python3
"""Run RAG ingestion: chunk documents and store embeddings."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import AppConfig
from src.db.manager import DatabaseManager
from src.rag.chunker import TextChunker
from src.rag.pipeline import RAGPipeline
from src.rag.vector_store import VectorStore


def main() -> None:
    config = AppConfig.from_env()
    db = DatabaseManager(config)
    try:
        vector_store = VectorStore(config.embedding_model)
        chunker = TextChunker(chunk_size=config.chunk_size, overlap=config.chunk_overlap)
        rag = RAGPipeline(db, vector_store, chunker, top_k=config.rag_top_k)

        total = rag.ingest(reset=True)
        print(f"Ingestion complete: {total} chunks stored.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
