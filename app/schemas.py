"""HTTP contracts from the billable-cut PRD."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

TextClass = Literal[
    "dimension",
    "tolerance",
    "thread_callout",
    "surface_finish",
    "part_tag",
    "revision",
    "sheet_metadata",
    "note",
]
WorkLevel = Literal["standard", "oriented"]
ReleaseState = Literal["released", "held"]
ReviewStatus = Literal["open", "released"]
SourceType = Literal["s3_json"]


class DetectionRequest(BaseModel):
    image: str = Field(description="Base64-encoded 2D image")
    source_id: str


class Annotation(BaseModel):
    id: str
    text_raw: str
    text_normalized: str
    text_class: TextClass
    polygon: list[list[float]]
    rotation_degrees: float
    confidence: float
    domain_validation_score: float
    matched_ref: Any | None = None
    match_score: float | None = None
    release_state: ReleaseState


class ReviewTask(BaseModel):
    review_id: str
    annotations: list[Annotation]
    status: ReviewStatus


class UsageCharge(BaseModel):
    work_level: WorkLevel
    caller_id: str
    recorded_at: datetime


class DetectionResponse(BaseModel):
    work_level: WorkLevel
    usage_charge: UsageCharge
    released: list[Annotation]
    held: list[ReviewTask]


class MatchConfigCreate(BaseModel):
    source_type: SourceType
    source_location: str


class MatchConfig(BaseModel):
    source_id: str
    source_type: SourceType
    source_location: str


class CorrectionItem(BaseModel):
    annotation_id: str
    accept: bool = False
    text_normalized: str | None = None
    text_class: TextClass | None = None


class CorrectionRequest(BaseModel):
    corrections: list[CorrectionItem]
