"""Detect, normalize, match, then persist one charge."""

import json
import logging
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.charges import record_charge, to_usage_charge
from app.db import AnnotationRow, DetectionRow, MatchConfigRow, utcnow
from app.detect import RawRegion
from app.match import ReferenceUnavailable, match_text
from app.normalize import clears_release_bar, normalize
from app.reviews import annotation_from_row, new_review_task, task_from_row
from app.schemas import DetectionResponse

logger = logging.getLogger("anchortext")
source_not_found_count = 0


class SourceNotFound(Exception):
    pass


def note_source_not_found(source_id: str) -> None:
    global source_not_found_count
    source_not_found_count += 1
    logger.warning("source_id invalid: %s", source_id)


def run_detection(
    session: Session,
    *,
    caller_id: str,
    source_id: str,
    image_bytes: bytes,
    reference_loader,
    image_dir: Path,
    engine_result: tuple,
) -> DetectionResponse:
    config = session.get(MatchConfigRow, source_id)
    if config is None or config.caller_id != caller_id:
        note_source_not_found(source_id)
        raise SourceNotFound(source_id)

    try:
        reference = reference_loader(config.source_location)
    except ReferenceUnavailable:
        raise
    image, work_level, regions = engine_result

    detection_id = str(uuid.uuid4())
    image_dir.mkdir(parents=True, exist_ok=True)
    image_path = image_dir / f"{detection_id}.png"
    image_path.write_bytes(_png(image_bytes, image))

    height, width = image.shape[:2]
    detection = DetectionRow(
        id=detection_id,
        caller_id=caller_id,
        source_id=source_id,
        work_level=work_level,
        image_path=str(image_path),
        image_width=width,
        image_height=height,
        created_at=utcnow(),
    )
    session.add(detection)

    built: list[tuple[AnnotationRow, bool]] = []
    for region in regions:
        built.append(_annotation(session, detection_id, region, reference))

    held_rows = [row for row, released in built if not released]
    task = None
    if held_rows:
        task = new_review_task(session, detection_id, caller_id)
        session.flush()
        for row in held_rows:
            row.review_task_id = task.id

    charge = record_charge(session, detection_id, caller_id, work_level)
    session.flush()

    released = [annotation_from_row(row) for row, is_released in built if is_released]
    held = [task_from_row(session, task)] if task is not None else []
    return DetectionResponse(
        work_level=work_level,  # type: ignore[arg-type]
        usage_charge=to_usage_charge(charge),
        released=released,
        held=held,
    )


def _annotation(
    session: Session,
    detection_id: str,
    region: RawRegion,
    reference,
) -> tuple[AnnotationRow, bool]:
    normalized = normalize(region.text)
    matched_ref, match_score = match_text(normalized.text_normalized, reference)
    released = clears_release_bar(region.confidence, normalized.domain_validation_score)
    row = AnnotationRow(
        id=str(uuid.uuid4()),
        detection_id=detection_id,
        review_task_id=None,
        text_raw=region.text,
        text_normalized=normalized.text_normalized,
        text_class=normalized.text_class,
        polygon_json=json.dumps(region.polygon),
        rotation_degrees=region.rotation_degrees,
        confidence=region.confidence,
        domain_validation_score=normalized.domain_validation_score,
        matched_ref_json=json.dumps(matched_ref) if matched_ref is not None else None,
        match_score=match_score,
        release_state="released" if released else "held",
    )
    session.add(row)
    return row, released


def _png(original: bytes, image) -> bytes:
    import cv2

    ok, encoded = cv2.imencode(".png", image)
    if ok:
        return encoded.tobytes()
    return original
