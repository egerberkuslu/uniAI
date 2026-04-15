"""Tests for RBAC engine — role-based filtering logic."""

import pytest
from unittest.mock import MagicMock

from src.models.enums import AccessScope, Role
from src.models.exceptions import PermissionDeniedError
from src.models.results import QueryResult
from src.models.user import Permission, User
from src.rbac.engine import RBACEngine


def _make_user(role: Role, department: str = "electronics", user_id: int = 1) -> User:
    scope_map = {
        Role.ADMIN: AccessScope.ALL,
        Role.MANAGER: AccessScope.DEPARTMENT,
        Role.VIEWER: AccessScope.OWN,
    }
    scope = scope_map[role]
    return User(
        id=user_id,
        name="Test User",
        email="test@co.com",
        role=role,
        department=department,
        permissions=(
            Permission(resource="orders", action="read", scope=scope),
            Permission(resource="refunds", action="read", scope=scope),
        ),
    )


class TestRBACEngine:
    def test_admin_sees_all_orders(self):
        mock_db = MagicMock()
        user = _make_user(Role.ADMIN, user_id=1)
        mock_db.get_user_by_token.return_value = user
        mock_db.query_records.return_value = QueryResult(
            records=({"id": 1, "amount": 100},),
            count=1,
            total_amount=100.0,
            access_scope=AccessScope.ALL,
            filter_description="None (full access)",
            table_name="orders",
        )

        engine = RBACEngine(mock_db, MagicMock())
        # Bypass auth, test query directly
        result = engine.query(user, "orders")
        assert result.count == 1
        assert result.access_scope == AccessScope.ALL

    def test_manager_sees_department(self):
        mock_db = MagicMock()
        user = _make_user(Role.MANAGER, department="electronics", user_id=2)
        mock_db.query_records.return_value = QueryResult(
            records=({"id": 1},),
            count=1,
            total_amount=299.99,
            access_scope=AccessScope.DEPARTMENT,
            filter_description="department = 'electronics'",
            table_name="orders",
        )

        engine = RBACEngine(mock_db, MagicMock())
        result = engine.query(user, "orders")
        assert result.access_scope == AccessScope.DEPARTMENT

    def test_viewer_sees_own_records(self):
        mock_db = MagicMock()
        user = _make_user(Role.VIEWER, user_id=3)
        mock_db.query_records.return_value = QueryResult(
            records=({"id": 1},),
            count=1,
            total_amount=299.99,
            access_scope=AccessScope.OWN,
            filter_description="assigned_to = 3",
            table_name="orders",
        )

        engine = RBACEngine(mock_db, MagicMock())
        result = engine.query(user, "orders")
        assert result.access_scope == AccessScope.OWN

    def test_permission_denied_for_unauthorised_table(self):
        mock_db = MagicMock()
        user = User(
            id=1, name="Test", email="t@co.com",
            role=Role.VIEWER, department="electronics",
            permissions=(),  # no permissions
        )
        mock_db.query_records.side_effect = PermissionDeniedError("No access")

        engine = RBACEngine(mock_db, MagicMock())
        with pytest.raises(PermissionDeniedError):
            engine.query(user, "orders")

    def test_permissions_summary(self):
        mock_db = MagicMock()
        user = _make_user(Role.ADMIN, user_id=1)
        engine = RBACEngine(mock_db, MagicMock())

        summary = engine.get_permissions_summary(user)
        assert summary["role"] == "admin"
        assert summary["user"] == "Test User"
        assert len(summary["permissions"]) == 2
