"""Per-user copies of analysis results and the workspace document."""
from __future__ import annotations

import json
import logging
import re

from fastapi.encoders import jsonable_encoder

from accounts.db import session_scope, utcnow
from accounts.models import Record, Workspace
from accounts.service import new_id

logger = logging.getLogger("careernavigator.auth")
MAX_JSON_CHARS = 1_500_000
KINDS = {"resume", "job", "github", "career", "report"}
RECORD_ID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def store_record(user_id: str, kind: str, payload: dict) -> None:
    if kind not in KINDS or not isinstance(payload, dict):
        return
    try:
        raw = json.dumps(jsonable_encoder(payload))
    except (TypeError, ValueError):
        logger.info("record_skipped kind=%s reason=encoding", kind)
        return
    if len(raw) > MAX_JSON_CHARS:
        logger.info("record_skipped kind=%s reason=size", kind)
        return
    with session_scope() as db:
        db.add(Record(id=new_id(), user_id=user_id, kind=kind, body=raw, created_at=utcnow()))


def list_records(user_id: str) -> dict:
    with session_scope() as db:
        rows = (
            db.query(Record)
            .filter(Record.user_id == user_id)
            .order_by(Record.created_at.desc())
            .limit(50)
            .all()
        )
        return {
            "records": [
                {"id": row.id, "kind": row.kind, "created_at": row.created_at.isoformat()}
                for row in rows
            ]
        }


def read_record(user_id: str, record_id: str) -> dict | None:
    if not RECORD_ID.fullmatch(record_id):
        return None
    with session_scope() as db:
        row = db.get(Record, record_id)
        if row is None or row.user_id != user_id:
            return None
        return {
            "id": row.id,
            "kind": row.kind,
            "created_at": row.created_at.isoformat(),
            "body": json.loads(row.body),
        }


def delete_record(user_id: str, record_id: str) -> bool:
    if not RECORD_ID.fullmatch(record_id):
        return False
    with session_scope() as db:
        row = db.get(Record, record_id)
        if row is None or row.user_id != user_id:
            return False
        db.delete(row)
        return True


def delete_all_records(user_id: str) -> None:
    with session_scope() as db:
        db.query(Record).filter(Record.user_id == user_id).delete(synchronize_session=False)


def load_workspace(user_id: str):
    with session_scope() as db:
        row = db.get(Workspace, user_id)
        if row is None:
            return None
        try:
            parsed = json.loads(row.payload)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None


def save_workspace(user_id: str, payload: dict) -> str | None:
    try:
        raw = json.dumps(payload)
    except (TypeError, ValueError):
        return "The workspace could not be saved."
    if len(raw) > MAX_JSON_CHARS:
        return "That workspace is too large to save."
    with session_scope() as db:
        row = db.get(Workspace, user_id)
        if row is None:
            db.add(Workspace(user_id=user_id, payload=raw, updated_at=utcnow()))
        else:
            row.payload = raw
            row.updated_at = utcnow()
    return None
