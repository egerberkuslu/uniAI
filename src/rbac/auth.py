"""Token-based authentication."""

from __future__ import annotations

from src.db.manager import DatabaseManager
from src.models.user import User


class Authenticator:
    """Authenticates users by their API token."""

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    def authenticate(self, token: str) -> User:
        """
        Validate a token and return the corresponding User.
        Raises AuthenticationError on invalid token.
        """
        return self._db.get_user_by_token(token)
