from app.db import models as m


def log_audit(session, application_id: str, actor: str, action: str, detail: str) -> m.AuditEvent:
    event = m.AuditEvent(application_id=application_id, actor=actor, action=action, detail=detail)
    session.add(event)
    session.flush()
    return event
