"""LangChain-powered chunker for knowledge base documents."""

from __future__ import annotations

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


class TextChunker:
    """
    Splits documents into overlapping LangChain ``Document`` chunks so downstream
    retrievers can attach metadata such as document id/title and chunk indices.
    """

    def __init__(self, chunk_size: int = 200, overlap: int = 50) -> None:
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=overlap,
            separators=["\n\n", "\n", ". ", " "],
            length_function=lambda text: len(text.split()),
        )

    def chunk(self, document_id: int, title: str, text: str) -> list[Document]:
        base_doc = Document(
            page_content=text,
            metadata={"document_id": document_id, "title": title},
        )
        chunks = self._splitter.split_documents([base_doc])
        for idx, chunk in enumerate(chunks):
            chunk.metadata = {
                **chunk.metadata,
                "chunk_index": idx,
            }
        return chunks
