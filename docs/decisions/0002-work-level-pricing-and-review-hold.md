# ADR-0002: Work-level pricing and caller review hold

## Status

Accepted

## Date

2026-09-24

## Context

PaddleOCR is the engine for this cut ([ADR-0001](0001-detection-engine-strategy.md)). The cost difference is one pass versus tiled, rectified, four-way recognition on that same engine, not a different engine. A sync detect call also cannot wait while a person fixes a bad transcript.

## Decision

Price each image by work level, `standard` or `oriented`, not by engine tier. Record one usage charge when detection finishes. Review and later edits do not add a charge.

Hold low-confidence regions until the caller’s user accepts or edits them in a minimal review UI. Release high-confidence regions on the sync response. The sync call does not wait on a person. We do not staff reviewers.

This narrows ADR-0001’s consequence that price follows engine tier. Engine tier remains the detection-engine decision. It is not the price.

## Alternatives considered

### Alternative A: Price by engine tier

- Benefits: matches an older reading of ADR-0001.
- Costs/risks: only PaddleOCR ships, so the price would not track the extra work.
- Why not selected: tiled detection and four-way recognition are the cost gap.

### Alternative B: Flat fee per image

- Benefits: one price to explain.
- Costs/risks: oriented work costs more than one pass.
- Why not selected: the price would ignore the work that was done.

### Alternative C: Charge per released annotation after review

- Benefits: the caller pays only for text they accepted.
- Costs/risks: compute is spent when detection finishes, and review is the caller’s labor.
- Why not selected: the charge would lag the cost and invite a second bill at edit time.

### Alternative D: Return every region and let the caller review outside this product

- Benefits: no review UI.
- Costs/risks: low-confidence text would leave this product as if it were final.
- Why not selected: low-confidence text stays held until the caller’s user accepts or edits it here.

## Consequences

- Positive: the common image stays on the cheap pass, and low-confidence text is not released as final.
- Negative: held regions need a review task and a caller-facing UI. The product bans an in-house review team and any UI beyond that review surface.
- Operational: every request records `standard` or `oriented` before the charge is written. Async batch jobs stay deferred. The review task is the exception, because a person cannot finish it inside the sync detect call.
- Compatibility/migration: `standard` and `oriented` are the price axis. Engine tier is not.
- Security/privacy: the review page is limited to the caller who owns the task. The API key is stored as a hash.

## Validation and revisit trigger

Revisit the release-bar cutoffs after production traffic exists. Revisit the rate card when a price per work level is chosen.
