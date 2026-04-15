"""Custom exception hierarchy."""


class RBACError(Exception):
    """Base exception for RBAC-related errors."""


class AuthenticationError(RBACError):
    """Raised when token is invalid."""


class PermissionDeniedError(RBACError):
    """Raised when user lacks access to a resource."""


class RoutingError(RBACError):
    """Raised when query cannot be classified."""
