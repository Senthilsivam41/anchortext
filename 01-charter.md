# Project Charter

| Field | Value |
|---|---|
| Initiative Name | Text Detection & Pattern-Match Annotation Service (working name: TBD) |
| Owner | Sendil |
| Status | Draft |
| Target Release | v0.1 (first cut) |
| Links | [ADR-001] · [PRD] |

---

## 1. Problem Statement

There is no low-cost, general-purpose service that both (a) detects and extracts all text from an arbitrary image and (b) reconciles that text against an external reference — a database table, S3 bucket, or JSON structure — to produce annotated, matched results. Existing options force a choice between expensive per-call cloud OCR (Textract/Vision) with no built-in reference-matching, or building bespoke pipelines per use case. The gap is a general API/SDK that does detection + reconciliation + annotation in one call, at minimal marginal cost, sold pay-as-you-go.

## 2. Goals

- Detect and extract all text regions in an arbitrary input image
- Match extracted text against a caller-registered reference source (S3, DB table, or JSON)
- Return structured annotation output (bounding box, text, confidence, matched reference, match score)
- Keep marginal cost per request near-zero for the common case, escalating to paid cloud OCR only when needed
- Expose the capability as a versioned REST API with a thin SDK wrapper
- Ship a first-cut MVP that proves the tiered-cost model end-to-end, not the full feature surface

## 3. Non-Goals (v0.1)

- No semantic/embedding-based matching (regex + fuzzy match only)
- No SDK-specific logic beyond a thin wrapper over the REST contract
- No support for reference sources beyond S3-hosted JSON
- No sync SLA tier / no multi-region deployment
- No UI/dashboard for reviewing annotations

## 4. Success Criteria

- **Primary KPI:** [TBD — e.g., % of requests resolved at Tier 0 without escalation to paid OCR]
- **Secondary KPI:** [TBD — e.g., cost per 1,000 requests at target volume]
- End-to-end request (image in → matched annotation out) works for the S3-JSON reference case with no manual intervention

## 5. Stakeholders

- **Owner / decision-maker:** Sendil
- **Users:** External API/SDK consumers (pay-as-you-go)

## 6. Constraints

- Minimal-cost bias: prefer self-hosted/open-weight components over paid cloud APIs wherever accuracy allows
- First cut must be deployable on a single, GPU-optional host
- Markdown-native, git-diffable docs stack for all planning artifacts

## 7. Phasing

| Phase | Scope |
|---|---|
| v0.1 (this charter) | Tier 0 OCR only, regex + fuzzy match, S3-JSON reference source, sync API, no SDK |
| v0.2 | Async batch jobs, Tier 1/2 escalation on low confidence, additional reference source types |
| v0.3 | Semantic/embedding match, SDK, usage-based billing integration |
