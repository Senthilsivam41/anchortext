# ADR-002: Work-level pricing and caller review hold

**Status:** Accepted
**Date:** 2026-09-24
**Deciders:** Sendil

## Decision

Price each image by work level (`standard` or `oriented`), not by the engine tier in [ADR-001](02-adr-001-detection-engine-strategy.md). This cut uses self-hosted PaddleOCR only. Record one usage charge when detection finishes. Review and later edits do not add a charge.

Hold low-confidence regions until the caller’s user accepts or edits them in a minimal review UI. Release high-confidence regions on the sync response. The sync call does not wait on a person. We do not staff reviewers.

This narrows ADR-001’s consequence that price follows engine tier. Engine tier remains the detection-engine decision. It is not the price.

## Considered options

- **Price by engine tier** (PaddleOCR, then a harder open-weight detector, then cloud OCR). Rejected for this cut: only PaddleOCR ships, and the cost gap is one pass versus tiled four-way recognition on that same engine.
- **Flat fee per image.** Rejected: oriented tiling and four-way recognition cost more than one pass.
- **Price each released annotation after review.** Rejected: the compute is spent when detection finishes, and review is the caller’s own labor.
- **Return every region and let the caller review outside this product.** Rejected: low-confidence text stays held until the caller’s user accepts or edits it here.

## Consequences

- Every request records `standard` or `oriented` before the charge is written.
- Held regions need a review task and a caller-facing UI. The charter no longer bans all UI. It bans an in-house review team and any UI beyond that review surface.
- Async batch jobs stay deferred. The review task is the exception, because a person cannot complete it inside the sync detect call.
