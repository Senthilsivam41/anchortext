"""Held regions stay on a review task until the caller accepts or edits them."""

import json
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import AnnotationRow, ReviewTaskRow
from app.normalize import normalize
from app.schemas import Annotation, CorrectionItem, ReviewTask, TextClass


def annotation_from_row(row: AnnotationRow) -> Annotation:
    matched = json.loads(row.matched_ref_json) if row.matched_ref_json else None
    return Annotation(
        id=row.id,
        text_raw=row.text_raw,
        text_normalized=row.text_normalized,
        text_class=row.text_class,  # type: ignore[arg-type]
        polygon=json.loads(row.polygon_json),
        rotation_degrees=row.rotation_degrees,
        confidence=row.confidence,
        domain_validation_score=row.domain_validation_score,
        matched_ref=matched,
        match_score=row.match_score,
        release_state=row.release_state,  # type: ignore[arg-type]
    )


def task_from_row(session: Session, task: ReviewTaskRow) -> ReviewTask:
    rows = session.scalars(
        select(AnnotationRow).where(AnnotationRow.review_task_id == task.id)
    ).all()
    return ReviewTask(
        review_id=task.id,
        annotations=[annotation_from_row(row) for row in rows],
        status=task.status,  # type: ignore[arg-type]
    )


def new_review_task(session: Session, detection_id: str, caller_id: str) -> ReviewTaskRow:
    task = ReviewTaskRow(
        id=str(uuid.uuid4()),
        detection_id=detection_id,
        caller_id=caller_id,
        status="open",
    )
    session.add(task)
    return task


def get_task(session: Session, review_id: str, caller_id: str) -> ReviewTaskRow | None:
    task = session.get(ReviewTaskRow, review_id)
    if task is None or task.caller_id != caller_id:
        return None
    return task


def apply_corrections(
    session: Session,
    task: ReviewTaskRow,
    corrections: list[CorrectionItem],
) -> ReviewTask:
    if task.status == "released":
        return task_from_row(session, task)
    by_id = {item.annotation_id: item for item in corrections}
    rows = session.scalars(
        select(AnnotationRow).where(AnnotationRow.review_task_id == task.id)
    ).all()
    known = {row.id for row in rows}
    unknown = set(by_id) - known
    if unknown:
        raise KeyError(next(iter(unknown)))
    for row in rows:
        item = by_id.get(row.id)
        if item is None or row.release_state == "released":
            continue
        if item.accept and item.text_normalized is None and item.text_class is None:
            row.release_state = "released"
            continue
        if item.text_normalized is not None:
            row.text_normalized = item.text_normalized
            if item.text_class is None:
                row.text_class = normalize(item.text_normalized).text_class
                row.domain_validation_score = normalize(item.text_normalized).domain_validation_score
            else:
                row.text_class = item.text_class
        elif item.text_class is not None:
            row.text_class = item.text_class
        row.release_state = "released"
    session.flush()
    remaining = session.scalars(
        select(AnnotationRow).where(
            AnnotationRow.review_task_id == task.id,
            AnnotationRow.release_state == "held",
        )
    ).all()
    if not remaining:
        task.status = "released"
    return task_from_row(session, task)


def held_annotations(session: Session, task_id: str) -> list[AnnotationRow]:
    return list(
        session.scalars(
            select(AnnotationRow).where(
                AnnotationRow.review_task_id == task_id,
                AnnotationRow.release_state == "held",
            )
        ).all()
    )


def class_or_none(value: str | None) -> TextClass | None:
    if value in {
        "dimension",
        "tolerance",
        "thread_callout",
        "surface_finish",
        "part_tag",
        "revision",
        "sheet_metadata",
        "note",
    }:
        return value  # type: ignore[return-value]
    return None
