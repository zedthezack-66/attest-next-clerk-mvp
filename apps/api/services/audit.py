from apps.api.models.entities import AuditLog


def audit(db, action: str, entity_type: str, entity_id, *, tenant_id=None, actor_type: str = "system",
          actor_id=None, **details) -> None:
    """Record an audit event in the caller's transaction (committed or rolled back with it)."""
    db.add(AuditLog(
        tenant_id=tenant_id,
        actor_type=actor_type,
        actor_id=str(actor_id) if actor_id else None,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        details=details,
    ))
