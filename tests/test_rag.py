"""Tests for RAG pipeline components."""

from src.models.results import SearchResult
from src.rag.chunker import TextChunker
from src.rag.pipeline import RAGPipeline


class _FakeDB:
    def search_similar_chunks(self, query_embedding, top_k=3, user_id=None):
        return [
            {
                "id": 1,
                "chunk_text": "Genel öğrenci davranış kuralları ve disiplin bilgileri.",
                "title": "Öğrenci Davranış Kuralları",
                "similarity": 0.52,
            },
            {
                "id": 2,
                "chunk_text": "İlk iki hafta içinde yapılan ders bırakma işlemlerinde ceza uygulanmaz. İkinci haftadan sonra yapılan çekilmeler için W notu verilir.",
                "title": "Ders Kayıt Yönergesi",
                "similarity": 0.51,
            },
            {
                "id": 3,
                "chunk_text": "Ders bırakma son tarihleri: 2. hafta - kayıt yok, 3-10. hafta - dekan onayı ile W notu, 10. haftadan sonra WF.",
                "title": "Ders Bırakma ve Eğitime Ara Verme",
                "similarity": 0.46,
            },
        ][:top_k]

    def get_searchable_chunks(self, user_id=None):
        return [
            {
                "id": 1,
                "chunk_text": "Genel öğrenci davranış kuralları ve disiplin bilgileri.",
                "title": "Öğrenci Davranış Kuralları",
            },
            {
                "id": 2,
                "chunk_text": "İlk iki hafta içinde yapılan ders bırakma işlemlerinde ceza uygulanmaz. İkinci haftadan sonra yapılan çekilmeler için W notu verilir.",
                "title": "Ders Kayıt Yönergesi",
            },
            {
                "id": 3,
                "chunk_text": "Ders bırakma son tarihleri: 2. hafta - kayıt yok, 3-10. hafta - dekan onayı ile W notu, 10. haftadan sonra WF.",
                "title": "Ders Bırakma ve Eğitime Ara Verme",
            },
        ]


class _FakeVectorStore:
    def encode_query(self, text):
        return [0.0]

    def encode_document(self, text):
        return [0.0]


class TestTextChunker:
    def test_basic_chunking(self):
        text = " ".join(f"word{i}" for i in range(300))
        chunker = TextChunker(chunk_size=100, overlap=20)
        chunks = chunker.chunk(document_id=42, title="Guide", text=text)
        assert len(chunks) >= 2
        assert len(chunks[0].page_content.split()) == 100
        assert chunks[0].metadata["document_id"] == 42
        assert chunks[0].metadata["title"] == "Guide"
        assert chunks[0].metadata["chunk_index"] == 0

    def test_short_text(self):
        text = "hello world"
        chunker = TextChunker(chunk_size=200, overlap=50)
        chunks = chunker.chunk(document_id=1, title="Short", text=text)
        assert len(chunks) == 1
        assert chunks[0].page_content == "hello world"
        assert chunks[0].metadata["chunk_index"] == 0

    def test_empty_text(self):
        chunker = TextChunker(chunk_size=200, overlap=50)
        chunks = chunker.chunk(document_id=1, title="Empty", text="")
        assert chunks == []

    def test_overlap(self):
        text = " ".join(f"w{i}" for i in range(250))
        chunker = TextChunker(chunk_size=100, overlap=20)
        chunks = chunker.chunk(document_id=5, title="Overlap", text=text)
        tail = chunks[0].page_content.split()[-20:]
        head = chunks[1].page_content.split()[:20]
        assert tail == head


class TestSearchResult:
    def test_frozen(self):
        r = SearchResult(chunk_id=1, text="hello", document_title="doc", similarity=0.9)
        assert r.chunk_id == 1
        assert r.similarity == 0.9


class TestRAGReranking:
    def test_prefers_specific_drop_policy_document(self):
        rag = RAGPipeline(_FakeDB(), _FakeVectorStore(), TextChunker())
        results = rag.search(
            "Ders bırakma yönergesine göre W notu ne zaman verilir",
            top_k=3,
        )
        assert results[0].document_title == "Ders Bırakma ve Eğitime Ara Verme"
