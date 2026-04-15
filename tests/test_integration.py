"""Integration tests — requires a running PostgreSQL with pgvector."""

import os
import sys
from pathlib import Path

import pytest

# Skip all tests if no DB connection
pytestmark = pytest.mark.skipif(
    not os.environ.get("RUN_INTEGRATION_TESTS"),
    reason="Set RUN_INTEGRATION_TESTS=1 to run integration tests",
)

from src.config import AppConfig
from src.db.manager import DatabaseManager
from src.rag.chunker import TextChunker
from src.rag.pipeline import RAGPipeline
from src.rag.vector_store import VectorStore
from src.rbac.auth import Authenticator
from src.rbac.engine import RBACEngine
from src.router.classifier import QueryRouter
from src.models.enums import AccessScope, RouteType
from src.models.exceptions import AuthenticationError, PermissionDeniedError


@pytest.fixture(scope="module")
def db():
    config = AppConfig.from_env()
    manager = DatabaseManager(config)
    manager.setup()
    yield manager
    manager.close()


@pytest.fixture(scope="module")
def rag(db):
    config = AppConfig.from_env()
    vs = VectorStore(config.embedding_model)
    chunker = TextChunker(chunk_size=config.chunk_size, overlap=config.chunk_overlap)
    pipeline = RAGPipeline(db, vs, chunker, top_k=config.rag_top_k)
    pipeline.ingest()
    return pipeline


class TestAuthenticationIntegration:
    def test_valid_admin_token(self, db):
        auth = Authenticator(db)
        user = auth.authenticate("admin_token")
        assert user.name == "Alice Chen"
        assert user.role.value == "admin"

    def test_valid_manager_token(self, db):
        auth = Authenticator(db)
        user = auth.authenticate("manager_token")
        assert user.name == "Bob Martinez"
        assert user.department == "electronics"

    def test_invalid_token(self, db):
        auth = Authenticator(db)
        with pytest.raises(AuthenticationError):
            auth.authenticate("invalid_token")


class TestRBACIntegration:
    def test_admin_sees_all_orders(self, db):
        engine = RBACEngine(db, Authenticator(db))
        user = engine.authenticate("admin_token")
        result = engine.query(user, "orders")
        assert result.count == 10
        assert result.access_scope == AccessScope.ALL

    def test_manager_sees_department_orders(self, db):
        engine = RBACEngine(db, Authenticator(db))
        user = engine.authenticate("manager_token")
        result = engine.query(user, "orders")
        assert result.count == 6  # electronics department
        assert result.access_scope == AccessScope.DEPARTMENT

    def test_viewer_sees_own_orders(self, db):
        engine = RBACEngine(db, Authenticator(db))
        user = engine.authenticate("viewer_token")
        result = engine.query(user, "orders")
        assert result.count == 3  # assigned_to = 3
        assert result.access_scope == AccessScope.OWN

    def test_admin_sees_all_refunds(self, db):
        engine = RBACEngine(db, Authenticator(db))
        user = engine.authenticate("admin_token")
        result = engine.query(user, "refunds")
        assert result.count == 6
        assert abs(result.total_amount - 1262.97) < 0.01

    def test_manager_refunds(self, db):
        engine = RBACEngine(db, Authenticator(db))
        user = engine.authenticate("manager_token")
        result = engine.query(user, "refunds")
        assert result.count == 3  # electronics department refunds
        assert abs(result.total_amount - 549.98) < 0.01

    def test_viewer_refunds(self, db):
        engine = RBACEngine(db, Authenticator(db))
        user = engine.authenticate("viewer_token")
        result = engine.query(user, "refunds")
        assert result.count == 1  # processed_by = 3
        assert abs(result.total_amount - 299.99) < 0.01

    def test_manager_student_information(self, db):
        engine = RBACEngine(db, Authenticator(db))
        user = engine.authenticate("manager_token")
        result = engine.query(user, "ogrenci_bilgi_sistemi")
        assert result.count == 3
        assert result.filter_description == "bolum = 'electronics'"

    def test_viewer_student_information(self, db):
        engine = RBACEngine(db, Authenticator(db))
        user = engine.authenticate("viewer_token")
        result = engine.query(user, "ogrenci_bilgi_sistemi")
        assert result.count == 1
        assert "advisor_id" in result.filter_description


class TestRAGIntegration:
    def test_search_returns_results(self, rag):
        results = rag.search("refund policy")
        assert len(results) > 0
        assert "Refund" in results[0].document_title

    def test_search_shipping(self, rag):
        results = rag.search("shipping delivery times")
        assert len(results) > 0


class TestRouterIntegration:
    def test_route_rag_question(self, rag):
        router = QueryRouter(rag)
        decision = router.route("What is our refund policy?")
        assert decision.route == RouteType.RAG

    def test_route_mcp_question(self, rag):
        router = QueryRouter(rag)
        decision = router.route("How many refunds were processed?")
        assert decision.route == RouteType.MCP

    def test_route_hybrid_question(self, rag):
        router = QueryRouter(rag)
        decision = router.route(
            "What is our refund policy and how many refunds happened?"
        )
        assert decision.route == RouteType.HYBRID
