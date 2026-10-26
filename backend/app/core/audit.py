import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.core.clock import now


def record(
    connection: Connection,
    *,
    actor: str,
    action: str,
    entity: str,
    entity_id: str | None,
    detail: dict[str, Any] | None = None,
) -> None:
    connection.execute(
        text("""INSERT INTO audit_log(actor, action, entity, entity_id, detail_json, at)
                  VALUES (:actor, :action, :entity, :entity_id, :detail, :at)"""),
        {
            "actor": actor,
            "action": action,
            "entity": entity,
            "entity_id": entity_id,
            "detail": json.dumps(detail or {}, ensure_ascii=False),
            "at": now().isoformat().replace("+00:00", "Z"),
        },
    )
