"""FastMCP server — thin facade that wires all components together."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
import os
import re
from typing import Any

from src.config import AppConfig
from src.db.manager import DatabaseManager
from src.llm.base import LLMProvider
from src.llm.factory import LLMProviderFactory
from src.models.enums import RouteType
from src.models.exceptions import AuthenticationError, PermissionDeniedError
from src.models.results import AssistantResponse, DBIntent, QueryResult
from src.models.user import User
from src.rag.chunker import TextChunker
from src.rag.pipeline import RAGPipeline
from src.rag.vector_store import VectorStore
from src.rbac.auth import Authenticator
from src.rbac.engine import RBACEngine
from src.router.classifier import QueryRouter
from src.router.context_builder import ContextBuilder
from src.router.llm_router import ALLOWED_FILTERS, LLMQueryRouter
from src.text.normalization import normalize_for_matching

from fastmcp import FastMCP


# ======================================================================
# Session Management
# ======================================================================

class SessionManager:
    """Simple session store for user tokens."""

    def __init__(self):
        self._sessions: dict[str, str] = {}
        # Default session from environment if available
        default_token = os.getenv("DEFAULT_USER_TOKEN")
        if default_token:
            self._sessions["default"] = default_token

    def set_token(self, session_id: str, token: str) -> None:
        """Store token for a session."""
        self._sessions[session_id] = token

    def get_token(self, session_id: str = "default") -> str | None:
        """Retrieve token for a session."""
        return self._sessions.get(session_id)

    def clear_token(self, session_id: str = "default") -> None:
        """Clear token for a session."""
        self._sessions.pop(session_id, None)

    def has_token(self, session_id: str = "default") -> bool:
        """Check if session has a token."""
        return session_id in self._sessions


# ======================================================================
# MCPServer — orchestrates all the pieces
# ======================================================================

class MCPServer:
    """Facade that wires together all components and exposes MCP tools."""

    def __init__(
        self,
        rbac: RBACEngine,
        rag: RAGPipeline,
        router: QueryRouter,
        llm: LLMProvider,
        context_builder: ContextBuilder,
        max_llm_tokens: int,
    ) -> None:
        self._rbac = rbac
        self._rag = rag
        self._router = router
        self._llm = llm
        self._ctx = context_builder
        self._max_llm_tokens = max_llm_tokens
        self._session_manager = SessionManager()

    # ------------------------------------------------------------------
    # Tool implementations
    # ------------------------------------------------------------------

    def search_knowledge(self, query: str, top_k: int = 3) -> dict:
        """
        Open RAG search — no auth required.
        Returns list of matching KB chunks with scores.
        """
        results = self._rag.search(query, top_k=top_k)
        return {
            "results": [
                {
                    "chunk_id": r.chunk_id,
                    "text": r.text,
                    "snippet": self._build_snippet(r.text),
                    "document_title": r.document_title,
                    "similarity": round(r.similarity, 4),
                }
                for r in results
            ],
            "count": len(results),
        }

    def query_records(self, token: str, table: str) -> dict:
        """
        RBAC-filtered database query.
        Requires token. Returns filtered records based on user's role.
        """
        user = self._rbac.authenticate(token)
        result = self._rbac.query(user, table)
        return self._query_result_to_dict(result)

    def query_records_intent(
        self,
        table: str,
        operation: str = "list",
        filters: dict[str, Any] | None = None,
        token: str | None = None,
    ) -> dict:
        """
        RBAC-safe structured DB tool. The caller provides intent, not SQL.
        Backend validates allowed filters and applies them after RBAC filtering.
        Token is optional; if not provided, uses session token.
        """
        final_token = token or self._session_manager.get_token()
        if not final_token:
            raise AuthenticationError("No token provided and no session token set. Use set_user_token() first.")
        user = self._rbac.authenticate(final_token)
        intent = DBIntent(table=table, operation=operation, filters=filters or {})
        result = self._rbac.query(user, table)
        result = self._apply_db_intent(result, intent)
        payload = self._query_result_to_dict(result)
        payload["operation"] = operation
        payload["intent_filters"] = filters or {}
        return payload

    def fetch_source(self, token: str, chunk_id: int) -> dict:
        """Fetch a RAG source chunk by id, respecting user-owned document visibility."""
        user = self._rbac.authenticate(token)
        db = self._rag._db
        row = db.get_chunk_by_id(chunk_id, user.id)
        if row is None:
            raise PermissionDeniedError(f"Source chunk {chunk_id} not found or not visible")
        return {
            "chunk_id": row["id"],
            "document_id": row["document_id"],
            "document_title": row["title"],
            "category": row.get("category"),
            "chunk_index": row["chunk_index"],
            "text": row["chunk_text"],
            "snippet": self._build_snippet(row["chunk_text"]),
        }

    def ask_question(self, token: str, question: str) -> dict:
        """
        Smart routed question answering.
        1. Authenticate user
        2. Route query (RAG / MCP / HYBRID)
        3. Fetch data from relevant sources
        4. Build prompt → generate answer
        5. Return answer + metadata
        """
        user = self._rbac.authenticate(token)
        decision = self._router.route(question)

        rag_results = None
        db_result = None

        if decision.route in (RouteType.RAG, RouteType.HYBRID):
            rag_results = self._rag.search(decision.rag_query or question, user_id=user.id)

        if decision.route in (RouteType.MCP, RouteType.HYBRID):
            table = decision.db_table or "orders"
            db_result = self._rbac.query(user, table)
            db_result = self._apply_db_intent(db_result, decision.db_intent)

        system_prompt = self._ctx.build_system_prompt(user, question)
        user_message = self._ctx.build_user_message(
            question=question,
            rag_results=rag_results,
            db_result=db_result,
            user=user,
        )

        answer = self._llm.generate(
            system_prompt,
            user_message,
            max_tokens=self._max_llm_tokens,
        )
        answer = self._normalize_rag_citations(answer, rag_results)

        response = AssistantResponse(
            answer=answer,
            route=decision.route,
            user=user,
            rag_sources=tuple(r.document_title for r in rag_results) if rag_results else (),
            rag_results=tuple(rag_results) if rag_results else (),
            db_result=db_result,
            routing_decision=decision,
        )

        return self._response_to_dict(response)

    def list_permissions(self, token: str) -> dict:
        """Show user's access level and permissions."""
        user = self._rbac.authenticate(token)
        return self._rbac.get_permissions_summary(user)

    def route_question(self, question: str, token: str | None = None) -> dict:
        """
        Expose the structured routing decision as an MCP/debug tool.
        Token is optional; if not provided, uses session token.
        """
        final_token = token or self._session_manager.get_token()
        if not final_token:
            raise AuthenticationError("No token provided and no session token set. Use set_user_token() first.")
        self._rbac.authenticate(final_token)
        decision = self._router.route(question)
        return self._routing_decision_to_dict(decision)

    def ingest_all_documents(self, reset: bool = True) -> dict:
        """Re-run the RAG ingestion pipeline (optionally resetting existing chunks)."""
        total = self._rag.ingest(reset=reset)
        return {"status": "ok", "chunks_ingested": total, "reset": reset}

    def ingest_document(
        self, token: str, title: str, content: str, category: str | None = None
    ) -> dict:
        """Add a new document to the knowledge base and chunk/index it with user association."""
        user = self._rbac.authenticate(token)
        return self._rag.ingest_document(title, content, category, user.id)

    def list_user_documents(self, token: str) -> dict:
        """List all documents uploaded by the authenticated user."""
        user = self._rbac.authenticate(token)
        from src.db.manager import DatabaseManager
        db = self._rag._db
        docs = db.get_user_documents(user.id)
        return {"documents": docs, "count": len(docs)}

    def delete_user_document(self, token: str, doc_id: int) -> dict:
        """Delete a document uploaded by the authenticated user."""
        user = self._rbac.authenticate(token)
        from src.db.manager import DatabaseManager
        db = self._rag._db
        deleted = db.delete_document(doc_id, user.id)
        if not deleted:
            raise PermissionDeniedError(f"Document {doc_id} not found or not owned by user")
        return {"status": "deleted", "document_id": doc_id}

    # ------------------------------------------------------------------
    # Session management tools
    # ------------------------------------------------------------------

    def set_user_token(self, token: str, session_id: str = "default") -> dict:
        """
        Set authentication token for the current session.
        Use this once at the start of your conversation to avoid passing token in every call.
        """
        # Validate token by attempting to authenticate
        user = self._rbac.authenticate(token)
        self._session_manager.set_token(session_id, token)
        return {
            "status": "ok",
            "message": f"Token set for session '{session_id}'",
            "user": user.name,
            "role": user.role.value,
            "masked_token": f"{token[:8]}..." if len(token) > 8 else "***",
        }

    def get_current_token(self, session_id: str = "default") -> dict:
        """
        Get the currently set token for this session (masked for security).
        """
        token = self._session_manager.get_token(session_id)
        if not token:
            return {
                "status": "no_token",
                "message": f"No token set for session '{session_id}'",
            }
        # Authenticate to show user info
        user = self._rbac.authenticate(token)
        return {
            "status": "ok",
            "session_id": session_id,
            "user": user.name,
            "role": user.role.value,
            "masked_token": f"{token[:8]}..." if len(token) > 8 else "***",
        }

    def clear_token(self, session_id: str = "default") -> dict:
        """
        Clear the authentication token for this session.
        """
        had_token = self._session_manager.has_token(session_id)
        self._session_manager.clear_token(session_id)
        return {
            "status": "ok",
            "message": f"Token cleared for session '{session_id}'" if had_token else f"No token was set for session '{session_id}'",
        }

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _query_result_to_dict(result: QueryResult) -> dict:
        payload = {
            "table": result.table_name,
            "filter": result.filter_description,
            "access_scope": result.access_scope.value,
            "count": result.count,
            "records": [
                {k: str(v) if hasattr(v, "__str__") else v for k, v in rec.items()}
                for rec in result.records
            ],
        }
        if result.total_amount is not None:
            payload["total_amount"] = result.total_amount
        return payload

    @staticmethod
    def _response_to_dict(resp: AssistantResponse) -> dict:
        d: dict = {
            "answer": resp.answer,
            "route": resp.route.value,
            "user": resp.user.name,
            "role": resp.user.role.value,
        }
        if resp.rag_sources:
            d["rag_sources"] = list(resp.rag_sources)
        if resp.rag_results:
            d["rag_citations"] = [
                {
                    "index": index,
                    "title": result.document_title,
                    "similarity": round(result.similarity, 4),
                    "snippet": MCPServer._build_snippet(result.text),
                }
                for index, result in enumerate(resp.rag_results, start=1)
            ]
        if resp.db_result:
            d["db_result"] = MCPServer._query_result_to_dict(resp.db_result)
        if resp.routing_decision:
            d["routing_decision"] = MCPServer._routing_decision_to_dict(resp.routing_decision)
        return d

    @staticmethod
    def _build_snippet(text: str, max_len: int = 220) -> str:
        compact = " ".join(text.split())
        if len(compact) <= max_len:
            return compact
        return compact[: max_len - 1].rstrip() + "…"

    @staticmethod
    def _normalize_rag_citations(
        answer: str,
        rag_results: list | tuple | None,
    ) -> str:
        if not answer or not rag_results:
            return answer

        title_to_index = {
            normalize_for_matching(result.document_title): idx
            for idx, result in enumerate(rag_results, start=1)
        }

        def replace_match(match: re.Match[str]) -> str:
            inner = match.group(1).strip()
            if inner.isdigit():
                return match.group(0)
            index = title_to_index.get(normalize_for_matching(inner))
            return f"[{index}]" if index is not None else match.group(0)

        return re.sub(r"\[([^\[\]]+)\]", replace_match, answer)

    @staticmethod
    def _routing_decision_to_dict(decision) -> dict:
        payload = {
            "route": decision.route.value,
            "rag_query": decision.rag_query,
            "db_table": decision.db_table,
            "confidence": decision.confidence,
            "source": decision.source,
        }
        if decision.db_intent:
            payload["db_intent"] = {
                "table": decision.db_intent.table,
                "operation": decision.db_intent.operation,
                "filters": decision.db_intent.filters,
            }
        return payload

    @staticmethod
    def _apply_db_intent(result: QueryResult | None, intent: DBIntent | None) -> QueryResult | None:
        if result is None or intent is None or not intent.filters:
            return result
        if intent.table != result.table_name:
            return result

        allowed = ALLOWED_FILTERS.get(result.table_name, set())
        filtered_records = list(result.records)
        applied: list[str] = []

        for key, value in intent.filters.items():
            if key not in allowed:
                continue
            column, operator = MCPServer._split_filter_key(key)
            filtered_records = [
                record for record in filtered_records
                if MCPServer._record_matches(record, column, operator, value)
            ]
            applied.append(MCPServer._describe_filter(column, operator, value))

        records = tuple(filtered_records)
        total_amount = None
        if records and "amount" in records[0]:
            total_amount = sum(float(record.get("amount", 0)) for record in records)

        description = result.filter_description
        if applied:
            description = f"{description}; intent filters: {', '.join(applied)}"

        return replace(
            result,
            records=records,
            count=len(records),
            total_amount=total_amount,
            filter_description=description,
        )

    @staticmethod
    def _split_filter_key(key: str) -> tuple[str, str]:
        for suffix, operator in (
            ("_gte", "gte"),
            ("_lte", "lte"),
            ("_gt", "gt"),
            ("_lt", "lt"),
        ):
            if key.endswith(suffix):
                return key[: -len(suffix)], operator
        return key, "eq"

    @staticmethod
    def _record_matches(record: dict, column: str, operator: str, expected: Any) -> bool:
        actual = record.get(column)
        if actual is None:
            return False

        if operator == "eq":
            return str(actual).casefold() == str(expected).casefold()

        try:
            actual_num = float(actual) if not isinstance(actual, Decimal) else float(actual)
            expected_num = float(expected)
        except (TypeError, ValueError):
            return False

        if operator == "gt":
            return actual_num > expected_num
        if operator == "gte":
            return actual_num >= expected_num
        if operator == "lt":
            return actual_num < expected_num
        if operator == "lte":
            return actual_num <= expected_num
        return False

    @staticmethod
    def _describe_filter(column: str, operator: str, value: Any) -> str:
        symbols = {"eq": "=", "gt": ">", "gte": ">=", "lt": "<", "lte": "<="}
        return f"{column} {symbols.get(operator, operator)} {value!r}"


# ======================================================================
# Factories
# ======================================================================
 
def build_server(config: AppConfig | None = None) -> MCPServer:
    if config is None:
        config = AppConfig.from_env()

    db = DatabaseManager(config)
    llm = LLMProviderFactory.create(config)
    vector_store = VectorStore(config.embedding_model)
    chunker = TextChunker(chunk_size=config.chunk_size, overlap=config.chunk_overlap)
    rag = RAGPipeline(db, vector_store, chunker, top_k=config.rag_top_k)
    authenticator = Authenticator(db)
    rbac = RBACEngine(db, authenticator)
    fallback_router = QueryRouter(rag, threshold=config.similarity_threshold)
    router = (
        LLMQueryRouter(llm, fallback_router, max_tokens=config.llm_router_max_tokens)
        if config.use_llm_router
        else fallback_router
    )
    ctx = ContextBuilder()

    return MCPServer(rbac, rag, router, llm, ctx, config.llm_max_tokens)


def create_app(config: AppConfig | None = None) -> FastMCP:
    """
    Factory that wires every component and returns a FastMCP instance.
    """
    if config is None:
        config = AppConfig.from_env()

    server: MCPServer | None = None

    def get_server() -> MCPServer:
        nonlocal server
        if server is None:
            server = build_server(config)
        return server

    # Create FastMCP app and register tools
    mcp = FastMCP("rbac-rag-mcp")

    @mcp.tool()
    def search_knowledge(query: str, top_k: int = 3) -> dict:
        """Search the open knowledge base (company policies, guides). No authentication required."""
        return get_server().search_knowledge(query, top_k)

    @mcp.tool()
    def query_records(token: str, table: str) -> dict:
        """Query protected database tables (orders, refunds, ogrenci_bilgi_sistemi) with RBAC filtering. Requires auth token."""
        return get_server().query_records(token, table)

    @mcp.tool()
    def query_records_intent(
        table: str,
        operation: str = "list",
        filters: dict | None = None,
        token: str | None = None,
    ) -> dict:
        """Run a structured, RBAC-safe database intent. Never accepts SQL; filters are allowlisted and applied after RBAC. Token is optional if session token is set."""
        return get_server().query_records_intent(table, operation, filters, token)

    @mcp.tool()
    def fetch_source(token: str, chunk_id: int) -> dict:
        """Fetch one cited RAG source chunk by chunk_id, respecting public/user document visibility."""
        return get_server().fetch_source(token, chunk_id)

    @mcp.tool()
    def ask_question(token: str, question: str) -> dict:
        """Ask a natural-language question. The system automatically routes to knowledge base, database, or both."""
        return get_server().ask_question(token, question)

    @mcp.tool()
    def route_question(question: str, token: str | None = None) -> dict:
        """Return the structured routing decision without executing RAG/DB answer generation. Token is optional if session token is set."""
        return get_server().route_question(question, token)

    @mcp.tool()
    def list_permissions(token: str) -> dict:
        """List the authenticated user's role, department, and resource permissions."""
        return get_server().list_permissions(token)

    @mcp.tool()
    def set_user_token(token: str, session_id: str = "default") -> dict:
        """Set your authentication token for this session. Use this once to avoid passing token in every call."""
        return get_server().set_user_token(token, session_id)

    @mcp.tool()
    def get_current_token(session_id: str = "default") -> dict:
        """Get the currently set token for this session (masked for security)."""
        return get_server().get_current_token(session_id)

    @mcp.tool()
    def clear_token(session_id: str = "default") -> dict:
        """Clear the authentication token for this session."""
        return get_server().clear_token(session_id)

    return mcp


# ======================================================================
# Entry point: run with `python -m src.mcp.server`
# ======================================================================

_mcp_app: FastMCP | None = None


def get_mcp_app() -> FastMCP:
    global _mcp_app
    if _mcp_app is None:
        _mcp_app = create_app()
    return _mcp_app


if __name__ == "__main__":
    runtime_cfg = AppConfig.from_env()
    if runtime_cfg.mcp_transport == "stdio":
        get_mcp_app().run(transport="stdio", show_banner=False)
    else:
        get_mcp_app().run(
            transport=runtime_cfg.mcp_transport,
            show_banner=True,
            host=runtime_cfg.mcp_host,
            port=runtime_cfg.mcp_port,
        )
