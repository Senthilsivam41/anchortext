"""PP-OCRv6 small, OpenCV tiling and rectification, and a four-angle ensemble.

Work level `standard` is one pass. `oriented` is the same weights plus tiling
and recognition at 0, 90, 180, and 270 degrees.
"""

from dataclasses import dataclass

import cv2
import numpy as np

ORIENT_MIN_SIDE = 1600
TILE_SIZE = 1280
TILE_OVERLAP = 160
ROTATION_TRIGGER_DEGREES = 20
MERGE_IOU = 0.5

DET_MODEL = "PP-OCRv6_small_det"
REC_MODEL = "PP-OCRv6_small_rec"


@dataclass
class RawRegion:
    polygon: list[list[float]]
    text: str
    confidence: float
    rotation_degrees: float = 0.0


class OcrEngine:
    def detect(self, image: np.ndarray) -> list[RawRegion]:
        raise NotImplementedError

    def recognize(self, crop: np.ndarray) -> tuple[str, float]:
        raise NotImplementedError


def decode_image(data: bytes) -> np.ndarray:
    array = np.frombuffer(data, dtype=np.uint8)
    image = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("image is not a decodable 2D raster")
    return image


def _as_mapping(result: object) -> dict:
    if isinstance(result, dict):
        return result
    payload = getattr(result, "json", None)
    if callable(payload):
        payload = payload()
    if isinstance(payload, dict):
        return payload
    mapping = {}
    for key in ("rec_texts", "rec_scores", "rec_polys", "dt_polys", "rec_boxes", "rec_text", "rec_score"):
        if hasattr(result, key):
            mapping[key] = getattr(result, key)
    return mapping


def _quad_from_points(points: np.ndarray) -> list[list[float]]:
    pts = np.asarray(points, dtype=np.float32).reshape(-1, 2)
    if len(pts) == 4:
        return [[float(x), float(y)] for x, y in pts]
    rect = cv2.minAreaRect(pts)
    box = cv2.boxPoints(rect)
    return [[float(x), float(y)] for x, y in box]


def parse_ocr_result(result: object) -> list[RawRegion]:
    pages = result if isinstance(result, list) else [result]
    regions: list[RawRegion] = []
    for page in pages:
        data = _as_mapping(page)
        texts = list(data.get("rec_texts") or [])
        scores = list(data.get("rec_scores") or [])
        polys = data.get("rec_polys")
        if polys is None:
            polys = data.get("dt_polys")
        if polys is None:
            polys = data.get("rec_boxes")
        if polys is None:
            continue
        for index, poly in enumerate(polys):
            text = str(texts[index]) if index < len(texts) else ""
            score = float(scores[index]) if index < len(scores) else 0.0
            quad = _quad_from_points(np.asarray(poly))
            regions.append(
                RawRegion(
                    polygon=quad,
                    text=text,
                    confidence=score,
                    rotation_degrees=edge_angle(quad),
                )
            )
    return regions


def parse_recognition_result(result: object) -> tuple[str, float]:
    pages = result if isinstance(result, list) else [result]
    best_text = ""
    best_score = 0.0
    for page in pages:
        data = _as_mapping(page)
        if "rec_text" in data and "rec_texts" not in data:
            score = float(data.get("rec_score") or 0.0)
            if score >= best_score:
                best_text = str(data.get("rec_text") or "")
                best_score = score
            continue
        texts = list(data.get("rec_texts") or [])
        scores = list(data.get("rec_scores") or [])
        for text, score in zip(texts, scores):
            score_f = float(score)
            if score_f >= best_score:
                best_text = str(text)
                best_score = score_f
    return best_text, best_score


class PaddleOcrEngine(OcrEngine):
    """PP-OCRv6 small. HPI selects ONNX Runtime or OpenVINO on CPU."""

    def __init__(self) -> None:
        from paddleocr import PaddleOCR

        kwargs = dict(
            text_detection_model_name=DET_MODEL,
            text_recognition_model_name=REC_MODEL,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
        try:
            self._ocr = PaddleOCR(enable_hpi=True, **kwargs)
        except Exception:
            self._ocr = PaddleOCR(**kwargs)
        self._recognizer = None

    def _recognition_model(self):
        if self._recognizer is None:
            try:
                from paddleocr import TextRecognition

                self._recognizer = TextRecognition(model_name=REC_MODEL)
            except Exception:
                self._recognizer = False
        return self._recognizer or None

    def detect(self, image: np.ndarray) -> list[RawRegion]:
        return parse_ocr_result(self._ocr.predict(image))

    def recognize(self, crop: np.ndarray) -> tuple[str, float]:
        model = self._recognition_model()
        if model is not None:
            return parse_recognition_result(model.predict(crop))
        regions = self.detect(crop)
        if not regions:
            return "", 0.0
        best = max(regions, key=lambda region: region.confidence)
        return best.text, best.confidence


def edge_angle(polygon: list[list[float]]) -> float:
    pts = np.asarray(polygon, dtype=np.float32)
    best_len = -1.0
    angle = 0.0
    for index in range(len(pts)):
        start = pts[index]
        end = pts[(index + 1) % len(pts)]
        delta = end - start
        length = float(np.hypot(delta[0], delta[1]))
        if length > best_len:
            best_len = length
            angle = float(np.degrees(np.arctan2(delta[1], delta[0])))
    return angle


def is_rotated(polygon: list[list[float]]) -> bool:
    angle = abs(edge_angle(polygon)) % 180
    deviation = min(angle, 180 - angle)
    return deviation >= ROTATION_TRIGGER_DEGREES


def _positions(length: int, tile: int, overlap: int) -> list[int]:
    if length <= tile:
        return [0]
    step = max(tile - overlap, 1)
    starts = list(range(0, length - tile + 1, step))
    last = length - tile
    if starts[-1] != last:
        starts.append(last)
    return starts


def iter_tiles(image: np.ndarray, tile: int = TILE_SIZE, overlap: int = TILE_OVERLAP):
    height, width = image.shape[:2]
    for y in _positions(height, tile, overlap):
        for x in _positions(width, tile, overlap):
            yield x, y, image[y : y + tile, x : x + tile]


def _bounds(polygon: list[list[float]]) -> tuple[float, float, float, float]:
    xs = [point[0] for point in polygon]
    ys = [point[1] for point in polygon]
    return min(xs), min(ys), max(xs), max(ys)


def bbox_iou(left: list[list[float]], right: list[list[float]]) -> float:
    ax1, ay1, ax2, ay2 = _bounds(left)
    bx1, by1, bx2, by2 = _bounds(right)
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    if inter == 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union else 0.0


def merge_regions(regions: list[RawRegion], iou_threshold: float = MERGE_IOU) -> list[RawRegion]:
    ranked = sorted(regions, key=lambda region: region.confidence, reverse=True)
    kept: list[RawRegion] = []
    for region in ranked:
        if any(bbox_iou(region.polygon, existing.polygon) >= iou_threshold for existing in kept):
            continue
        kept.append(region)
    return kept


def _order_quad(polygon: list[list[float]]) -> np.ndarray:
    pts = np.asarray(polygon, dtype=np.float32)
    sums = pts.sum(axis=1)
    diffs = np.diff(pts, axis=1).reshape(-1)
    rect = np.zeros((4, 2), dtype=np.float32)
    rect[0] = pts[np.argmin(sums)]
    rect[2] = pts[np.argmax(sums)]
    rect[1] = pts[np.argmin(diffs)]
    rect[3] = pts[np.argmax(diffs)]
    return rect


def rectify(image: np.ndarray, polygon: list[list[float]]) -> np.ndarray:
    rect = _order_quad(polygon)
    width = int(max(np.linalg.norm(rect[1] - rect[0]), np.linalg.norm(rect[2] - rect[3])))
    height = int(max(np.linalg.norm(rect[3] - rect[0]), np.linalg.norm(rect[2] - rect[1])))
    width = max(width, 1)
    height = max(height, 1)
    destination = np.array(
        [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]],
        dtype=np.float32,
    )
    matrix = cv2.getPerspectiveTransform(rect, destination)
    return cv2.warpPerspective(image, matrix, (width, height))


def _rotations(crop: np.ndarray) -> list[tuple[float, np.ndarray]]:
    return [
        (0.0, crop),
        (90.0, cv2.rotate(crop, cv2.ROTATE_90_CLOCKWISE)),
        (180.0, cv2.rotate(crop, cv2.ROTATE_180)),
        (270.0, cv2.rotate(crop, cv2.ROTATE_90_COUNTERCLOCKWISE)),
    ]


def recognize_ensemble(crop: np.ndarray, engine: OcrEngine) -> tuple[str, float, float]:
    best_text = ""
    best_score = -1.0
    best_angle = 0.0
    for angle, rotated in _rotations(crop):
        text, score = engine.recognize(rotated)
        if score > best_score:
            best_text, best_score, best_angle = text, score, angle
    return best_text, max(best_score, 0.0), best_angle


def _shift(region: RawRegion, x: int, y: int) -> RawRegion:
    return RawRegion(
        polygon=[[point[0] + x, point[1] + y] for point in region.polygon],
        text=region.text,
        confidence=region.confidence,
        rotation_degrees=region.rotation_degrees,
    )


def read_standard(image: np.ndarray, engine: OcrEngine) -> list[RawRegion]:
    return engine.detect(image)


def read_oriented(image: np.ndarray, engine: OcrEngine) -> list[RawRegion]:
    found: list[RawRegion] = []
    for x, y, tile in iter_tiles(image):
        for region in engine.detect(tile):
            found.append(_shift(region, x, y))
    refined: list[RawRegion] = []
    for region in merge_regions(found):
        crop = rectify(image, region.polygon)
        text, score, angle = recognize_ensemble(crop, engine)
        refined.append(
            RawRegion(
                polygon=region.polygon,
                text=text or region.text,
                confidence=score if text else region.confidence,
                rotation_degrees=angle,
            )
        )
    return refined


def recognize_image(image_bytes: bytes, engine: OcrEngine) -> tuple[np.ndarray, str, list[RawRegion]]:
    """Decode and read an image. Safe to run off the event loop."""
    image = decode_image(image_bytes)
    work_level, regions = read_image(image, engine)
    return image, work_level, regions


def read_image(image: np.ndarray, engine: OcrEngine) -> tuple[str, list[RawRegion]]:
    height, width = image.shape[:2]
    if max(height, width) >= ORIENT_MIN_SIDE:
        return "oriented", read_oriented(image, engine)
    standard = read_standard(image, engine)
    if any(is_rotated(region.polygon) for region in standard):
        return "oriented", read_oriented(image, engine)
    return "standard", standard
