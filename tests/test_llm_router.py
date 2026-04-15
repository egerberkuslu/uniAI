"""Tests for structured LLM routing."""

from unittest.mock import MagicMock

from src.models.enums import RouteType
from src.models.results import SearchResult
from src.router.classifier import QueryRouter
from src.router.llm_router import LLMQueryRouter


class _FakeLLM:
    def __init__(self, response: str) -> None:
        self.response = response

    def generate(self, system_prompt: str, user_message: str, max_tokens: int = 512) -> str:
        return self.response

    def get_model_name(self) -> str:
        return "fake-router"


def _fallback_router() -> QueryRouter:
    rag = MagicMock()
    rag.search.return_value = [
        SearchResult(chunk_id=1, text="policy", document_title="doc", similarity=0.8)
    ]
    return QueryRouter(rag)


class TestLLMQueryRouter:
    def test_routes_with_valid_structured_json(self):
        llm = _FakeLLM(
            """
            {
              "route": "hybrid",
              "rag_query": "Fazla yük almak için şartlar nelerdir?",
              "db_intent": {
                "table": "ogrenci_bilgi_sistemi",
                "operation": "count",
                "filters": {"bolum": "electronics", "gpa_gt": 3.5}
              },
              "confidence": 0.94
            }
            """
        )
        router = LLMQueryRouter(llm, _fallback_router())

        decision = router.route(
            "Ders kayıt yönergesine göre fazla yük şartları nelerdir ve electronics bölümünde GPA'si 3.5 üstü kaç öğrenci var?"
        )

        assert decision.route == RouteType.HYBRID
        assert decision.source == "llm"
        assert decision.db_intent is not None
        assert decision.db_intent.operation == "count"
        assert decision.db_intent.filters == {"bolum": "electronics", "gpa_gt": 3.5}

    def test_invalid_filter_falls_back_to_deterministic_router(self):
        llm = _FakeLLM(
            """
            {
              "route": "mcp",
              "rag_query": null,
              "db_intent": {
                "table": "ogrenci_bilgi_sistemi",
                "operation": "list",
                "filters": {"drop table users": true}
              },
              "confidence": 0.99
            }
            """
        )
        router = LLMQueryRouter(llm, _fallback_router())

        decision = router.route("Öğrenci kayıtlarını göster")

        assert decision.source == "deterministic"
