"""Tests for authentication module."""

import pytest
from unittest.mock import MagicMock, patch

from src.models.enums import AccessScope, Role
from src.models.exceptions import AuthenticationError
from src.models.user import Permission, User
from src.rbac.auth import Authenticator


def _make_admin_user() -> User:
    return User(
        id=1,
        name="Alice Chen",
        email="alice@co.com",
        role=Role.ADMIN,
        department="all",
        permissions=(
            Permission(resource="orders", action="read", scope=AccessScope.ALL),
            Permission(resource="refunds", action="read", scope=AccessScope.ALL),
        ),
    )


class TestAuthenticator:
    def test_authenticate_valid_token(self):
        mock_db = MagicMock()
        user = _make_admin_user()
        mock_db.get_user_by_token.return_value = user

        auth = Authenticator(mock_db)
        result = auth.authenticate("admin_token")

        assert result == user
        mock_db.get_user_by_token.assert_called_once_with("admin_token")

    def test_authenticate_invalid_token(self):
        mock_db = MagicMock()
        mock_db.get_user_by_token.side_effect = AuthenticationError("Invalid token")

        auth = Authenticator(mock_db)
        with pytest.raises(AuthenticationError):
            auth.authenticate("bad_token")
