"""Database manager — all PostgreSQL operations in one place."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor

from src.config import AppConfig
from src.models.enums import AccessScope, Role
from src.models.exceptions import AuthenticationError, PermissionDeniedError
from src.models.results import QueryResult
from src.models.user import Permission, User


class DatabaseManager:
    """Encapsulates ALL database operations using psycopg2."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._conn = psycopg2.connect(
            host=config.db_host,
            port=config.db_port,
            dbname=config.db_name,
            user=config.db_user,
            password=config.db_password,
        )
        self._conn.autocommit = True

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def setup(self) -> None:
        """Run schema.sql and seed.sql to initialise the database."""
        base = Path(__file__).parent
        for sql_file in ("schema.sql", "seed.sql"):
            path = base / sql_file
            with open(path) as f:
                sql = f.read()
            with self._conn.cursor() as cur:
                cur.execute(sql)
        print(f"Database initialised from schema.sql + seed.sql")

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def get_user_by_token(self, token: str) -> User:
        """
        Look up user by token and return a frozen User value object
        including all permissions.  Raises AuthenticationError if not found.
        """
        with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT u.id, u.name, u.email, u.department,
                       r.name AS role_name, r.level AS role_level
                FROM users u
                JOIN roles r ON u.role_id = r.id
                WHERE u.token = %s
                """,
                (token,),
            )
            row = cur.fetchone()
            if row is None:
                raise AuthenticationError(f"Invalid token: {token!r}")

            cur.execute(
                """
                SELECT resource, action, scope
                FROM role_permissions
                WHERE role_id = (
                    SELECT role_id FROM users WHERE id = %s
                )
                """,
                (row["id"],),
            )
            perm_rows = cur.fetchall()

        role = Role(row["role_name"])
        permissions = tuple(
            Permission(
                resource=p["resource"],
                action=p["action"],
                scope=AccessScope(p["scope"]),
            )
            for p in perm_rows
        )

        return User(
            id=row["id"],
            name=row["name"],
            email=row["email"],
            role=role,
            department=row["department"],
            permissions=permissions,
        )

    # ------------------------------------------------------------------
    # RBAC-filtered queries
    # ------------------------------------------------------------------

    def query_records(self, user: User, table: str) -> QueryResult:
        """
        Query a protected table with automatic RBAC WHERE clause.

        admin   → no filter
        manager → WHERE department/bolum = user.department
        viewer  → WHERE assigned_to / processed_by / advisor_id = user.id
        """
        allowed_tables = {"orders", "refunds", "ogrenci_bilgi_sistemi"}
        if table not in allowed_tables:
            raise PermissionDeniedError(f"Unknown resource: {table!r}")

        scope = user.has_permission(table, "read")
        if scope is None:
            raise PermissionDeniedError(
                f"User {user.name} ({user.role.value}) has no read access to {table}"
            )

        where_clause, params, filter_description = self._build_filters(user, table, scope)
        query = f"SELECT * FROM {table} {where_clause} ORDER BY id"

        with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            rows = cur.fetchall()

        records = tuple(dict(r) for r in rows)
        total_amount: float | None = None
        if records and "amount" in records[0]:
            total_amount = sum(float(r.get("amount", 0)) for r in records)

        return QueryResult(
            records=records,
            count=len(records),
            total_amount=total_amount,
            access_scope=scope,
            filter_description=filter_description,
            table_name=table,
        )

    def _build_filters(
        self, user: User, table: str, scope: AccessScope
    ) -> tuple[str, list[Any], str]:
        if scope == AccessScope.ALL:
            return "", [], "None (full access)"

        if scope == AccessScope.DEPARTMENT:
            column_map = {
                "orders": "department",
                "refunds": "department",
                "ogrenci_bilgi_sistemi": "bolum",
            }
            column = column_map.get(table)
            if column is None:
                raise PermissionDeniedError(f"Department filter unsupported for {table}")
            return (
                f"WHERE {column} = %s",
                [user.department],
                f"{column} = {user.department!r}",
            )

        if scope == AccessScope.OWN:
            column_map = {
                "orders": "assigned_to",
                "refunds": "processed_by",
                "ogrenci_bilgi_sistemi": "advisor_id",
            }
            column = column_map.get(table)
            if column is None:
                raise PermissionDeniedError(f"Own-records filter unsupported for {table}")
            return (
                f"WHERE {column} = %s",
                [user.id],
                f"{column} = {user.id} (own records)",
            )

        raise PermissionDeniedError(f"Unknown access scope: {scope}")

    # ------------------------------------------------------------------
    # Knowledge base
    # ------------------------------------------------------------------

    def get_all_documents(self) -> list[dict]:
        with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, title, content FROM kb_documents")
            return [dict(r) for r in cur.fetchall()]

    def store_chunk(
        self, doc_id: int, text: str, index: int, embedding: list[float]
    ) -> None:
        emb_str = "[" + ",".join(str(v) for v in embedding) + "]"
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO kb_chunks (document_id, chunk_text, chunk_index, embedding)
                VALUES (%s, %s, %s, %s::vector)
                """,
                (doc_id, text, index, emb_str),
            )

    def create_document(self, title: str, content: str, category: str | None = None, user_id: int | None = None) -> int:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO kb_documents (title, content, category, user_id)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (title, content, category, user_id),
            )
            new_id = cur.fetchone()[0]
        return int(new_id)

    def search_similar_chunks(
        self, query_embedding: list[float], top_k: int = 3, user_id: int | None = None
    ) -> list[dict]:
        emb_str = "[" + ",".join(str(v) for v in query_embedding) + "]"
        with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
            if user_id is not None:
                cur.execute(
                    """
                    SELECT c.id, c.chunk_text, d.title,
                           1 - (c.embedding <=> %s::vector) AS similarity
                    FROM kb_chunks c
                    JOIN kb_documents d ON c.document_id = d.id
                    WHERE d.user_id = %s OR d.user_id IS NULL
                    ORDER BY c.embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (emb_str, user_id, emb_str, top_k),
                )
            else:
                cur.execute(
                    """
                    SELECT c.id, c.chunk_text, d.title,
                           1 - (c.embedding <=> %s::vector) AS similarity
                    FROM kb_chunks c
                    JOIN kb_documents d ON c.document_id = d.id
                    ORDER BY c.embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (emb_str, emb_str, top_k),
                )
            return [dict(r) for r in cur.fetchall()]

    def get_searchable_chunks(self, user_id: int | None = None) -> list[dict]:
        with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
            if user_id is not None:
                cur.execute(
                    """
                    SELECT c.id, c.chunk_text, d.title
                    FROM kb_chunks c
                    JOIN kb_documents d ON c.document_id = d.id
                    WHERE d.user_id = %s OR d.user_id IS NULL
                    ORDER BY c.id
                    """,
                    (user_id,),
                )
            else:
                cur.execute(
                    """
                    SELECT c.id, c.chunk_text, d.title
                    FROM kb_chunks c
                    JOIN kb_documents d ON c.document_id = d.id
                    ORDER BY c.id
                    """
                )
            return [dict(r) for r in cur.fetchall()]

    def get_chunk_by_id(self, chunk_id: int, user_id: int | None = None) -> dict | None:
        with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
            if user_id is not None:
                cur.execute(
                    """
                    SELECT c.id, c.chunk_text, c.chunk_index, d.id AS document_id,
                           d.title, d.category, d.user_id
                    FROM kb_chunks c
                    JOIN kb_documents d ON c.document_id = d.id
                    WHERE c.id = %s AND (d.user_id = %s OR d.user_id IS NULL)
                    """,
                    (chunk_id, user_id),
                )
            else:
                cur.execute(
                    """
                    SELECT c.id, c.chunk_text, c.chunk_index, d.id AS document_id,
                           d.title, d.category, d.user_id
                    FROM kb_chunks c
                    JOIN kb_documents d ON c.document_id = d.id
                    WHERE c.id = %s AND d.user_id IS NULL
                    """,
                    (chunk_id,),
                )
            row = cur.fetchone()
            return dict(row) if row else None

    def reset_kb_chunks(self) -> None:
        with self._conn.cursor() as cur:
            cur.execute("DELETE FROM kb_chunks")

    def get_user_documents(self, user_id: int) -> list[dict]:
        """Get all documents uploaded by a specific user."""
        with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, title, category, created_at
                FROM kb_documents
                WHERE user_id = %s
                ORDER BY created_at DESC
                """,
                (user_id,)
            )
            return [dict(r) for r in cur.fetchall()]

    def delete_document(self, doc_id: int, user_id: int) -> bool:
        """Delete a document if it belongs to the user. Returns True if deleted."""
        with self._conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM kb_documents
                WHERE id = %s AND user_id = %s
                """,
                (doc_id, user_id)
            )
            return cur.rowcount > 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        if self._conn and not self._conn.closed:
            self._conn.close()
