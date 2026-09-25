import numpy as np

from app.detect import (
    RawRegion,
    bbox_iou,
    is_rotated,
    merge_regions,
    parse_ocr_result,
    read_image,
    rectify,
)
from app.match import iter_entries, match_text
from app.normalize import normalize


def test_thread_callout_corrects_ocr_confusions():
    result = normalize("M1O x 1.75")
    assert result.text_normalized == "M10 × 1.75"
    assert result.text_class == "thread_callout"
    assert result.domain_validation_score == 0.9


def test_note_stays_below_the_release_bar():
    result = normalize("see detail")
    assert result.text_class == "note"
    assert result.domain_validation_score < 0.6


def test_fuzzy_match_returns_the_reference_entry():
    matched, score = match_text("M10 × 1.75", ["REV A", "M10 × 1.75"])
    assert matched == "M10 × 1.75"
    assert score == 1.0


def test_reference_entries_accept_objects():
    entries = iter_entries([{"text": "REV A", "id": "1"}])
    assert entries == [("REV A", {"text": "REV A", "id": "1"})]


def test_parse_ocr_result_reads_quads():
    regions = parse_ocr_result(
        {
            "rec_texts": ["25"],
            "rec_scores": [0.91],
            "rec_polys": [[[1, 2], [11, 2], [11, 8], [1, 8]]],
        }
    )
    assert regions[0].text == "25"
    assert regions[0].confidence == 0.91
    assert len(regions[0].polygon) == 4


def test_merge_keeps_the_higher_confidence_overlap():
    low = RawRegion([[0, 0], [10, 0], [10, 4], [0, 4]], "a", 0.4)
    high = RawRegion([[1, 0], [11, 0], [11, 4], [1, 4]], "b", 0.9)
    assert bbox_iou(low.polygon, high.polygon) > 0.5
    merged = merge_regions([low, high])
    assert [region.text for region in merged] == ["b"]


def test_rectify_returns_a_crop():
    image = np.zeros((40, 80, 3), dtype=np.uint8)
    crop = rectify(image, [[5, 5], [25, 6], [24, 18], [4, 16]])
    assert crop.size > 0


class FakeEngine:
    def __init__(self, regions):
        self.regions = regions
        self.detect_calls = 0
        self.recognize_calls = 0

    def detect(self, image):
        self.detect_calls += 1
        return list(self.regions)

    def recognize(self, crop):
        self.recognize_calls += 1
        return "M10 × 1.75", 0.99


def test_small_horizontal_image_stays_standard():
    engine = FakeEngine([RawRegion([[0, 0], [20, 0], [20, 8], [0, 8]], "25", 0.95)])
    image = np.zeros((64, 64, 3), dtype=np.uint8)
    level, regions = read_image(image, engine)
    assert level == "standard"
    assert engine.recognize_calls == 0
    assert regions[0].text == "25"


def test_vertical_text_uses_the_oriented_ensemble():
    vertical = RawRegion([[0, 0], [8, 0], [8, 40], [0, 40]], "M10", 0.5)
    assert is_rotated(vertical.polygon)
    engine = FakeEngine([vertical])
    image = np.zeros((80, 80, 3), dtype=np.uint8)
    level, regions = read_image(image, engine)
    assert level == "oriented"
    assert engine.recognize_calls == 4
    assert regions[0].text == "M10 × 1.75"
    assert regions[0].rotation_degrees in {0.0, 90.0, 180.0, 270.0}
