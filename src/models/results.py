"""Result value objects returned by various services."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.models.enums import AccessScope, RouteType
from src.models.user import User


@dataclass(frozen=True)
class SearchResult:
    chunk_id: int
    text: str
    document_title: str
    similarity: float


@dataclass(frozen=True)
class QueryResult:
    records: tuple[dict, ...]
    count: int
    total_amount: float | None
    access_scope: AccessScope
    filter_description: str
    table_name: str


@dataclass(frozen=True)
class DBIntent:
    table: str
    operation: str = "list"
    filters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RoutingDecision:
    route: RouteType
    rag_query: str | None
    db_table: str | None
    confidence: float
    db_intent: DBIntent | None = None
    source: str = "deterministic"


@dataclass(frozen=True)
class AssistantResponse:
    answer: str
    route: RouteType
    user: User
    rag_sources: tuple[str, ...] = ()
    rag_results: tuple[SearchResult, ...] = ()
    db_result: QueryResult | None = None
    routing_decision: RoutingDecision | None = None
