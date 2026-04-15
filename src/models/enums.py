"""Enumerations used across the application."""

from enum import Enum


class Role(Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    VIEWER = "viewer"


class RouteType(Enum):
    RAG = "rag"
    MCP = "mcp"
    HYBRID = "hybrid"


class AccessScope(Enum):
    ALL = "all"
    DEPARTMENT = "department"
    OWN = "own"
