"""Structured LLM router with deterministic fallback and schema validation."""

from __future__ import annotations

import json
import re
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

from src.llm.base import LLMProvider
from src.models.enums import RouteType
from src.models.results import DBIntent, RoutingDecision
from src.router.classifier import QueryRouter


ALLOWED_TABLES = {"orders", "refunds", "ogrenci_bilgi_sistemi"}
ALLOWED_OPERATIONS = {"list", "count", "sum", "average", "max", "min"}
ALLOWED_FILTERS = {
    "orders": {"department", "status", "assigned_to", "amount_gt", "amount_gte", "amount_lt", "amount_lte"},
    "refunds": {"department", "processed_by", "amount_gt", "amount_gte", "amount_lt", "amount_lte"},
    "ogrenci_bilgi_sistemi": {"bolum", "sinif", "advisor_id", "gpa_gt", "gpa_gte", "gpa_lt", "gpa_lte"},
}


class StructuredDBIntent(BaseModel):
    table: Literal["orders", "refunds", "ogrenci_bilgi_sistemi"]
    operation: Literal["list", "count", "sum", "average", "max", "min"] = "list"
    filters: dict[str, Any] = Field(default_factory=dict)

    @field_validator("filters")
    @classmethod
    def validate_filters(cls, filters: dict[str, Any], info) -> dict[str, Any]:
        table = info.data.get("table")
        allowed = ALLOWED_FILTERS.get(table, set())
        unknown = set(filters) - allowed
        if unknown:
            raise ValueError(f"unsupported filters for {table}: {sorted(unknown)}")
        return filters


class StructuredRoute(BaseModel):
    route: Literal["rag", "mcp", "hybrid"]
    rag_query: str | None = None
    db_intent: StructuredDBIntent | None = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    @field_validator("rag_query")
    @classmethod
    def normalize_rag_query(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class LLMQueryRouter:
    """Routes questions by asking the LLM for a constrained JSON intent."""

    def __init__(
        self,
        llm: LLMProvider,
        fallback_router: QueryRouter,
        max_tokens: int = 700,
    ) -> None:
        self._llm = llm
        self._fallback = fallback_router
        self._max_tokens = max_tokens

    def route(self, query: str) -> RoutingDecision:
        fallback = self._fallback.route(query)

        try:
            raw = self._llm.generate(
                self._build_system_prompt(),
                self._build_user_message(query, fallback),
                max_tokens=self._max_tokens,
            )
            structured = StructuredRoute.model_validate_json(self._extract_json(raw))
            decision = self._to_routing_decision(structured, fallback)
            if decision.confidence < 0.55:
                return fallback
            return decision
        except (ValidationError, ValueError, json.JSONDecodeError):
            return fallback
        except Exception:
            return fallback

    @staticmethod
    def _build_system_prompt() -> str:
        return (
            "You are a production query router. Return ONLY valid JSON. "
            "Do not answer the user. Do not write SQL. "
            "Your job is to classify a Turkish or English university assistant question into route and structured intent. "
            "Allowed route values: rag, mcp, hybrid. "
            "Allowed tables: orders, refunds, ogrenci_bilgi_sistemi. "
            "Allowed operations: list, count, sum, average, max, min. "
            "Allowed filters by table: "
            "ogrenci_bilgi_sistemi={bolum,sinif,advisor_id,gpa_gt,gpa_gte,gpa_lt,gpa_lte}; "
            "orders={department,status,assigned_to,amount_gt,amount_gte,amount_lt,amount_lte}; "
            "refunds={department,processed_by,amount_gt,amount_gte,amount_lt,amount_lte}. "
            "Use rag for document/policy/regulation questions. "
            "Use mcp for database listing/counting/aggregation questions. "
            "Use hybrid when both are needed. "
            "For hybrid, separate rag_query from db_intent. "
            "Never include RBAC filters; backend adds RBAC separately. "
            "Never invent table or filter names."
        )

    @staticmethod
    def _build_user_message(query: str, fallback: RoutingDecision) -> str:
        fallback_payload = {
            "route": fallback.route.value,
            "rag_query": fallback.rag_query,
            "db_table": fallback.db_table,
            "db_intent": {
                "table": fallback.db_intent.table,
                "operation": fallback.db_intent.operation,
                "filters": fallback.db_intent.filters,
            } if fallback.db_intent else None,
            "confidence": fallback.confidence,
        }
        return (
            "Return JSON exactly like this shape:\n"
            "{\"route\":\"hybrid\",\"rag_query\":\"...\",\"db_intent\":{\"table\":\"ogrenci_bilgi_sistemi\",\"operation\":\"count\",\"filters\":{\"bolum\":\"electronics\"}},\"confidence\":0.9}\n\n"
            f"Question: {query}\n"
            f"Deterministic fallback hints: {json.dumps(fallback_payload, ensure_ascii=False)}"
        )

    @staticmethod
    def _extract_json(raw: str) -> str:
        text = raw.strip()
        if text.startswith("{") and text.endswith("}"):
            return text

        fenced = re.search(r"```(?:json)?\\s*(\\{.*?\\})\\s*```", text, flags=re.DOTALL)
        if fenced:
            return fenced.group(1)

        start = text.find("{")
        if start == -1:
            raise ValueError("router returned no JSON object")

        depth = 0
        for idx in range(start, len(text)):
            char = text[idx]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[start: idx + 1]

        raise ValueError("router returned incomplete JSON object")

    @staticmethod
    def _to_routing_decision(
        structured: StructuredRoute,
        fallback: RoutingDecision,
    ) -> RoutingDecision:
        route = RouteType(structured.route)
        db_intent = None
        db_table = None
        if structured.db_intent is not None:
            db_table = structured.db_intent.table
            db_intent = DBIntent(
                table=structured.db_intent.table,
                operation=structured.db_intent.operation,
                filters=structured.db_intent.filters,
            )

        if route in (RouteType.MCP, RouteType.HYBRID) and db_intent is None:
            db_table = fallback.db_table
            db_intent = fallback.db_intent

        rag_query = structured.rag_query
        if route in (RouteType.RAG, RouteType.HYBRID) and not rag_query:
            rag_query = fallback.rag_query

        return RoutingDecision(
            route=route,
            rag_query=rag_query,
            db_table=db_table,
            confidence=structured.confidence,
            db_intent=db_intent,
            source="llm",
        )
