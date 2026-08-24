"""Role-based access-control policy helpers."""

from __future__ import annotations

from enum import StrEnum

from app.models.enums import Role


class Permission(StrEnum):
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"
    SETTINGS = "settings"


ROLE_PERMISSIONS = {
    Role.OWNER: {Permission.READ, Permission.WRITE, Permission.ADMIN, Permission.SETTINGS},
    Role.ADMIN: {Permission.READ, Permission.WRITE, Permission.ADMIN, Permission.SETTINGS},
    Role.EDITOR: {Permission.READ, Permission.WRITE},
    Role.MEMBER: {Permission.READ},
    Role.VIEWER: {Permission.READ},
}


def can(role: Role | str, permission: Permission | str) -> bool:
    return Permission(permission) in ROLE_PERMISSIONS[Role(role)]
