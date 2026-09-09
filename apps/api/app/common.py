import json
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, inspect
from .models import AuditEvent


def serialize(record):
    return jsonable_encoder(
        {c.key: getattr(record, c.key) for c in inspect(record).mapper.column_attrs},
        custom_encoder={__import__("decimal").Decimal: str},
    )


def owned(db, model, id, org):
    record = db.scalar(select(model).where(model.id == id, model.organization_id == org))
    if record is None:
        raise HTTPException(404, "Record not found in your organization.")
    return record


def audit(db, org, actor, action, entity, id, old=None, new=None, details=None):
    def clean(value):
        return json.loads(json.dumps(value, default=str)) if value is not None else None

    db.add(
        AuditEvent(
            organization_id=org,
            user_id=actor,
            action=action,
            entity_type=entity,
            entity_id=id,
            old_value=clean(old),
            new_value=clean(new),
            details=clean(details or {}),
        )
    )
