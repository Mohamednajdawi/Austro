# Sequential implementation backlog

Implementation update v0.2.0: S01 complete for synthetic scope; S02/S03 include real local inference and evidence verification; S04 exact-action local approval/execution is delivered; S05 has a working DE/EN browser interface and Chromium end-to-end test. These are local-pilot subsets, not enterprise acceptance. Estimates below are original planning ranges, not remaining-work commitments.

Remaining: deletion/retention policy, incremental trusted audit, global wall-clock deadlines and quotas, larger bilingual corpus, durable mid-run cancellation/recovery, source integration, independent accessibility validation and enterprise operations. Source-content fingerprints, exact action approval, cancellation/rejection and transactional note append now exist. S06 infrastructure workflow and S07/S08 enterprise integration/operations remain pending. See LOCAL_PILOT_RELEASE.md.

| Slice | Deliverable | Depends on | Acceptance | Effort |
| --- | --- | --- | --- | --- |
| S01 | Strict safe settings, fixture principals, workspace isolation, SQLite migrations and authenticated ticket read | Scaffold verification | A01–A04, A19 | 2–3 days |
| S02 | Permission-aware retrieval, citations, versions and deletion/cache handling | S01 | A05–A08, A17 | 2–4 days |
| S03 | Fake classifier/retriever/drafter, bounded workflow, model gateway and denial evidence | S02 | A09–A12, A18, A20 | 3–4 days |
| S04 | Immutable preview, approval, atomic mock execution, cancellation and recovery | S03 | A13–A16, A21–A24 | 3–5 days |
| S05 | DE/EN accessible self-contained UI, evidence export, CSRF and safe rendering | S04 | A25–A28 | 3–4 days |
| S06 | Synthetic infrastructure template, adversarial regression and demo script | S05 | A29–A31 + full suite | 2–4 days |
| S07 | Licensed platform, approved models, identity, source and security adapters | S06 + G01–G06 | Actual adapter contracts/full-path data evidence | After discovery |
| S08 | Pilot capacity, HA/recovery, legal/security review, support and business baseline | S07 + G07–G10 | ACG-approved acceptance | After discovery |

## S01 start instructions

First write failing tests for safe settings and unknown/live-mode rejection. Then implement server-owned test principals with explicit synthetic sessions. Add two isolated workspaces and read-only synthetic tickets. Reject browser role overrides, disabled users and missing identity. Add startup validation before any business endpoint. Never load host cloud credentials.

## Evidence discipline

Record command, date, dependency snapshot, acceptance IDs and limitations per slice. Smoke tests are not domain acceptance tests. Never silently substitute fake adapters in tests claiming live coverage.

## Deferred, not shipped

Invoice/OCR processing, natural-language authoring, OIDC, real DLP/SIEM, real-model quality, 500-user capacity, distributed execution and production failover.
