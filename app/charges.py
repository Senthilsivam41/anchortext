"""One usage charge per image, written when detection finishes."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import UsageChargeRow, utcnow
from app.schemas import UsageCharge


class ChargeAlreadyRecorded(Exception):
    pass


def record_charge(session: Session, detection_id: str, caller_id: str, work_level: str) -> UsageChargeRow:
    existing = session.scalar(
        select(UsageChargeRow).where(UsageChargeRow.detection_id == detection_id)
    )
    if existing is not None:
        raise ChargeAlreadyRecorded(detection_id)
    row = UsageChargeRow(
        id=str(uuid.uuid4()),
        detection_id=detection_id,
        caller_id=caller_id,
        work_level=work_level,
        created_at=utcnow(),
    )
    session.add(row)
    return row


def charge_count(session: Session, detection_id: str | None = None) -> int:
    stmt = select(func.count()).select_from(UsageChargeRow)
    if detection_id is not None:
        stmt = stmt.where(UsageChargeRow.detection_id == detection_id)
    return int(session.scalar(stmt) or 0)


def to_usage_charge(row: UsageChargeRow) -> UsageCharge:
    return UsageCharge(
        work_level=row.work_level,  # type: ignore[arg-type]
        caller_id=row.caller_id,
        recorded_at=row.created_at,
    )
