"""Regex is applied during normalization. Fuzzy match uses RapidFuzz."""

import json
import re
from typing import Any

from rapidfuzz import fuzz, process

MATCH_SCORE_CUTOFF = 80
_S3_URI = re.compile(r"^s3://([^/]+)/(.+)$")


class ReferenceUnavailable(Exception):
    """The registered object could not be read."""


def parse_s3_uri(uri: str) -> tuple[str, str]:
    match = _S3_URI.match(uri)
    if not match:
        raise ValueError("source_location must be an s3://bucket/key URI")
    return match.group(1), match.group(2)


def load_s3_json(uri: str) -> Any:
    bucket, key = parse_s3_uri(uri)
    try:
        import boto3
    except ImportError as exc:
        raise ReferenceUnavailable("boto3 is not installed") from exc
    try:
        body = boto3.client("s3").get_object(Bucket=bucket, Key=key)["Body"].read()
    except Exception as exc:
        raise ReferenceUnavailable(str(exc)) from exc
    return json.loads(body)


def iter_entries(data: Any) -> list[tuple[str, Any]]:
    entries: list[tuple[str, Any]] = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, str):
                entries.append((item, item))
            elif isinstance(item, dict):
                text = item.get("text") or item.get("value") or item.get("name")
                if isinstance(text, str):
                    entries.append((text, item))
    elif isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, str):
                entries.append((value, {str(key): value}))
    return entries


def match_text(normalized: str, data: Any) -> tuple[Any | None, float | None]:
    entries = iter_entries(data)
    if not entries or not normalized:
        return None, None
    choices = [text for text, _entry in entries]
    hit = process.extractOne(
        normalized,
        choices,
        scorer=fuzz.WRatio,
        score_cutoff=MATCH_SCORE_CUTOFF,
    )
    if hit is None:
        return None, None
    _text, score, index = hit
    return entries[index][1], round(score / 100, 4)
