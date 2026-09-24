# Product Requirements Document (PRD)

## Document Control

| Field | Value |
|---|---|
| Initiative Name | Oriented engineering-text annotation service — billable cut |
| Document Owner | Sendil |
| Target Release | Billable cut (all six charter initiatives) |
| Status | Draft |
| Links | [Plan](00-plan-billable-annotation.md) · [Glossary](CONTEXT.md) · [Charter](01-charter.md) · [ADR-001](02-adr-001-detection-engine-strategy.md) · [ADR-002](04-adr-002-work-level-pricing-and-review-hold.md) |

---

## 1. Executive Summary

### 1.1 Problem Statement
No low-cost API both reads all text from a 2D image — including engineering drawings with mixed orientations — and reconciles the normalized text against a caller-registered S3 JSON reference. Callers otherwise stitch OCR and matching together and pay full cloud-OCR rates on every image.

### 1.2 Target Outcomes & KPIs
- **Primary KPI:** [TBD — e.g., % of images processed at work level `standard`]
- **Secondary KPI:** [TBD — e.g., one usage charge per image, with cost per 1,000 images at each work level]
- High-confidence regions are released on the sync response. Low-confidence regions are held for the caller’s user. Each image is charged once, at detection finish.

---

## 2. System Boundary & Context

- **Actors:** External API callers (pay-as-you-go). The caller’s user completes review tasks. No in-house reviewer.
- **Upstream:** A 2D image (sync upload) and a registered reference source (S3 JSON)
- **Downstream:** PaddleOCR (self-hosted). Work level is `standard` (one pass) or `oriented` (tile, rectify, 0/90/180/270). Reference bytes live in S3
- **Context:** Client → Gateway → Work-level detection → Normalize and class → Pattern match → Release or hold → Usage charge. Held regions → caller review UI → release. The charge is not repeated

Terms are defined in [CONTEXT.md](CONTEXT.md).

---

## 3. The Specification Contracts (Core SDD)

### 3.1 Synchronous APIs (REST)
- **OpenAPI / Swagger Spec:** [TBD — link once drafted]
- **API versioning:** URL versioning (`/v1/...`)
- **Key endpoints:**
  - `POST /v1/detect` — Detect, normalize, match, release or hold, and record the usage charge. Does not wait on a person
  - `POST /v1/match-config` — Register an S3 JSON reference source and receive a `source_id`
  - `GET /v1/match-config/{source_id}` — Registration status for a reference source
  - `GET /v1/reviews/{review_id}` — One review task and its held annotations
  - `POST /v1/reviews/{review_id}/corrections` — Caller accepts or edits held annotations. Releases them. Does not create a usage charge

### 3.2 Asynchronous Events (Kafka / Flink / PubSub)
No batch pipeline in this cut. A review task outlives the sync detect call because a person completes it. That task is stored and read through the review endpoints above. General async batch jobs stay deferred.

### 3.3 Data Models

**DetectionRequest**
- `image` (binary/base64, a 2D image)
- `source_id` (string, a registered reference source)

**DetectionResponse**
- `work_level` (`standard` or `oriented`)
- `usage_charge` (one charge: work level, caller identity, recorded at detection finish; rate card TBD)
- `released` (list of released annotations)
- `held` (list of review tasks)

**Annotation**
- `text_raw` (string, recognizer output)
- `text_normalized` (string, engineering-format correction)
- `text_class` (enum: `dimension`, `tolerance`, `thread_callout`, `surface_finish`, `part_tag`, `revision`, `sheet_metadata`, `note`)
- `polygon` (four corners, in image pixels)
- `rotation_degrees` (float)
- `confidence` (float, 0–1, OCR)
- `domain_validation_score` (float, 0–1)
- `matched_ref` (nullable entry from the reference source)
- `match_score` (float, 0–1, nullable when nothing matched)
- `release_state` (`released` or `held`)

**ReviewTask**
- `review_id` (string)
- `annotations` (the held annotations for this task)
- `status` (`open` or `released`)

**MatchConfig**
- `source_id` (string)
- `source_type` (enum: `s3_json` only)
- `source_location` (S3 URI)

**CorrectionRequest**
- For each held annotation: `accept` or a replacement `text_normalized` and `text_class`
- Raw transcript, polygon, and confidence stay as detected

---

## 4. Functional Requirements (Behavioral Specs)

### Scenario 1: High-confidence detection, match, and release
- **Given** a caller has registered a valid S3 JSON reference and holds a `source_id`
- **When** the caller submits `POST /v1/detect` with a 2D image and that `source_id`, and a region’s confidence and domain-validation score clear the release bar
- **Then** that region is in `released` with polygon, rotation, raw and normalized text, text class, and — where regex or fuzzy match hits — `matched_ref` and `match_score`
- **And** the response includes exactly one `usage_charge` at the work level that ran

### Scenario 2: Reference source not found
- **Given** a caller submits `POST /v1/detect` with a `source_id` that is not registered
- **When** the request is processed
- **Then** the system returns 404, the `source_id` is invalid, and it emits a failure metric
- **And** it does not detect, hold, or charge

### Scenario 3: Low-confidence region is held
- **Given** a valid `source_id` and an image whose region fails the release bar
- **When** detect finishes
- **Then** that region is omitted from `released` and returned inside an open review task in `held`
- **And** the usage charge for the image is still recorded once, at the work level that ran

### Scenario 4: Caller releases a held region
- **Given** an open review task
- **When** the caller’s user submits `POST /v1/reviews/{review_id}/corrections` accepting or editing the held region
- **Then** the annotation’s `release_state` becomes `released`, the task status becomes `released`, and the edited normalized text and text class are stored
- **And** no second usage charge is recorded

### Scenario 5: Oriented work level
- **Given** an image that cannot be resolved by one pass (large sheet, or text at 90/180/270 or a slight angle)
- **When** detect runs the tiled, rectified, four-way path
- **Then** `work_level` is `oriented` and the single usage charge uses that work level
- **And** a one-pass image is `standard`

---

## 5. Non-Functional Requirements (NFRs)

| Category | Requirement | Measurement / SLA |
|---|---|---|
| Throughput | Expected peak load, sync detect | [TBD] |
| Latency | Maximum acceptable sync detect time, excluding human review | [TBD] |
| Availability | Expected uptime | [TBD] |
| Data Retention | How long images, annotations, and review tasks are retained | [TBD] |
| Security | AuthN/AuthZ, PII in extracted text | [TBD — at minimum API-key auth, and the charge is attributed to that caller] |
| Cost | One charge per image at the work level consumed. Oriented costs more than standard. Engine remains PaddleOCR | Rate card TBD. Target: near-zero marginal cost on `standard` |

The release bar (confidence plus domain-validation score) is a placeholder until production traffic exists. Do not tune it in advance.

---

## 6. Observability & Telemetry

- **Business metrics:** Requests per `source_id`, match rate, share of images at each work level, hold rate, review tasks released, charges written per image (must stay at one)
- **System metrics:** PaddleOCR latency for standard and oriented paths, tile count on the oriented path
- **Distributed tracing:** [TBD — trace id through gateway → detection → normalize → match → charge]
- **Alerting:** [TBD — page if 404-on-source_id exceeds a threshold, if oriented latency p95 exceeds a threshold, or if any image records a second charge]

---

## 7. Rollout & Versioning Strategy

- **API versioning:** `/v1/...` from the start
- **Deployment:** Single host, GPU-optional. The review UI is the only user interface and ships with this cut. No canary or blue-green until a later batch pipeline exists
- **Rollback:** Redeploy the prior image. Registered `source_id`s stay valid because reference bytes live in S3. Usage charges already recorded are not replayed by a rollback
