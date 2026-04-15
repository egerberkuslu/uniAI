"""User and Permission value objects."""

from __future__ import annotations

from dataclasses import dataclass

from src.models.enums import AccessScope, Role


@dataclass(frozen=True)
class Permission:
    resource: str
    action: str
    scope: AccessScope


@dataclass(frozen=True)
class User:
    id: int
    name: str
    email: str
    role: Role
    department: str
    permissions: tuple[Permission, ...]

    def has_permission(self, resource: str, action: str = "read") -> AccessScope | None:
        """Returns the scope if user has permission, None otherwise."""
        for perm in self.permissions:
            if perm.resource == resource and perm.action == action:
                return perm.scope
        return None

    @property
    def is_admin(self) -> bool:
        return self.role == Role.ADMIN
