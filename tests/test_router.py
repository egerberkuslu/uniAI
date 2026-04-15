"""Tests for the query router."""

from unittest.mock import MagicMock

from src.models.enums import RouteType
from src.models.results import RoutingDecision, SearchResult
from src.router.classifier import QueryRouter


def _mock_rag():
    rag = MagicMock()
    rag.search.return_value = [
        SearchResult(chunk_id=1, text="policy", document_title="doc", similarity=0.8)
    ]
    return rag


class TestQueryRouter:
    def test_rag_only_keywords(self):
        router = QueryRouter(_mock_rag())
        decision = router.route("What is our refund policy?")
        assert decision.route == RouteType.RAG
        assert decision.rag_query is not None
        assert decision.db_table is None

    def test_mcp_only_keywords(self):
        router = QueryRouter(_mock_rag())
        decision = router.route("How many refunds were processed?")
        assert decision.route == RouteType.MCP
        assert decision.db_table is not None
        assert decision.rag_query is None

    def test_hybrid_keywords(self):
        router = QueryRouter(_mock_rag())
        decision = router.route(
            "What is our refund policy and how many refunds did we process?"
        )
        assert decision.route == RouteType.HYBRID
        assert decision.rag_query is not None
        assert decision.db_table is not None

    def test_refund_table_detection(self):
        router = QueryRouter(_mock_rag())
        decision = router.route("How many refunds were processed?")
        assert decision.db_table == "refunds"

    def test_orders_table_default(self):
        router = QueryRouter(_mock_rag())
        decision = router.route("Show me the count of records")
        assert decision.db_table == "orders"

    def test_routes_to_student_information_table(self):
        router = QueryRouter(_mock_rag())
        decision = router.route("List ogrenci GPA for electronics")
        assert decision.db_table == "ogrenci_bilgi_sistemi"
        assert decision.route == RouteType.MCP

    def test_routes_turkish_student_query(self):
        router = QueryRouter(_mock_rag())
        decision = router.route("Öğrenci not ortalamasını ve danışmanını göster")
        assert decision.db_table == "ogrenci_bilgi_sistemi"
        assert decision.route == RouteType.MCP

    def test_routes_turkish_policy_query(self):
        router = QueryRouter(_mock_rag())
        decision = router.route("Ders kayıt yönergesi nedir?")
        assert decision.route == RouteType.RAG

    def test_student_policy_question_stays_rag(self):
        router = QueryRouter(_mock_rag())
        decision = router.route("ogrenci sikayet proseduru nedir?")
        assert decision.route == RouteType.RAG

    def test_hybrid_query_extracts_rag_clause(self):
        router = QueryRouter(_mock_rag())
        decision = router.route(
            "Ders bırakma yönergesine göre W notu ne zaman verilir ve electronics bölümünde kaç öğrenci var?"
        )
        assert decision.route == RouteType.HYBRID
        assert decision.rag_query == "Ders bırakma yönergesine göre W notu ne zaman verilir"

    def test_detects_student_filters_for_deterministic_fallback(self):
        router = QueryRouter(_mock_rag())
        decision = router.route(
            "Electronics bölümünde GPA'si 3.5 üstü kaç öğrenci var?"
        )
        assert decision.db_intent is not None
        assert decision.db_intent.operation == "count"
        assert decision.db_intent.filters == {"bolum": "electronics", "gpa_gt": 3.5}

    def test_fallback_to_rag_on_similarity(self):
        rag = MagicMock()
        rag.search.return_value = [
            SearchResult(chunk_id=1, text="onboarding", document_title="doc", similarity=0.5)
        ]
        router = QueryRouter(rag, threshold=0.3)
        # No keywords match → fallback to RAG similarity
        decision = router.route("Tell me about onboarding process")
        assert decision.route == RouteType.RAG

    def test_fallback_defaults_to_rag_when_uncertain(self):
        rag = MagicMock()
        rag.search.return_value = [
            SearchResult(chunk_id=1, text="x", document_title="doc", similarity=0.1)
        ]
        router = QueryRouter(rag, threshold=0.3)
        decision = router.route("Something random xyz")
        assert decision.route == RouteType.RAG
        assert decision.db_table is None
