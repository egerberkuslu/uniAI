"""Tests for MCP server response serialization."""

from src.mcp.server import MCPServer
from src.models.enums import AccessScope, Role, RouteType
from src.models.results import AssistantResponse, DBIntent, QueryResult, SearchResult
from src.models.user import Permission, User


def _user() -> User:
    return User(
        id=1,
        name="Alice Chen",
        email="alice@co.com",
        role=Role.ADMIN,
        department="all",
        permissions=(Permission(resource="orders", action="read", scope=AccessScope.ALL),),
    )


class TestServerSerialization:
    def test_response_includes_rag_citations(self):
        response = AssistantResponse(
            answer="Erken kayıt onur öğrencileri ve son sınıflar içindir. [1]",
            route=RouteType.RAG,
            user=_user(),
            rag_sources=("Ders Kayıt Yönergesi",),
            rag_results=(
                SearchResult(
                    chunk_id=1,
                    text="Onur öğrencileri ve son sınıf öğrencileri için erken kayıt imkanı bulunmaktadır.",
                    document_title="Ders Kayıt Yönergesi",
                    similarity=0.91234,
                ),
            ),
        )

        payload = MCPServer._response_to_dict(response)

        assert payload["rag_sources"] == ["Ders Kayıt Yönergesi"]
        assert payload["rag_citations"][0]["index"] == 1
        assert payload["rag_citations"][0]["title"] == "Ders Kayıt Yönergesi"
        assert payload["rag_citations"][0]["similarity"] == 0.9123
        assert "erken kayıt" in payload["rag_citations"][0]["snippet"].lower()

    def test_normalize_title_citation_to_number(self):
        result = SearchResult(
            chunk_id=1,
            text="Onur öğrencileri ve son sınıflar için erken kayıt vardır.",
            document_title="Ders Kayıt Yönergesi",
            similarity=0.9,
        )

        normalized = MCPServer._normalize_rag_citations(
            "Erken kayıt mümkündür. [Ders Kayıt Yönergesi]",
            [result],
        )

        assert normalized.endswith("[1]")

    def test_apply_db_intent_filters_records_safely(self):
        result = QueryResult(
            records=(
                {"full_name": "Mert Yilmaz", "bolum": "electronics", "gpa": "3.42"},
                {"full_name": "Selin Acar", "bolum": "electronics", "gpa": "3.78"},
                {"full_name": "Ahmet Kaya", "bolum": "clothing", "gpa": "2.95"},
            ),
            count=3,
            total_amount=None,
            access_scope=AccessScope.ALL,
            filter_description="None (full access)",
            table_name="ogrenci_bilgi_sistemi",
        )
        intent = DBIntent(
            table="ogrenci_bilgi_sistemi",
            operation="count",
            filters={"bolum": "electronics", "gpa_gt": 3.5},
        )

        filtered = MCPServer._apply_db_intent(result, intent)

        assert filtered is not None
        assert filtered.count == 1
        assert filtered.records[0]["full_name"] == "Selin Acar"
        assert "intent filters" in filtered.filter_description

    def test_record_matches_numeric_comparisons(self):
        record = {"gpa": "3.78", "bolum": "electronics"}

        assert MCPServer._record_matches(record, "gpa", "gt", 3.5)
        assert MCPServer._record_matches(record, "gpa", "gte", 3.78)
        assert MCPServer._record_matches(record, "bolum", "eq", "electronics")
        assert not MCPServer._record_matches(record, "gpa", "lt", 3.5)
