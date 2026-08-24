"""ACL checks used by retrieval backends."""

from __future__ import annotations

from app.retrieval.models import ACLContext


def can_read_document(permissions: dict, acl: ACLContext) -> bool:
    """Return whether the caller can read a document under its propagated ACL."""
    allowed_users = {str(item) for item in permissions.get("allowed_users", [])}
    allowed_groups = {str(item) for item in permissions.get("allowed_groups", [])}
    if not allowed_users and not allowed_groups:
        return True
    if acl.user_id is not None and acl.user_id in allowed_users:
        return True
    return bool(allowed_groups.intersection(acl.group_ids))
