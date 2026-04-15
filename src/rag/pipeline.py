"""LangChain-powered RAG pipeline — open access knowledge retrieval."""

from __future__ import annotations

from collections import Counter

from langchain_core.documents import Document

from src.db.manager import DatabaseManager
from src.models.results import SearchResult
from src.rag.chunker import TextChunker
from src.rag.vector_store import VectorStore
from src.text.normalization import normalize_for_matching, tokenize_for_matching


class RAGPipeline:
    """RAG search built from LangChain chunkers + embeddings over pgvector."""

    def __init__(
        self,
        db: DatabaseManager,
        vector_store: VectorStore,
        chunker: TextChunker,
        top_k: int = 3,
    ) -> None:
        self._db = db
        self._vs = vector_store
        self._chunker = chunker
        self._top_k = top_k

    def ingest(self, reset: bool = True) -> int:
        """Ingest documents into pgvector using LangChain chunker + embeddings."""
        if reset:
            self._db.reset_kb_chunks()

        documents = self._db.get_all_documents()
        total_chunks = 0

        for doc in documents:
            chunks = self._chunker.chunk(
                document_id=doc["id"],
                title=doc["title"],
                text=doc["content"],
            )
            for chunk in chunks:
                embedding = self._vs.encode_document(chunk.page_content)
                self._db.store_chunk(
                    doc["id"],
                    chunk.page_content,
                    chunk.metadata.get("chunk_index", total_chunks),
                    embedding,
                )
                total_chunks += 1

        print(f"Ingested {total_chunks} chunks from {len(documents)} documents")
        return total_chunks

    def search(self, query: str, top_k: int | None = None, user_id: int | None = None) -> list[SearchResult]:
        limit = top_k or self._top_k
        query_embedding = self._vs.encode_query(query)
        candidate_limit = max(limit * 4, 8)
        documents = self._retrieve_documents(query_embedding, candidate_limit, user_id)
        vector_results = [
            SearchResult(
                chunk_id=int(doc.metadata.get("chunk_id", idx)),
                text=doc.page_content,
                document_title=str(doc.metadata.get("title", "")),
                similarity=float(doc.metadata.get("similarity", 0.0)),
            )
            for idx, doc in enumerate(documents)
        ]
        lexical_results = self._lexical_search(query, candidate_limit, user_id)
        return self._merge_results(query, vector_results, lexical_results, limit)

    def _retrieve_documents(
        self, query_embedding: list[float], top_k: int, user_id: int | None = None
    ) -> list[Document]:
        raw = self._db.search_similar_chunks(query_embedding, top_k=top_k, user_id=user_id)
        return [
            Document(
                page_content=row["chunk_text"],
                metadata={
                    "chunk_id": row["id"],
                    "title": row["title"],
                    "similarity": float(row["similarity"]),
                },
            )
            for row in raw
        ]

    def _lexical_search(
        self, query: str, top_k: int, user_id: int | None = None
    ) -> list[SearchResult]:
        query_tokens = tuple(dict.fromkeys(tokenize_for_matching(query)))
        if not query_tokens:
            return []

        normalized_query = normalize_for_matching(query)
        candidates = self._db.get_searchable_chunks(user_id=user_id)
        scored: list[SearchResult] = []

        for row in candidates:
            title = str(row["title"])
            text = str(row["chunk_text"])
            title_tokens = set(tokenize_for_matching(title))
            ordered_title_tokens = tokenize_for_matching(title)
            text_tokens = set(tokenize_for_matching(text))
            haystack = f"{title}\n{text}"
            normalized_haystack = normalize_for_matching(haystack)
            haystack_tokens = tokenize_for_matching(haystack)
            title_overlap = sum(1 for token in query_tokens if token in title_tokens)
            text_overlap = sum(1 for token in query_tokens if token in text_tokens)
            if title_overlap == 0 and text_overlap == 0:
                continue

            title_coverage = title_overlap / len(query_tokens)
            text_coverage = text_overlap / len(query_tokens)
            title_bigram_coverage = self._ngram_overlap(query_tokens, ordered_title_tokens, 2)
            title_trigram_coverage = self._ngram_overlap(query_tokens, ordered_title_tokens, 3)
            bigram_coverage = self._ngram_overlap(query_tokens, haystack_tokens, 2)
            trigram_coverage = self._ngram_overlap(query_tokens, haystack_tokens, 3)
            phrase_bonus = 0.15 if normalized_query and normalized_query in normalized_haystack else 0.0
            title_bonus = 0.15 if title_overlap > 0 else 0.0
            similarity = min(
                0.99,
                (title_coverage * 0.75)
                + (text_coverage * 0.45)
                + (title_bigram_coverage * 1.2)
                + (title_trigram_coverage * 1.35)
                + (bigram_coverage * 0.8)
                + (trigram_coverage * 0.9)
                + phrase_bonus
                + title_bonus,
            )
            scored.append(
                SearchResult(
                    chunk_id=int(row["id"]),
                    text=text,
                    document_title=title,
                    similarity=similarity,
                )
            )

        return sorted(scored, key=lambda result: result.similarity, reverse=True)[:top_k]

    @staticmethod
    def _merge_results(
        query: str,
        vector_results: list[SearchResult],
        lexical_results: list[SearchResult],
        top_k: int,
    ) -> list[SearchResult]:
        query_tokens = tokenize_for_matching(query)
        merged: dict[int, dict[str, SearchResult | float]] = {}
        for result in vector_results:
            merged.setdefault(result.chunk_id, {"result": result, "vector": 0.0, "lexical": 0.0})
            merged[result.chunk_id]["result"] = result
            merged[result.chunk_id]["vector"] = result.similarity

        for result in lexical_results:
            merged.setdefault(result.chunk_id, {"result": result, "vector": 0.0, "lexical": 0.0})
            merged[result.chunk_id]["result"] = result
            merged[result.chunk_id]["lexical"] = result.similarity

        ranked: list[tuple[tuple[float, float, float, float, float], SearchResult]] = []
        for item in merged.values():
            result = item["result"]
            vector_score = float(item["vector"])
            lexical_score = float(item["lexical"])
            combined = max(vector_score, lexical_score, (vector_score * 0.45) + (lexical_score * 0.85))
            title_tokens = tokenize_for_matching(result.document_title)
            title_overlap = sum(1 for token in query_tokens if token in title_tokens)
            title_bigram = RAGPipeline._ngram_overlap(query_tokens, title_tokens, 2)
            ranked.append(
                (
                    (title_bigram, float(title_overlap), combined, lexical_score, vector_score),
                    SearchResult(
                        chunk_id=result.chunk_id,
                        text=result.text,
                        document_title=result.document_title,
                        similarity=min(0.99, combined),
                    ),
                )
            )

        return [
            result
            for _, result in sorted(ranked, key=lambda item: item[0], reverse=True)[:top_k]
        ]

    @staticmethod
    def _ngram_overlap(
        query_tokens: tuple[str, ...],
        haystack_tokens: tuple[str, ...],
        size: int,
    ) -> float:
        if len(query_tokens) < size or len(haystack_tokens) < size:
            return 0.0

        query_ngrams = Counter(
            tuple(query_tokens[idx: idx + size])
            for idx in range(len(query_tokens) - size + 1)
        )
        haystack_ngrams = {
            tuple(haystack_tokens[idx: idx + size])
            for idx in range(len(haystack_tokens) - size + 1)
        }
        matches = sum(1 for ngram in query_ngrams if ngram in haystack_ngrams)
        return matches / len(query_ngrams)

    def ingest_document(
        self,
        title: str,
        content: str,
        category: str | None = None,
        user_id: int | None = None,
    ) -> dict:
        doc_id = self._db.create_document(title, content, category, user_id)
        chunks = self._chunker.chunk(doc_id, title, content)
        for chunk in chunks:
            embedding = self._vs.encode_document(chunk.page_content)
            self._db.store_chunk(
                doc_id,
                chunk.page_content,
                chunk.metadata.get("chunk_index", 0),
                embedding,
            )
        return {"document_id": doc_id, "chunks": len(chunks)}
