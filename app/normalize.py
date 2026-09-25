"""Engineering text class, normalized transcript, and the release bar.

The release thresholds are placeholders until production traffic exists.
"""

import re
from dataclasses import dataclass

from app.schemas import TextClass

# Placeholder release bar. Do not treat these numbers as tuned.
RELEASE_CONFIDENCE = 0.85
RELEASE_VALIDATION = 0.6

_THREAD = re.compile(
    r"^(?:M\d+(?:\.\d+)?(?:\s*×\s*\d+(?:\.\d+)?)?|\d+/\d+-\d+\s+UNC)$",
    re.IGNORECASE,
)
_TOLERANCE = re.compile(
    r"^(?:±\s*\d+(?:\.\d+)?|\+\d+(?:\.\d+)?/-\d+(?:\.\d+)?|[HhGg]\d{1,2})$"
)
_SURFACE = re.compile(r"^(?:Ra|Rz)\s*\d+(?:\.\d+)?$", re.IGNORECASE)
_REVISION = re.compile(r"^REV\s+[A-Z0-9]+$", re.IGNORECASE)
_SHEET = re.compile(
    r"^(?:SCALE\s+\d+\s*:\s*\d+|SHEET\s+\d+\s+OF\s+\d+)$",
    re.IGNORECASE,
)
_DIMENSION = re.compile(r"^(?:[Øø⌀R]\s*)?\d+(?:\.\d+)?$", re.IGNORECASE)
_PART = re.compile(r"^[A-Z]{1,12}-\d+[A-Z0-9]*$", re.IGNORECASE)

_CLASS_PATTERNS: list[tuple[TextClass, re.Pattern[str]]] = [
    ("sheet_metadata", _SHEET),
    ("revision", _REVISION),
    ("surface_finish", _SURFACE),
    ("thread_callout", _THREAD),
    ("tolerance", _TOLERANCE),
    ("dimension", _DIMENSION),
    ("part_tag", _PART),
]


@dataclass(frozen=True)
class NormalizedText:
    text_normalized: str
    text_class: TextClass
    domain_validation_score: float
    corrected: bool


def apply_ocr_corrections(text: str) -> str:
    """Fix common engineering OCR confusions without dropping the raw string."""
    cleaned = text.strip()
    cleaned = re.sub(r"(?<=\d)[Oo](?=\s|[xX×]|$)", "0", cleaned)
    cleaned = re.sub(r"(?<=[A-Za-z])[Oo](?=\d)", "0", cleaned)
    cleaned = re.sub(r"(?<=\d)\s*[xX]\s*(?=\d)", " × ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _classify(text: str) -> TextClass | None:
    for name, pattern in _CLASS_PATTERNS:
        if pattern.match(text):
            return name
    return None


def _present(text: str, text_class: TextClass) -> str:
    if text_class in {"revision", "surface_finish", "sheet_metadata", "part_tag"}:
        return text.upper()
    return text


def normalize(raw: str) -> NormalizedText:
    original = raw.strip()
    corrected = apply_ocr_corrections(original)
    original_class = _classify(original)
    corrected_class = _classify(corrected)

    if corrected_class and corrected != original:
        return NormalizedText(
            text_normalized=_present(corrected, corrected_class),
            text_class=corrected_class,
            domain_validation_score=0.9,
            corrected=True,
        )
    if original_class:
        return NormalizedText(
            text_normalized=_present(original, original_class),
            text_class=original_class,
            domain_validation_score=0.97,
            corrected=False,
        )
    if corrected_class:
        return NormalizedText(
            text_normalized=_present(corrected, corrected_class),
            text_class=corrected_class,
            domain_validation_score=0.9,
            corrected=True,
        )
    return NormalizedText(
        text_normalized=corrected or original,
        text_class="note",
        domain_validation_score=0.4,
        corrected=corrected != original,
    )


def clears_release_bar(confidence: float, domain_validation_score: float) -> bool:
    return confidence >= RELEASE_CONFIDENCE and domain_validation_score >= RELEASE_VALIDATION
