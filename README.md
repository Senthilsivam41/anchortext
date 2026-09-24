# Anchortext

Anchortext is a pay-as-you-go API that reads text from a 2D image, including engineering drawings with horizontal, vertical, upside-down, and slightly rotated text. It returns engineering text annotations matched to a caller-registered reference, and charges once per image.

The recognizer is self-hosted PaddleOCR. Price follows **work level** (`standard` or `oriented`), not which OCR engine ran.

## Goals

- Extract every text region from a 2D image as a quadrilateral with an orientation.
- Keep the raw transcript, a normalized transcript, confidence, and an engineering text class (dimension, tolerance, thread callout, surface finish, part tag, revision, sheet metadata, note).
- Match normalized text to a caller-registered S3 JSON reference.
- Release high-confidence annotations immediately. Hold low-confidence ones until the caller’s user accepts or edits them.
- Charge once per image when detection finishes. Review and edits are included.

## Initiatives required to bill

The product is billable only when all six exist:

1. Oriented detection (one pass, or tile + rectify + four-way recognition)
2. Engineering normalization and text class
3. Reference match against registered S3 JSON
4. Review hold and a minimal UI for the caller’s user
5. One usage charge per image, keyed by work level
6. The `/v1` contract for annotations, match config, and review

CAD files, keypoints, masks, spatial association to leaders, other OCR engines, semantic match, extra reference sources, and an SDK are not required to bill.

## Docs

| Doc | What it decides |
|---|---|
| [00-plan-billable-annotation.md](00-plan-billable-annotation.md) | Goals, initiatives, and what is deferred |
| [CONTEXT.md](CONTEXT.md) | Glossary |
| [01-charter.md](01-charter.md) | Problem, goals, non-goals, initiatives |
| [02-adr-001-detection-engine-strategy.md](02-adr-001-detection-engine-strategy.md) | PaddleOCR first; later engines are not the price |
| [04-adr-002-work-level-pricing-and-review-hold.md](04-adr-002-work-level-pricing-and-review-hold.md) | Work-level price and caller review hold |
| [03-prd.md](03-prd.md) | API, annotation model, and scenarios |

Start with the glossary, then the charter.
