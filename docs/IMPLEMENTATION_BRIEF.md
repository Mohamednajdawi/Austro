# Implementation brief

Prepared 2026-09-23. These technical defaults are recommendations, not ACG-approved specifications or claims of shipped capabilities.

Implementation status: see CHALLENGE_EVIDENCE.md and BACKLOG.md. The shipped v0.1.0 slice uses uv/src layout and TOML prompts from the adapted mo_skills profile. The larger architecture below remains a target, not a description of fully implemented features. Current workflows end at `awaiting_review`; they do not implement the full approval/execution state machine below.

## Outcome

Build an evidence-producing control demonstrator and reusable integration boundary around a supported enterprise agent platform. First: IT-support ticket preparation. Second: infrastructure change-request drafting against a synthetic authoritative asset database. Invoice review is a later template.

The offline build proves application controls with fake agents. It cannot prove language quality, real-model robustness, vendor feature parity, enterprise support or 500-user capacity. Platform integration is required before representing it as the challenge solution.

## Requirement mapping

| ID | Requirement | Initial evidence | Later dependency |
| --- | --- | --- | --- |
| R01 | Human-supervised multi-agent workflows | Bounded classifier/retriever/drafter simulation | Supported orchestration and real agents |
| R02 | Multiple models/providers | Adapter contract and alternate fake behavior | Two approved real model/provider configurations |
| R03 | Inspection before model processing | Spy proves denied context is never sent | All preprocessing/model paths + real DLP |
| R04 | GDPR/AI Act | Synthetic-only scope and processing inventory | Legal classification, contracts and DPIA decisions |
| R05 | Source/role authorization | Server-controlled identities, query-time ACL | Actual IdP/source entitlement fidelity |
| R06 | Prevent uncontrolled reuse | No external inference/telemetry; scoped memory | Subprocessors, retention, contracts and egress evidence |
| R07 | Traceability/data location | Structured audit with redacted references | SIEM, external anchoring, retention and hosting map |
| R08 | Human control of critical actions | Parameter-bound approval and executor enforcement | ACG approval rules and native change process |
| R09 | Enterprise/security integration | Typed mock adapters | Named sandbox APIs and security interfaces |
| R10 | German/English | Bilingual fixtures and UI | Held-out model evaluation with experts |
| R11 | 500 users, growth | Quotas and load-test plan | Measured concurrency, HA and sizing |
| R12 | Lifecycle, accessibility, org separation | Versions, workspaces, accessible UI design | EN 301 549 scope, authoring and operational validation |

## Architecture decisions

1. Python 3.11/FastAPI/Pydantic v2 integration harness; pytest/TestClient with HTTPX2 tests, as required by current Starlette. This is NOT the enterprise orchestration product.
2. Modular monolith initially: identity, retrieval, policy, approvals, executor, workflow and audit boundaries. No unnecessary microservices.
3. SQLite for single-host synthetic demo only, with explicit transactions and row versions. Production HA/storage chosen with the platform, not assumed equivalent.
4. Deterministic fake model and synthetic source/action adapters first, clearly labeled. Real inference disabled by design until approved.
5. Simple self-contained HTML/CSS/JavaScript UI later, no frontend framework or CDN dependencies. DE/EN messages, keyboard-accessible approval previews and visible demo banner.
6. Supported platform owns enterprise orchestration/lifecycle. IBM watsonx Orchestrate is a candidate, not an authorized purchase. Copilot Studio remains an alternative if full-path controls pass.
7. Do not install IBM Developer Edition over existing Windows/Docker: current documentation warns of conflict. Use separately approved clean environment or licensed remote tenant.
8. Do not discover/reuse credentials from unrelated projects. No real-system adapter until external gates close.

## Security invariants

- Principal/workspace/roles come from a server-validated session, never caller-supplied JSON. Fixture identities are test-only, impossible to enable in live mode.
- Delegation cannot increase privilege. Effective authority is bounded by principal, agent, workflow, workspace, tool and destination.
- Preserve source versions, permissions and classification on chunks, citations, caches, memory and intermediate messages.
- Filter authorization before any model/reranker receives content; recheck on permission changes and cache reuse.
- Inspect complete payload before EVERY model call, including OCR/embedding/preprocessing paths when added. Unknown classification/provider/destination defaults to deny.
- Classification metadata dominates heuristic scanning. Regex examples are not enterprise DLP or a complete prompt-injection defense.
- Reading a restricted source does not permit publishing its summary into a broadly visible ticket. Enforce destination audience policy.
- Model outputs never authorize tools, mint approvals or modify policies. Strict schemas reject unexpected fields/coercion; use allowlisted typed actions only.
- No arbitrary shell, dynamic tool installation, arbitrary URL fetching, email sending, account changes, payments or production infrastructure writes.
- No streaming of unreviewed sensitive output. Render escaped text; no active remote images/links from model content.
- Application no-network behavior is not an OS-level egress guarantee. Validate deployment network controls separately.
- Audit stores actor/run IDs, timestamps, source/policy/model/tool versions, decisions, approvals, outcomes and redacted payload references. No credentials, unnecessary raw personal data or claimed hidden model reasoning.
- A local hash chain is only tamper-evident relative to a trusted anchor; do not call local writable logs immutable.

## Domain contracts

| Entity | Fields and rules |
| --- | --- |
| Principal | ID, workspace, active status, server-resolved roles, authorization version |
| SourceRecord | ID, version, classification, ACL, workspace, freshness, content |
| Run | ID, owner/workspace, state, workflow/model/policy versions, deadlines, budget |
| Proposal | ID/run, typed action, target, canonical parameters, target version, destination audience, digest |
| Approval | Proposal digest, approver, policy version, UTC issued/expiry, nonce, consumed/revoked state |
| AuditEvent | ID/run, UTC timestamp, actor, event, outcome, versions, redacted references |

Action digest covers ALL execution-relevant fields with stable serialization. Strict schemas reject extra fields and security-sensitive coercions. Future money calculations use Decimal/integer minor units.

## Workflow

`RECEIVED -> CLASSIFIED -> RETRIEVED -> DRAFTED -> AWAITING_APPROVAL -> APPROVED -> EXECUTING -> COMPLETED`

Other states: BLOCKED, FAILED, CANCELLED, EXPIRED, RECONCILIATION_REQUIRED. Exceptions never imply approval. Permission/target/policy changes trigger revalidation and new approval as necessary. Inject the clock in tests.

Demo writes: append a reviewed internal note to a synthetic ticket or create a synthetic change request. Conservative default: every write approved by an authorized person other than the requester, pending ACG's actual rules.

Mock-store approval consumption and action mutation must be transactional. Future external actions require idempotency keys, durable intent/outbox and reconciliation. Never promise exactly-once across remote systems or retry an ambiguous timeout blindly.

## Planned API (not implemented)

- POST /api/runs: start scoped workflow using session principal.
- GET /api/runs/{id}: authorized state and evidence.
- POST /api/runs/{id}/cancel: stop pending work.
- GET /api/proposals/{id}: exact action preview.
- POST /api/proposals/{id}/approve or /reject: server-resolved authority.
- Internal executor: revalidate action, approval, policy and target version.
- GET /api/runs/{id}/evidence: authorized redacted export.

Before browser exposure: session/CSRF controls on mutations, safe error messages, no unrestricted CORS. Unauthorized object lookup must not leak object existence. Minimal health metadata may remain public.

## Initial demo limits (not ACG requirements)

10 steps, 2 transient retries, 60-second processing deadline excluding approval wait, 15-minute approval expiry, 8,000-character input, maximum 5 approved chunks/20,000 context characters. No file uploads/OCR initially. Workspace quotas and cancellation checked at transitions.

## Test data and evaluation

Build at least 24 synthetic bilingual business cases covering normal requests, restricted documents, insufficient evidence, conflicting versions and approval-required actions; add adversarial cases from ACCEPTANCE.md separately. Real-model evaluation uses held-out expert-reviewed cases, not development fixtures. Reported pilot quality/productivity percentages are hypotheses, not existing benchmarks.

## Demonstrator definition of done

S01–S06 pass applicable acceptance IDs with no skipped security tests, safe startup validation, repeatable runs and clearly labeled limitations. This does not close vendor, production, regulatory or commercial gates.
