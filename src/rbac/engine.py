"""RBAC engine — combines authentication with permission-checked queries."""

from __future__ import annotations

from src.db.manager import DatabaseManager
from src.models.enums import AccessScope
from src.models.exceptions import PermissionDeniedError
from src.models.results import QueryResult
from src.models.user import User
from src.rbac.auth import Authenticator


class RBACEngine:
    """High-level RBAC interface: authenticate + authorise + query."""

    def __init__(self, db: DatabaseManager, authenticator: Authenticator) -> None:
        self._db = db
        self._auth = authenticator

    def authenticate(self, token: str) -> User:
        """Delegate to Authenticator."""
        return self._auth.authenticate(token)

    def query(self, user: User, table: str) -> QueryResult:
        """Run an RBAC-filtered query via DatabaseManager."""
        return self._db.query_records(user, table)

    def get_permissions_summary(self, user: User) -> dict:
        """Return a human-readable summary of the user's access."""
        perms = []
        for p in user.permissions:
            perms.append(
                {
                    "resource": p.resource,
                    "action": p.action,
                    "scope": p.scope.value,
                }
            )
        return {
            "user": user.name,
            "role": user.role.value,
            "department": user.department,
            "permissions": perms,
        }
