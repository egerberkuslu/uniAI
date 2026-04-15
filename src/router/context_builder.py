"""Context builder — assembles LLM prompts from RAG + DB results."""

from __future__ import annotations

from src.models.results import QueryResult, SearchResult
from src.models.user import User
from src.text.normalization import looks_turkish


class ContextBuilder:
    """Assembles the LLM prompt from RAG results + DB results."""

    @staticmethod
    def build_system_prompt(user: User, question: str | None = None) -> str:
        response_language = "Turkish" if question and looks_turkish(question) else "the user's language"
        return (
            f"You are a company internal assistant. "
            f"Answer based ONLY on the provided context.\n"
            f"Current user: {user.name} (Role: {user.role.value}, "
            f"Department: {user.department}).\n"
            f"Respond in {response_language}. "
            f"Preserve original Turkish names and terminology when they appear in the context.\n"
            f"When you use knowledge-base content, cite it with numbered references in square brackets at the end of the sentence. "
            f"Use only the source numbers provided in the context, such as [1] or [2].\n"
            f"Be concise and helpful. "
            f"If database data is shown, mention the user's access level. "
            f"Do not make up information not present in the context."
        )

    @staticmethod
    def build_user_message(
        question: str,
        rag_results: list[SearchResult] | None = None,
        db_result: QueryResult | None = None,
        user: User | None = None,
    ) -> str:
        parts: list[str] = []
        if looks_turkish(question):
            parts.append("IMPORTANT: Yanıtını yalnızca Türkçe ver. Başka dil kullanma.\n")
        parts.append(f"Question: {question}\n")

        if rag_results:
            parts.append("=== Knowledge Base (Open) ===")
            for index, r in enumerate(rag_results, start=1):
                parts.append(
                    f"[{index}] {r.document_title} (similarity: {r.similarity:.2f})\n"
                    f"{r.text}"
                )
            parts.append("")

        if db_result:
            role_label = user.role.value if user else "unknown"
            parts.append(f"=== Database (RBAC-filtered for {role_label}) ===")
            parts.append(f"Table: {db_result.table_name}")
            parts.append(f"Filter applied: {db_result.filter_description}")
            parts.append(f"Record count: {db_result.count}")
            if db_result.total_amount is not None:
                parts.append(f"Total amount: ${db_result.total_amount:,.2f}")
            parts.append("Records:")
            for rec in db_result.records:
                parts.append(f"  - {rec}")
            summary_lines = ContextBuilder._build_db_summary(db_result)
            if summary_lines:
                parts.append("")
                parts.extend(summary_lines)
            parts.append("")

        parts.append("Answer the question using ONLY the above context.")
        return "\n".join(parts)

    @staticmethod
    def _build_db_summary(db_result: QueryResult) -> list[str]:
        """Provide deterministic summaries for tricky tables to steer the LLM."""

        if db_result.table_name != "ogrenci_bilgi_sistemi" or not db_result.records:
            return []

        per_class: dict[str, tuple[str | None, float]] = {}
        for rec in db_result.records:
            sinif = rec.get("sinif")
            try:
                gpa = float(rec.get("gpa", 0))
            except (TypeError, ValueError):
                continue
            if not sinif:
                continue
            current = per_class.get(str(sinif))
            if current is None or gpa > current[1]:
                per_class[str(sinif)] = (rec.get("full_name"), gpa)

        if not per_class:
            return []

        summary = ["Top GPA per sinif (auto-computed):"]
        for sinif, (name, gpa) in sorted(per_class.items(), key=lambda item: item[0]):
            student = name or "unknown"
            summary.append(f"  sinif {sinif}: {student} — GPA {gpa:.2f}")
        return summary
