# Challenge criteria and implementation evidence

**Authoritative current matrix:** [v0.4.0 platform release](PLATFORM_RELEASE.md). Sections below describe earlier milestones. The release now includes local invoice/infrastructure review, document extraction, bounded template configuration and two local model API protocols. It still does not satisfy every enterprise requirement, and no perfect score is claimed.

## Current release: v0.2.0

Working local AI pilot now delivered: actual Qwen classification and source-quote selection; server-verified evidence; browser ticket/source/review workspace; exact digest-bound separate-person approval; cancellation/rejection; atomic note append plus audit event; replay/concurrency protection. English/German live checks and a complete real-model Chromium flow passed. See [current release evidence](LOCAL_PILOT_RELEASE.md) and README for usage. The v0.1 matrix below is retained as historical context, not current feature status. Enterprise connectors, IdP, DLP, no-code authoring, HA, scale, certification and commercial readiness remain gaps.

Challenge page rechecked 2026-09-23. It lists core requirements and desirable features but exposes no verified numerical score weights. This is a market exploration, not a guaranteed contract award. A perfect score cannot be promised or calculated. The strongest response links every claim to reproducible evidence and labels gaps.

## What improves evaluation

| Evaluation area inferred from published requirements | Evidence required for strongest credible response | Current implementation | Remaining gap |
| --- | --- | --- | --- |
| Data security and policy before AI processing | Observe forbidden payloads never reaching model endpoints; cover every intermediary | Model-spy tests; classification and size checked before/after both calls | Content DLP, actual external endpoints, OCR/embedding paths and egress controls |
| Roles and organizational governance | Different users receive only authorized data; revocation propagates | Opaque expiring sessions, two workspaces, source roles, per-request and saved-run checks | Enterprise IdP, delegated scopes, richer ABAC, reviews of concurrent access changes |
| Human control | Exact action preview; wrong/expired/replayed approval cannot execute | Draft-only run, strict schema rejects injected authority fields; no executable business actions | S04 approvals, separation of duties and atomic execution; do NOT count this as complete |
| Multi-agent workflows | Useful cross-system sequence with inspectable state and delegation | Two deterministic fake stages plus authorized retrieval | Real agent orchestration, supported platform, durable pause/resume/cancel |
| Model choice | Two approved providers with equivalent control enforcement | Replaceable adapter and alternate fake behavior in tests | Real providers, geography, cost and quality comparison |
| Integration | Live sandbox workflow across enterprise systems and security tools | Typed local source/model/policy boundaries and REST API | ACG ticket/document/identity/DLP/SIEM interfaces |
| Traceability | Full decision/action chain with source and configuration versions | Persisted owner-scoped run, source versions, model/policy/workflow IDs, timestamps and outcomes | Incremental/denied-request auditing, trusted anchors, retention, sensitive-data handling |
| Practical usefulness | Measured handling-time/quality improvement on held-out German/English cases | Bilingual templated draft and missing-evidence fallback | Real model evaluation, domain review and business baseline |
| Enterprise operating maturity | Supported release, recovery, scalable hosting and accountable supplier | uv lock, typed package, repeatable tests, real loopback smoke test | HA, 500-user sizing, supplier support, security assessment, references |
| Cost transparency and portability | Three-year TCO, per-workflow costs, scale/exit options | Prior strategy provides illustrative model only | Quotes, measured consumption, business-owner approval |
| Accessibility and authoring | Accessible DE/EN user and authoring interfaces | None; API slice only | EN 301 549/WCAG testing and governed no-code authoring |
| GDPR/AI Act/Part-IS | Documented intended use, data flows, role allocation and accepted evidence | Synthetic-only scope and explicit live gates | Legal/security/operational assessments; no certification claim |

## Verified release scope

v0.1.0: secure synthetic ticket read and review-only draft path. No real model or external service calls. No unattended ticket, account, infrastructure or payment mutation. Fake classifier recognizes a VPN keyword; fake drafter returns a localized template. It is a test instrument, not a production-quality assistant.

Tests: `test_settings.py`, `test_access.py`, `test_workflow.py`, `test_hardening.py`, `test_runtime.py`, plus scaffold/preparation checks. Run `uv run --locked pytest -q`; run Ruff and mypy from README. The real-server test terminates its temporary process.

## Highest-priority next evidence

1. Bind human approval to immutable action parameters, source/target versions, authorized approver and expiry; prove replay/concurrency safety.
2. Integrate the selected supported platform and one approved sandbox connector without bypassing controls.
3. Add an approved real model and independent red-team tests; evaluate DE/EN output quality.
4. Add an accessible evidence/approval UI, full lifecycle controls and operational recovery.
5. Obtain deployment-specific legal/security evidence, credible references and measured commercial assumptions.

## Known limitations and nonclaims

No full vendor platform, no approval implementation, no real DLP, no production identity, no threat-proof prompt injection protection, no real model-quality evidence, no distributed recovery, no load/availability claims, no audited accessibility, no immutable audit store. Source scanning currently loads local JSON rows and filters before model use; this is not a production search/index design. The prompt profile is TOML, not copied upstream YAML. Injection of adapters is for trusted developer/test code, not adversarial plugins. A source update occurring between separate checks is not made transactionally atomic across external systems.

## Sources

- https://www.ioeb-innovationsplattform.at/en/challenges/detail/secure-agentic-ai-in-the-enterprise-platform-for-controlled-and-secure-ai-agent-operations/
- https://github.com/Mohamednajdawi/mo_skills
- https://docs.astral.sh/uv/concepts/projects/config/
- https://docs.astral.sh/uv/concepts/build-backend/
- https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- https://fastapi.tiangolo.com/reference/security/
- https://docs.astral.sh/ruff/configuration/
- https://mypy.readthedocs.io/en/stable/getting_started.html
- https://docs.python.org/3.11/library/sqlite3.html
