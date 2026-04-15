"""Keyword-based query router — classifies into RAG / MCP / HYBRID."""

from __future__ import annotations

import re

from src.models.enums import RouteType
from src.models.results import DBIntent, RoutingDecision
from src.rag.pipeline import RAGPipeline
from src.text.normalization import normalize_for_matching


class QueryRouter:
    """
    Classifies queries into RAG, MCP, or HYBRID using keyword matching.
    """

    MCP_ACTION_KEYWORDS = [
        "how many",
        "show me",
        "list",
        "count",
        "total",
        "records",
        "amount",
        "status",
        "recent",
        "last month",
        "last quarter",
        "revenue",
        "gpa",
        "advisor",
        "transcript",
        "sinif",
        "danisman",
        "goster",
        "kac",
        "liste",
        "not ortalamasi",
        "ortalama",
        "toplam",
    ]

    RAG_KEYWORDS = [
        "policy",
        "how to",
        "what is",
        "guide",
        "procedure",
        "standard",
        "warranty",
        "onboarding",
        "privacy",
        "security",
        "shipping",
        "delivery",
        "rule",
        "akademik durum",
        "burs",
        "davranis",
        "ders kayit",
        "gereksinim",
        "kural",
        "mali yardim",
        "mezuniyet",
        "notlandirma",
        "politika",
        "prosedur",
        "sinav",
        "yonerge",
        "yonetmelik",
        "yurt",
    ]

    MCP_KEYWORDS = [
        "how many",
        "show me",
        "list",
        "count",
        "total",
        "records",
        "orders",
        "refunds",
        "amount",
        "status",
        "recent",
        "last month",
        "last quarter",
        "revenue",
        "ogrenci",
        "student",
        "gpa",
        "advisor",
        "transcript",
        "sinif",
        "danisman",
        "goster",
        "kac",
        "liste",
        "not ortalamasi",
        "ortalama",
        "siparis",
        "toplam",
    ]

    TABLE_KEYWORDS: dict[str, str] = {
        "refund": "refunds",
        "return": "refunds",
        "iade": "refunds",
        "ogrenci": "ogrenci_bilgi_sistemi",
        "student": "ogrenci_bilgi_sistemi",
        "gpa": "ogrenci_bilgi_sistemi",
        "transcript": "ogrenci_bilgi_sistemi",
        "advisor": "ogrenci_bilgi_sistemi",
        "danisman": "ogrenci_bilgi_sistemi",
        "not ortalamasi": "ogrenci_bilgi_sistemi",
        "sinif": "ogrenci_bilgi_sistemi",
        "siparis": "orders",
        "order": "orders",
    }
    DEFAULT_TABLE = "orders"

    def __init__(self, rag: RAGPipeline, threshold: float = 0.3) -> None:
        self._rag = rag
        self._threshold = threshold
        self._rag_keywords = [normalize_for_matching(keyword) for keyword in self.RAG_KEYWORDS]
        self._mcp_keywords = [normalize_for_matching(keyword) for keyword in self.MCP_KEYWORDS]
        self._mcp_action_keywords = [
            normalize_for_matching(keyword) for keyword in self.MCP_ACTION_KEYWORDS
        ]
        self._table_keywords = {
            normalize_for_matching(keyword): table
            for keyword, table in self.TABLE_KEYWORDS.items()
        }

    def _score(self, query: str, keywords: list[str]) -> int:
        q = normalize_for_matching(query)
        return sum(1 for kw in keywords if kw in q)

    def _detect_table(self, query: str) -> str:
        q = normalize_for_matching(query)
        for keyword, table in self._table_keywords.items():
            if keyword in q:
                return table
        # Also check for explicit 'order' keyword
        if "order" in q and "refund" not in q:
            return "orders"
        return self.DEFAULT_TABLE

    def _detect_operation(self, query: str) -> str:
        q = normalize_for_matching(query)
        if any(token in q for token in ("kac", "count", "how many", "sayisi")):
            return "count"
        if any(token in q for token in ("toplam", "total", "sum")):
            return "sum"
        if any(token in q for token in ("ortalama", "average", "avg")):
            return "average"
        if any(token in q for token in ("en yuksek", "highest", "max")):
            return "max"
        if any(token in q for token in ("en dusuk", "lowest", "min")):
            return "min"
        return "list"

    def _detect_filters(self, query: str, table: str) -> dict:
        q = normalize_for_matching(query)
        filters: dict[str, object] = {}

        if table == "ogrenci_bilgi_sistemi":
            for department in ("electronics", "clothing", "books"):
                if department in q:
                    filters["bolum"] = department
            class_match = re.search(r"(\d+)\s*\.?(?:\s*)sinif", q)
            if class_match:
                filters["sinif"] = int(class_match.group(1))
            gpa_match = re.search(
                r"gpa(?:\s*'?si)?\s*(?:>|ustu|uzeri|greater than)?\s*(\d+(?:\.\d+)?)\s*(?:ustu|uzeri)?",
                q,
            )
            if gpa_match:
                filters["gpa_gt"] = float(gpa_match.group(1))

        if table in {"orders", "refunds"}:
            for department in ("electronics", "clothing", "books"):
                if department in q:
                    filters["department"] = department
            for status in ("shipped", "delivered", "processing", "returned"):
                if status in q:
                    filters["status"] = status

        return filters

    def _build_db_intent(self, query: str, table: str) -> DBIntent:
        return DBIntent(
            table=table,
            operation=self._detect_operation(query),
            filters=self._detect_filters(query, table),
        )

    def _extract_rag_query(self, query: str) -> str:
        parts = [
            part.strip(" ,?.!")
            for part in re.split(r"\b(?:ve|and)\b", query, flags=re.IGNORECASE)
        ]
        candidates = [
            part
            for part in parts
            if part
            and self._score(part, self._rag_keywords) > 0
            and self._score(part, self._mcp_action_keywords) == 0
        ]
        if candidates:
            return max(candidates, key=len)
        return query

    def route(self, query: str) -> RoutingDecision:
        """
        Classify query:
        1. Score against RAG_KEYWORDS and MCP_KEYWORDS
        2. Both > 0 → HYBRID
        3. Only MCP > 0 → MCP
        4. Only RAG > 0 → RAG
        5. Fallback: try RAG search, if best score > threshold → RAG, else → default to RAG (safest)
        """
        rag_score = self._score(query, self._rag_keywords)
        mcp_score = self._score(query, self._mcp_keywords)
        mcp_action_score = self._score(query, self._mcp_action_keywords)

        if rag_score > 0 and mcp_action_score > 0:
            table = self._detect_table(query)
            return RoutingDecision(
                route=RouteType.HYBRID,
                rag_query=self._extract_rag_query(query),
                db_table=table,
                confidence=0.9,
                db_intent=self._build_db_intent(query, table),
            )

        if mcp_action_score > 0 or (mcp_score > 0 and rag_score == 0):
            table = self._detect_table(query)
            return RoutingDecision(
                route=RouteType.MCP,
                rag_query=None,
                db_table=table,
                confidence=0.8,
                db_intent=self._build_db_intent(query, table),
            )

        if rag_score > 0:
            return RoutingDecision(
                route=RouteType.RAG,
                rag_query=query,
                db_table=None,
                confidence=0.8,
            )

        # Fallback: try RAG similarity
        try:
            results = self._rag.search(query, top_k=1)
            if results and results[0].similarity >= self._threshold:
                return RoutingDecision(
                    route=RouteType.RAG,
                    rag_query=query,
                    db_table=None,
                    confidence=results[0].similarity,
                )
        except Exception:
            pass

        return RoutingDecision(
            route=RouteType.RAG,
            rag_query=query,
            db_table=None,
            confidence=0.4,
        )
