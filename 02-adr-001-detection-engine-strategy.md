# ADR-001: Tiered Text Detection Engine Strategy

**Status:** Proposed
**Date:** 2026-09-24
**Deciders:** Sendil

## Context

The service must detect and extract text from arbitrary images at minimal marginal cost, while still supporting hard cases (low-quality scans, unusual fonts, skewed layouts) that cheap engines miss. Running every request through a paid cloud OCR API (Textract, GCP Vision) is the simplest design but makes per-request cost dominate the pricing model. A single self-hosted engine (Tesseract/PaddleOCR) is cheap but will under-perform on hard images, risking annotation accuracy.

## Decision

Adopt a tiered, confidence-gated detection pipeline:

- **Tier 0 (default):** Self-hosted PaddleOCR — handles the majority of clean, well-formatted images at near-zero marginal cost
- **Tier 1 (fast-follow, not in v0.1):** Open-weight detector/recognizer pair (DBNet/CRAFT + TrOCR) for harder layouts
- **Tier 2 (fallback only):** Paid cloud OCR (Textract/GCP Vision), invoked only when Tier 0/1 confidence falls below a defined threshold

v0.1 ships Tier 0 only; Tier 1/2 escalation is deferred to v0.2 per the Charter's phasing.

## Options Considered

### Option A: Cloud OCR for every request (Textract/GCP Vision)

| Dimension | Assessment |
|-----------|------------|
| Complexity | Low |
| Cost | High — dominates unit economics at scale |
| Scalability | High (vendor-managed) |
| Team familiarity | High (multi-cloud experience) |

**Pros:** Best accuracy out of the box, no infra to run, fast to ship
**Cons:** Marginal cost per request undermines the "minimal cost" goal; vendor lock-in on pricing

### Option B: Self-hosted OCR only (Tesseract/PaddleOCR)

| Dimension | Assessment |
|-----------|------------|
| Complexity | Medium |
| Cost | Low |
| Scalability | Medium (self-managed capacity) |
| Team familiarity | Medium |

**Pros:** Near-zero marginal cost, full control
**Cons:** Accuracy degrades on hard images with no fallback, risks poor annotation quality on a meaningful subset of real-world inputs

### Option C: Tiered, confidence-gated pipeline (chosen)

| Dimension | Assessment |
|-----------|------------|
| Complexity | Medium-High |
| Cost | Low, with bounded worst-case (only hard cases hit Tier 2) |
| Scalability | Medium (self-managed base, vendor overflow) |
| Team familiarity | Medium |

**Pros:** Aligns cost curve with price curve; most requests stay cheap; hard cases still get accurate results
**Cons:** More moving parts than a single-engine design; confidence threshold needs tuning and monitoring

## Trade-off Analysis

Option C costs more to build than A or B individually, but it's the only option that doesn't force a choice between the Charter's cost goal and its accuracy expectations. The added complexity is front-loaded (routing + confidence threshold logic) rather than recurring, so it doesn't compound per-request cost the way Option A does.

## Consequences

- What becomes easier: pricing can be tied to tier consumed, giving a defensible margin structure
- What becomes harder: need observability on confidence-threshold behavior to catch mis-routing (e.g., Tier 0 silently under-escalating)
- What we'll need to revisit: the confidence threshold itself, once real request data exists — starting value should be treated as a placeholder, not tuned in advance of production traffic

## Action Items

1. [ ] Stand up Tier 0 (PaddleOCR) as the only engine for v0.1
2. [ ] Instrument confidence scores on every detection, even though Tier 1/2 routing isn't built yet, to gather tuning data ahead of v0.2
3. [ ] Defer Tier 1/2 implementation and threshold tuning to v0.2 per Charter phasing
