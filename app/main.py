"""FastAPI routes for detect, match config, review, and the one review page."""

import asyncio
import base64
import binascii
import os
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import (
    ApiKeyRow,
    Base,
    MatchConfigRow,
    hash_api_key,
    keys_match,
    make_engine,
    make_session_factory,
)
from app.detect import PaddleOcrEngine, recognize_image
from app.match import ReferenceUnavailable, load_s3_json, parse_s3_uri
from app.pipeline import SourceNotFound, note_source_not_found, run_detection
from app.reviews import apply_corrections, class_or_none, get_task, task_from_row
from app.schemas import (
    CorrectionItem,
    CorrectionRequest,
    DetectionRequest,
    DetectionResponse,
    MatchConfig,
    MatchConfigCreate,
    ReviewTask,
)

COOKIE = "anchortext_api_key"
TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


class AppState:
    def __init__(self, session_factory, engine, reference_loader, image_dir: Path):
        self.session_factory = session_factory
        self.ocr_engine = engine
        self.reference_loader = reference_loader
        self.image_dir = image_dir


def create_app(
    *,
    database_url: str | None = None,
    api_key: str | None = None,
    ocr_engine=None,
    reference_loader=None,
    image_dir: Path | None = None,
) -> FastAPI:
    database_url = database_url or os.environ.get(
        "ANCHORTEXT_DATABASE_URL", "sqlite:///./data/anchortext.db"
    )
    api_key = api_key if api_key is not None else os.environ.get("ANCHORTEXT_API_KEY", "")
    image_dir = image_dir or Path(os.environ.get("ANCHORTEXT_IMAGE_DIR", "./data/images"))
    _ensure_sqlite_parent(database_url)
    sql_engine = make_engine(database_url)
    Base.metadata.create_all(sql_engine)
    session_factory = make_session_factory(sql_engine)
    if api_key:
        _seed_key(session_factory, api_key)

    app = FastAPI(title="Anchortext", version="0.1.0")
    app.state.anchor = AppState(
        session_factory=session_factory,
        engine=ocr_engine or _LazyPaddle(),
        reference_loader=reference_loader or load_s3_json,
        image_dir=image_dir,
    )

    def db() -> Session:
        session = session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def caller(request: Request, session: Session = Depends(db)) -> ApiKeyRow:
        token = request.headers.get("X-API-Key") or request.cookies.get(COOKIE)
        if not token:
            raise HTTPException(status_code=401, detail="API key required")
        row = session.scalar(select(ApiKeyRow).where(ApiKeyRow.key_hash == hash_api_key(token)))
        if row is None or not keys_match(token, row.key_hash):
            raise HTTPException(status_code=401, detail="API key required")
        return row

    @app.post("/v1/match-config", response_model=MatchConfig)
    def register_match_config(
        body: MatchConfigCreate,
        caller_row: ApiKeyRow = Depends(caller),
        session: Session = Depends(db),
    ) -> MatchConfig:
        try:
            parse_s3_uri(body.source_location)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        row = MatchConfigRow(
            source_id=str(uuid.uuid4()),
            source_type=body.source_type,
            source_location=body.source_location,
            caller_id=caller_row.id,
        )
        session.add(row)
        session.flush()
        return MatchConfig(
            source_id=row.source_id,
            source_type="s3_json",
            source_location=row.source_location,
        )

    @app.get("/v1/match-config/{source_id}", response_model=MatchConfig)
    def get_match_config(
        source_id: str,
        caller_row: ApiKeyRow = Depends(caller),
        session: Session = Depends(db),
    ) -> MatchConfig:
        row = session.get(MatchConfigRow, source_id)
        if row is None or row.caller_id != caller_row.id:
            raise HTTPException(status_code=404, detail="source_id is invalid")
        return MatchConfig(
            source_id=row.source_id,
            source_type="s3_json",
            source_location=row.source_location,
        )

    @app.post("/v1/detect", response_model=DetectionResponse)
    async def detect(
        request: Request,
        caller_row: ApiKeyRow = Depends(caller),
        session: Session = Depends(db),
    ) -> DetectionResponse:
        image_bytes, source_id = await _read_detect_body(request)
        state: AppState = request.app.state.anchor
        config = session.get(MatchConfigRow, source_id)
        if config is None or config.caller_id != caller_row.id:
            note_source_not_found(source_id)
            raise HTTPException(status_code=404, detail="source_id is invalid")
        try:
            recognized = await asyncio.to_thread(recognize_image, image_bytes, state.ocr_engine)
            return run_detection(
                session,
                caller_id=caller_row.id,
                source_id=source_id,
                image_bytes=image_bytes,
                reference_loader=state.reference_loader,
                image_dir=state.image_dir,
                engine_result=recognized,
            )
        except SourceNotFound as exc:
            raise HTTPException(status_code=404, detail="source_id is invalid") from exc
        except ReferenceUnavailable as exc:
            raise HTTPException(status_code=502, detail="reference source could not be read") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/v1/reviews/{review_id}", response_model=ReviewTask)
    def get_review(
        review_id: str,
        caller_row: ApiKeyRow = Depends(caller),
        session: Session = Depends(db),
    ) -> ReviewTask:
        task = get_task(session, review_id, caller_row.id)
        if task is None:
            raise HTTPException(status_code=404, detail="review task not found")
        return task_from_row(session, task)

    @app.post("/v1/reviews/{review_id}/corrections", response_model=ReviewTask)
    def correct_review(
        review_id: str,
        body: CorrectionRequest,
        caller_row: ApiKeyRow = Depends(caller),
        session: Session = Depends(db),
    ) -> ReviewTask:
        task = get_task(session, review_id, caller_row.id)
        if task is None:
            raise HTTPException(status_code=404, detail="review task not found")
        if not body.corrections:
            raise HTTPException(status_code=400, detail="no corrections")
        try:
            return apply_corrections(session, task, body.corrections)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="annotation not on this review task") from exc

    @app.get("/reviews/{review_id}", response_class=HTMLResponse)
    def review_page(
        review_id: str,
        request: Request,
        session: Session = Depends(db),
    ):
        caller_row = _caller_or_none(request, session)
        if caller_row is None:
            return TEMPLATES.TemplateResponse(
                request,
                "review.html",
                {"review_id": review_id, "needs_key": True, "task": None, "detection": None},
            )
        task = get_task(session, review_id, caller_row.id)
        if task is None:
            raise HTTPException(status_code=404, detail="review task not found")
        from app.db import DetectionRow

        detection = session.get(DetectionRow, task.detection_id)
        return TEMPLATES.TemplateResponse(
            request,
            "review.html",
            {
                "review_id": review_id,
                "needs_key": False,
                "task": task_from_row(session, task),
                "detection": detection,
            },
        )

    @app.post("/reviews/{review_id}/session")
    def review_login(review_id: str, api_key: str = Form(...)):
        response = RedirectResponse(url=f"/reviews/{review_id}", status_code=303)
        response.set_cookie(COOKIE, api_key, httponly=True, samesite="lax")
        return response

    @app.post("/reviews/{review_id}/corrections")
    def review_form_correction(
        review_id: str,
        request: Request,
        annotation_id: str = Form(...),
        accept: str = Form("false"),
        text_normalized: str = Form(""),
        text_class: str = Form(""),
        session: Session = Depends(db),
    ):
        caller_row = _caller_or_none(request, session)
        if caller_row is None:
            raise HTTPException(status_code=401, detail="API key required")
        task = get_task(session, review_id, caller_row.id)
        if task is None:
            raise HTTPException(status_code=404, detail="review task not found")
        item = CorrectionItem(
            annotation_id=annotation_id,
            accept=accept == "true" and not text_normalized.strip(),
            text_normalized=text_normalized.strip() or None,
            text_class=class_or_none(text_class.strip() or None),
        )
        try:
            apply_corrections(session, task, [item])
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="annotation not on this review task") from exc
        return RedirectResponse(url=f"/reviews/{review_id}", status_code=303)

    @app.get("/reviews/{review_id}/image")
    def review_image(
        review_id: str,
        request: Request,
        session: Session = Depends(db),
    ):
        caller_row = _caller_or_none(request, session)
        if caller_row is None:
            raise HTTPException(status_code=401, detail="API key required")
        task = get_task(session, review_id, caller_row.id)
        if task is None:
            raise HTTPException(status_code=404, detail="review task not found")
        from app.db import DetectionRow

        detection = session.get(DetectionRow, task.detection_id)
        if detection is None:
            raise HTTPException(status_code=404, detail="image not found")
        data = Path(detection.image_path).read_bytes()
        return Response(content=data, media_type="image/png")

    return app


class _LazyPaddle:
    def __init__(self) -> None:
        self._inner = None

    def _engine(self):
        if self._inner is None:
            self._inner = PaddleOcrEngine()
        return self._inner

    def detect(self, image):
        return self._engine().detect(image)

    def recognize(self, crop):
        return self._engine().recognize(crop)


def _ensure_sqlite_parent(database_url: str) -> None:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        return
    path = database_url[len(prefix) :]
    if not path or path == ":memory:":
        return
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def _seed_key(session_factory, api_key: str) -> None:
    session = session_factory()
    try:
        digest = hash_api_key(api_key)
        existing = session.scalar(select(ApiKeyRow).where(ApiKeyRow.key_hash == digest))
        if existing is None:
            session.add(ApiKeyRow(id=str(uuid.uuid4()), key_hash=digest))
            session.commit()
    finally:
        session.close()


def _caller_or_none(request: Request, session: Session) -> ApiKeyRow | None:
    token = request.headers.get("X-API-Key") or request.cookies.get(COOKIE)
    if not token:
        return None
    row = session.scalar(select(ApiKeyRow).where(ApiKeyRow.key_hash == hash_api_key(token)))
    if row is None or not keys_match(token, row.key_hash):
        return None
    return row


async def _read_detect_body(request: Request) -> tuple[bytes, str]:
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("application/json"):
        body = DetectionRequest.model_validate(await request.json())
        try:
            payload = body.image.split(",", 1)[-1]
            return base64.b64decode(payload, validate=True), body.source_id
        except (binascii.Error, ValueError) as exc:
            raise HTTPException(status_code=400, detail="image is not valid base64") from exc
    form = await request.form()
    upload = form.get("image")
    source_id = form.get("source_id")
    if upload is None or not hasattr(upload, "read") or not source_id:
        raise HTTPException(status_code=400, detail="image and source_id are required")
    return await upload.read(), str(source_id)


app = create_app()
