# ADR-0001: Tiered text detection engine

## Status

Proposed

## Date

2026-09-24

## Context

The service must read text from arbitrary 2D images at low marginal cost, including hard cases that a single cheap pass misses. Sending every request to a paid cloud OCR API makes per-request cost dominate the price. A single self-hosted engine is cheap and will miss some hard images if nothing else is allowed later.

Price is not this decision. [ADR-0002](0002-work-level-pricing-and-review-hold.md) prices `standard` and `oriented` work on the engine chosen here. Tier 1 and Tier 2 are not prices.

## Decision

Adopt a tiered, confidence-gated detection pipeline, and ship only the first tier in this cut:

- Tier 0, the default: self-hosted PaddleOCR. The running model is PP-OCRv6 small.
- Tier 1, deferred: an open-weight detector and recognizer for harder layouts.
- Tier 2, deferred: paid cloud OCR, only when an earlier tier’s confidence falls below a threshold.

The billable cut ships PaddleOCR only. Turn off the document and text-line orientation classifiers. This product rectifies quadrilaterals and tries 0, 90, 180, and 270 degrees itself.

## Alternatives considered

### Alternative A: Cloud OCR for every request

- Benefits: accuracy without local model hosting.
- Costs/risks: marginal cost follows the vendor price on every image.
- Why not selected: it fights the cost goal before a hard image has been seen.

### Alternative B: Self-hosted OCR only, with no later tier

- Benefits: near-zero marginal cost and one deployable.
- Costs/risks: accuracy drops on hard images and there is no fallback.
- Why not selected as the long-term shape: the pipeline keeps room for Tier 1 and Tier 2. This cut still ships Tier 0 only.

## Consequences

- Positive: detection cost stays low on the common path, and ADR-0002 can price `standard` separately from tiled four-way recognition without changing the engine.
- Negative: hard images have no cloud fallback until a later decision builds Tier 1 or Tier 2.
- Operational: log confidence on every region so a later engine decision has data. The confidence threshold is a placeholder until production traffic exists.
- Compatibility/migration: callers depend on quadrilateral annotations, not on which engine produced them.
- Security/privacy: images and transcripts stay on this host except for the caller’s own S3 reference.

## Validation and revisit trigger

Revisit the confidence threshold once real request data exists. Revisit Tier 1 or Tier 2 if PP-OCRv6 small misses a material share of engineering text after the oriented pass.
