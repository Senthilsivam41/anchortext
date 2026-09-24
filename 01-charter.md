# Project Charter

| Field | Value |
|---|---|
| Initiative Name | Oriented engineering-text annotation service |
| Owner | Sendil |
| Status | Draft |
| Target Release | Billable cut (all six initiatives) |
| Links | [Plan](00-plan-billable-annotation.md) · [Glossary](CONTEXT.md) · [ADR-001](02-adr-001-detection-engine-strategy.md) · [ADR-002](04-adr-002-work-level-pricing-and-review-hold.md) · [PRD](03-prd.md) |

---

## 1. Problem Statement

There is no low-cost, general-purpose service that both (a) detects and extracts all text from an arbitrary 2D image, including engineering drawings with horizontal, vertical, upside-down, and slightly rotated text, and (b) reconciles the normalized text against a caller-registered reference to produce annotations. Existing options force a choice between expensive per-call cloud OCR with no reference matching, or a bespoke pipeline per drawing. The gap is one API that detects, normalizes, matches, and returns annotations, and that charges once per image at the work level actually used.

## 2. Goals

- Extract every text region from a 2D image, including engineering drawings where text is horizontal, vertical, upside down, outside the sheet, or slightly rotated
- Represent each region as a quadrilateral with an orientation, plus raw transcript, normalized transcript, confidence, and an engineering text class (dimension, tolerance, thread callout, surface finish, part tag, revision, sheet metadata, note)
- Match normalized text to the caller-registered reference (S3 JSON, `source_id`) and return the matched reference and match score
- Release high-confidence annotations on the sync response, and hold low-confidence ones until the caller’s user accepts or edits them in a minimal review UI
- Charge once per image when detection finishes, priced by work level (`standard` or `oriented`). Review and edits add no second charge
- Keep the engine on self-hosted PaddleOCR so the common case stays cheap

## 3. Non-Goals (this cut)

- No DWG, DXF, or other CAD-native extraction. Input is a 2D image
- No keypoints, masks, or generic object boxes
- No association of text to leaders, dimension lines, title-block zones, or BOM cells
- No engine other than PaddleOCR. ADR-001 Tier 1 and Tier 2 stay engine options, not prices
- No semantic or embedding match. Regex and fuzzy match only
- No reference source other than S3-hosted JSON
- No SDK beyond a thin wrapper over the REST contract, and no SDK in this cut
- No in-house review team. The only UI is the caller’s review of held regions
- No second charge for review or edits
- No sync SLA tier and no multi-region deployment
- No async batch jobs. A review task is the exception, because a person cannot finish it inside the sync detect call

## 4. Success Criteria

- **Primary KPI:** [TBD — e.g., % of images resolved at work level `standard`]
- **Secondary KPI:** [TBD — e.g., cost per 1,000 images at each work level]
- An image with a valid `source_id` returns released annotations for high-confidence regions with no manual step
- Low-confidence regions become a review task the caller’s user can accept or edit, after which those annotations are released
- Each image produces exactly one usage charge, recorded when detection finishes, at the work level that ran

## 5. Stakeholders

- **Owner / decision-maker:** Sendil
- **Users:** External API consumers (pay-as-you-go), including the caller’s user who completes review tasks

## 6. Constraints

- Minimal-cost bias: self-hosted PaddleOCR, with oriented processing only when the image needs it
- First cut must be deployable on a single, GPU-optional host
- Markdown-native, git-diffable docs stack for all planning artifacts
- A sync detect call does not wait on a person

## 7. Initiatives

The product is billable only when all six exist.

| Initiative | Scope |
|---|---|
| Oriented detection | Tile large images, detect four-corner regions with PP-OCR, rectify each crop, try 0/90/180/270, keep the best transcript. Record `standard` or `oriented`. Log confidence on every region |
| Engineering normalization | Assign a text class and a normalized transcript. Keep the raw string. Produce a domain-validation score used, with OCR confidence, to release or hold |
| Reference match | Register an S3 JSON source and receive a `source_id`. Match normalized text with regex and fuzzy match. Unknown `source_id` is a 404 and does not detect |
| Review hold | Sync detect returns released annotations plus held review tasks. A minimal UI lets the caller’s user accept or edit held regions, then releases them |
| Usage charge | One charge per image when detection finishes, keyed by work level. Later edits do not rebill. Attribute the charge to the caller (API key at minimum) |
| Contract update | Annotation carries polygon, rotation, raw and normalized text, text class, validation score, and release state. Review-task reads and correction writes live under `/v1` |

### Deferred

- CAD-native extraction
- Spatial association of text to geometry
- ADR-001 Tier 1 and Tier 2 engines
- Semantic match, additional reference-source types, and an SDK
- Async batch jobs other than the review task
