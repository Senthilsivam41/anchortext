# Product Requirements Document (PRD)

## Document Control

| Field | Value |
|---|---|
| Initiative Name | Text Detection & Pattern-Match Annotation Service — v0.1 |
| Document Owner | Sendil |
| Target Release | v0.1 (first cut) |
| Status | Draft |
| Links | [ADR-001: Tiered Text Detection Engine Strategy] · [Charter] |

---

## 1. Executive Summary

### 1.1 Problem Statement
No low-cost, general-purpose API exists that both detects/extracts all text from an arbitrary image and reconciles it against an external reference (S3, DB, JSON) to produce matched, structured annotations. Callers must otherwise stitch together separate OCR and matching pipelines, usually paying full cloud-OCR rates on every request regardless of image difficulty.

### 1.2 Target Outcomes & KPIs
- **Primary KPI:** [TBD — e.g., % of v0.1 requests successfully annotated end-to-end without manual correction]
- **Secondary KPI:** [TBD — e.g., cost per 1,000 requests at Tier 0 only]

---

## 2. System Boundary & Context

- **Actors:** External API callers (pay-as-you-go consumers); no internal SDK-specific actors in v0.1
- **Upstream Dependencies:** Caller-supplied image (sync upload); caller-registered reference source (S3 JSON)
- **Downstream Dependencies:** PaddleOCR (self-hosted, Tier 0 per ADR-001); reference-source storage (S3)
- **Context Diagram:** [Insert sequence: Client → Gateway → Preprocessing → Tier 0 OCR → Pattern Match → Annotation Assembler → Response]

---

## 3. The Specification Contracts (Core SDD)

### 3.1 Synchronous APIs (REST)
- **OpenAPI / Swagger Spec:** [TBD — link once drafted]
- **Key Endpoints Introduced:**
  - `POST /v1/detect` - Sync detection + annotation for a single image against a registered reference source
  - `POST /v1/match-config` - Register a reference source (S3 JSON) and receive a `source_id`
  - `GET /v1/match-config/{source_id}` - Retrieve current reference-source registration status

### 3.2 Asynchronous Events (Kafka / Flink / PubSub)
N/A for v0.1 — async batch jobs are deferred to v0.2 per Charter phasing.

### 3.3 Data Models

**DetectionRequest**
- `image` (binary/base64)
- `source_id` (string, references a registered reference source)

**Annotation** (one per detected text region)
- `text` (string)
- `bbox` (x, y, width, height)
- `confidence` (float, 0–1)
- `matched_ref` (nullable — the matched entry from the reference source)
- `match_score` (float, 0–1, nullable if no match found)

**MatchConfig**
- `source_id` (string)
- `source_type` (enum: `s3_json` only in v0.1)
- `source_location` (S3 URI)

---

## 4. Functional Requirements (Behavioral Specs)

### Scenario 1: Successful detection and match
- **Given** a caller has registered a valid S3-JSON reference source and received a `source_id`
- **When** the caller submits `POST /v1/detect` with an image and that `source_id`
- **Then** the response contains one `Annotation` per detected text region, each with `bbox`, `confidence`, and — where a regex/fuzzy match is found — `matched_ref` and `match_score`

### Scenario 2: Reference source not found
- **Given** a caller submits `POST /v1/detect` with a `source_id` that has not been registered or has expired
- **When** the request is processed
- **Then** the system returns a 404 status with an error indicating the `source_id` is invalid, and emits a failure metric — no partial detection is attempted

---

## 5. Non-Functional Requirements (NFRs)

| Category | Requirement | Measurement / SLA |
|---|---|---|
| Throughput | Expected peak load, v0.1 sync-only | [TBD] |
| Latency | Maximum acceptable sync response time | [TBD] |
| Availability | Expected uptime SLA for v0.1 | [TBD] |
| Data Retention | How long uploaded images / results are retained | [TBD] |
| Security | AuthN/AuthZ mechanism, PII handling for extracted text | [TBD — at minimum API-key auth] |
| Cost | Marginal cost ceiling per request at Tier 0 | [TBD — target near-zero per ADR-001] |

---

## 6. Observability & Telemetry

- **Business Metrics:** Requests per `source_id`, match-rate per request, escalation rate (n/a in v0.1 since Tier 1/2 don't exist yet, but confidence should still be logged per ADR-001 Action Item 2)
- **System Metrics:** PaddleOCR inference latency, queue depth if requests are ever throttled
- **Distributed Tracing:** [TBD — trace ID propagation through gateway → OCR → match layer]
- **Alerting Thresholds:** [TBD — e.g., page if 404-on-source_id rate exceeds X% or if OCR latency p95 exceeds threshold]

---

## 7. Rollout & Versioning Strategy

- **API Versioning:** URL versioning (`/v1/...`) from the start
- **Deployment Pattern:** Single-host deployment for v0.1 (GPU-optional, per Charter constraint); no canary/blue-green until v0.2 introduces async infra
- **Rollback Plan:** v0.1 is a single deployable service with no persistent schema migrations beyond `MatchConfig` registration — rollback is a straightforward redeploy of the prior container image; registered `source_id`s remain valid across rollback since the reference data itself lives in S3, not in the service
