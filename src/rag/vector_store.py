"""LangChain embedding wrapper for storing/searching knowledge chunks."""

from __future__ import annotations

from langchain_community.embeddings import HuggingFaceEmbeddings
from src.text.normalization import augment_for_embedding


class VectorStore:
    """Encodes text using LangChain's HuggingFaceEmbeddings interface."""

    def __init__(
        self,
        model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    ) -> None:
        self._embeddings = HuggingFaceEmbeddings(model_name=model_name)

    def encode_document(self, text: str) -> list[float]:
        vectors = self._embeddings.embed_documents([augment_for_embedding(text)])
        return list(vectors[0]) if vectors else []

    def encode_query(self, text: str) -> list[float]:
        return list(self._embeddings.embed_query(augment_for_embedding(text)))
