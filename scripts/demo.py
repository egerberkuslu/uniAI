#!/usr/bin/env python3
"""Interactive CLI demo for the RBAC-RAG-MCP system."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import AppConfig
from src.db.manager import DatabaseManager
from src.llm.factory import LLMProviderFactory
from src.mcp.server import MCPServer
from src.rag.chunker import TextChunker
from src.rag.pipeline import RAGPipeline
from src.rag.vector_store import VectorStore
from src.rbac.auth import Authenticator
from src.rbac.engine import RBACEngine
from src.router.classifier import QueryRouter
from src.router.context_builder import ContextBuilder


TOKENS = {
    "1": ("admin_token", "Alice Chen (admin)"),
    "2": ("manager_token", "Bob Martinez (manager, electronics)"),
    "3": ("viewer_token", "Charlie Kim (viewer, electronics)"),
    "4": ("manager2_token", "Diana Lopez (manager, clothing)"),
    "5": ("viewer2_token", "Eve Johnson (viewer, books)"),
}


def main() -> None:
    config = AppConfig.from_env()

    db = DatabaseManager(config)
    llm = LLMProviderFactory.create(config)
    vector_store = VectorStore(config.embedding_model)
    chunker = TextChunker(chunk_size=config.chunk_size, overlap=config.chunk_overlap)
    rag = RAGPipeline(db, vector_store, chunker, top_k=config.rag_top_k)
    authenticator = Authenticator(db)
    rbac = RBACEngine(db, authenticator)
    router = QueryRouter(rag, threshold=config.similarity_threshold)
    ctx = ContextBuilder()

    server = MCPServer(rbac, rag, router, llm, ctx, config.llm_max_tokens)

    print("=" * 60)
    print("  RBAC-RAG-MCP Interactive Demo")
    print("=" * 60)

    while True:
        print("\nSelect user:")
        for k, (_, label) in TOKENS.items():
            print(f"  [{k}] {label}")
        print("  [q] Quit")

        choice = input("\n> ").strip()
        if choice == "q":
            break
        if choice not in TOKENS:
            print("Invalid choice.")
            continue

        token, label = TOKENS[choice]
        print(f"\nLogged in as {label}")

        while True:
            print(f"\n[{label}] Enter question (or 'back' / 'quit'):")
            question = input("> ").strip()
            if question.lower() == "back":
                break
            if question.lower() == "quit":
                db.close()
                return
            if not question:
                continue

            try:
                result = server.ask_question(token, question)
                print("\n--- Answer ---")
                print(result["answer"])
                print("\n--- Metadata ---")
                print(f"  Route: {result['route']}")
                print(f"  User:  {result['user']} ({result['role']})")
                if "rag_sources" in result:
                    print(f"  RAG sources: {', '.join(result['rag_sources'])}")
                if "db_result" in result:
                    dr = result["db_result"]
                    print(f"  DB table: {dr['table']} | Filter: {dr['filter']}")
                    total = dr.get("total_amount")
                    if total is not None:
                        print(f"  Records: {dr['count']} | Total: ${total:,.2f}")
                    else:
                        print(f"  Records: {dr['count']}")
            except Exception as e:
                print(f"\nError: {e}")

    db.close()
    print("Goodbye!")


if __name__ == "__main__":
    main()
