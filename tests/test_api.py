import base64

import cv2
import numpy as np
from fastapi.testclient import TestClient

from app.charges import charge_count
from app.detect import RawRegion
from app.main import create_app


class FakeEngine:
    def __init__(self, regions):
        self.regions = regions
        self.detect_calls = 0

    def detect(self, _image):
        self.detect_calls += 1
        return list(self.regions)

    def recognize(self, _crop):
        return "M10 × 1.75", 0.99


def png_b64(width=120, height=80) -> str:
    image = np.zeros((height, width, 3), dtype=np.uint8)
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    return base64.b64encode(encoded.tobytes()).decode()


def build(tmp_path, regions):
    engine = FakeEngine(regions)
    app = create_app(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        api_key="test-key",
        ocr_engine=engine,
        reference_loader=lambda _uri: ["M10 × 1.75", "REV A"],
        image_dir=tmp_path / "images",
    )
    client = TestClient(app)
    client.headers["X-API-Key"] = "test-key"
    return client, app, engine


def register(client) -> str:
    response = client.post(
        "/v1/match-config",
        json={"source_type": "s3_json", "source_location": "s3://drawings/refs.json"},
    )
    assert response.status_code == 200
    return response.json()["source_id"]


def test_unknown_source_does_not_detect_or_charge(tmp_path):
    client, app, engine = build(
        tmp_path,
        [RawRegion([[0, 0], [20, 0], [20, 8], [0, 8]], "M1O x 1.75", 0.95)],
    )
    response = client.post(
        "/v1/detect",
        json={"image": png_b64(), "source_id": "missing"},
    )
    assert response.status_code == 404
    assert engine.detect_calls == 0
    session = app.state.anchor.session_factory()
    try:
        assert charge_count(session) == 0
    finally:
        session.close()


def test_high_confidence_region_is_released_and_charged_once(tmp_path):
    client, app, _engine = build(
        tmp_path,
        [RawRegion([[10, 10], [50, 10], [50, 18], [10, 18]], "M1O x 1.75", 0.95)],
    )
    source_id = register(client)
    response = client.post("/v1/detect", json={"image": png_b64(), "source_id": source_id})
    assert response.status_code == 200
    body = response.json()
    assert body["work_level"] == "standard"
    assert body["usage_charge"]["work_level"] == "standard"
    assert body["held"] == []
    annotation = body["released"][0]
    assert annotation["text_raw"] == "M1O x 1.75"
    assert annotation["text_normalized"] == "M10 × 1.75"
    assert annotation["text_class"] == "thread_callout"
    assert annotation["matched_ref"] == "M10 × 1.75"
    assert annotation["release_state"] == "released"
    assert len(annotation["polygon"]) == 4
    session = app.state.anchor.session_factory()
    try:
        assert charge_count(session) == 1
    finally:
        session.close()


def test_low_confidence_region_is_held_and_release_does_not_rebill(tmp_path):
    client, app, _engine = build(
        tmp_path,
        [RawRegion([[10, 10], [50, 10], [50, 18], [10, 18]], "M1O x 1.75", 0.2)],
    )
    source_id = register(client)
    detected = client.post("/v1/detect", json={"image": png_b64(), "source_id": source_id})
    assert detected.status_code == 200
    body = detected.json()
    assert body["released"] == []
    task = body["held"][0]
    assert task["status"] == "open"
    annotation_id = task["annotations"][0]["id"]

    corrected = client.post(
        f"/v1/reviews/{task['review_id']}/corrections",
        json={
            "corrections": [
                {
                    "annotation_id": annotation_id,
                    "text_normalized": "M12 × 1.5",
                    "text_class": "thread_callout",
                }
            ]
        },
    )
    assert corrected.status_code == 200
    updated = corrected.json()
    assert updated["status"] == "released"
    assert updated["annotations"][0]["text_normalized"] == "M12 × 1.5"
    assert updated["annotations"][0]["text_raw"] == "M1O x 1.75"
    assert updated["annotations"][0]["release_state"] == "released"
    session = app.state.anchor.session_factory()
    try:
        assert charge_count(session) == 1
    finally:
        session.close()


def test_review_page_accepts_a_held_region_without_a_second_charge(tmp_path):
    client, app, _engine = build(
        tmp_path,
        [RawRegion([[10, 10], [50, 10], [50, 18], [10, 18]], "see note", 0.99)],
    )
    source_id = register(client)
    detected = client.post("/v1/detect", json={"image": png_b64(), "source_id": source_id})
    review_id = detected.json()["held"][0]["review_id"]
    annotation_id = detected.json()["held"][0]["annotations"][0]["id"]

    page = TestClient(app)
    login = page.post(f"/reviews/{review_id}/session", data={"api_key": "test-key"})
    assert login.status_code == 200
    assert "see note" in login.text
    saved = page.post(
        f"/reviews/{review_id}/corrections",
        data={
            "annotation_id": annotation_id,
            "accept": "true",
        },
        follow_redirects=True,
    )
    assert saved.status_code == 200
    assert "released" in saved.text.lower() or "These regions are released" in saved.text
    session = app.state.anchor.session_factory()
    try:
        assert charge_count(session) == 1
    finally:
        session.close()


def test_large_sheet_is_priced_as_oriented(tmp_path):
    client, _app, engine = build(
        tmp_path,
        [RawRegion([[0, 0], [20, 0], [20, 8], [0, 8]], "25.0", 0.95)],
    )
    source_id = register(client)
    response = client.post(
        "/v1/detect",
        json={"image": png_b64(width=1700, height=1700), "source_id": source_id},
    )
    assert response.status_code == 200
    assert response.json()["work_level"] == "oriented"
    assert response.json()["usage_charge"]["work_level"] == "oriented"
    assert engine.detect_calls > 1
