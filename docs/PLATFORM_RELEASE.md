# v0.4.0 capability and evidence matrix

This is the current release status and supersedes older planning/status sections. It does NOT claim the entire requested enterprise description is implemented. The software is a testable local LangGraph pilot with controlled review workflows; enterprise access and production assurances remain separate deliverables.

## Implemented in this release

| Area | Delivered behavior | Limits |
| --- | --- | --- |
| LangGraph orchestration | IT classification/retrieval/evidence nodes; business specialist branch; durable review interrupt and approved execution | Bounded predefined graphs, not arbitrary autonomous multi-agent teams |
| Invoice workflow | Typed invoice fields compared with local order, supplier and contract; Decimal arithmetic; discrepancies, bank mismatch and local duplicate hints; cost-center suggestion | Human-entered invoice fields; no automatic invoice extraction/ERP/payment; reports mostly English with localized heading |
| Infrastructure workflow | Reverse dependency traversal in authorized asset records; stale dates, incomplete references and safety flags; review package | No live topology integration, complete graph guarantee, production change or rollback |
| Human control | Exact action digest, source/target fingerprints, expiry, different reviewer, cancellation/rejection, replay/concurrency guards | Only appends a sandbox note; local administrator can issue both identities |
| Template lifecycle | Reviewer-only names, enablement and retrieval limits; stored immutable revision rows; changes invalidate prior action execution | Three templates only; no natural-language or arbitrary code/tool authoring |
| Source ingestion | Reviewer publication and retirement; source types for documents/incidents/logs/email/wiki/business | Human-curated local data, not connected company systems; retirement is not physical erasure |
| Document extraction | Digital PDF, UTF-8 text formats, plain EML; size/page/time limits; no automatic publication | No OCR/Office/malware scan; parser process has no OS sandbox or hard RAM cap |
| Search | Permission-filtered title/content substring search by source type | Not semantic search, historical incident resolution or automated log correlation |
| Model flexibility | Native Ollama and OpenAI-compatible local HTTP API, same schemas and grounding checks | Both validated with local Qwen, not separate vendors; external destinations remain blocked |
| Content inspection | Classification/length gates plus email/IBAN/credential/private-key heuristics; policy preview | Not exhaustive PII detection, certified DLP, external model routing or SIEM integration |
| Injection judge | Local model screens the ticket and each cited source separately before review; enum-only verdicts are stored on the run, bound into the approval digest and shown to the reviewer; flagged approvals need confirmation | Advisory only, never blocks or approves; small model can miss or be manipulated; detection rate unmeasured; items beyond 1 + MAX_SOURCES reported unscreened |
| Monitoring | Owner-scoped run metadata, model-call counts and proposal states | No cross-user executive dashboard, billing, token usage or live streaming |
| Recovery | Resume after human review; reconcile committed action when final checkpoint fails | Not distributed HA or arbitrary failed-node recovery |
| UI | Existing DE/EN IT/review UI, bilingual-labeled business forms, sources/configuration/search/monitoring | New forms/report messages not fully localized; accessibility certification absent |

## Architecture and trust boundaries

- Request identity remains server-resolved from opaque expiring sessions.
- LangGraph controls execution order; it cannot bypass the independent authorization/approval service.
- Business calculations are deterministic tools. No LLM is trusted for arithmetic, financial authorization or infrastructure topology completeness.
- Approved effect remains `append_sandbox_note` for all workflows. Invoice review does not post/pay; infrastructure review does not deploy.
- Source changes, classification, audience, requester/reviewer status, template revision and target content are checked before action mutation.
- SQLite action update and action event are atomic; graph checkpoints commit separately with a narrow reconciliation path.
- LangSmith tracing stays disabled; no external inference is enabled. Checkpoints and local data are plaintext and require host protection.

## Remaining work from the user's full description

1. Enterprise identity/SSO and delegated source permissions.
2. Real Microsoft 365, ticket-system, ERP, infrastructure, monitoring, DLP and SIEM connectors.
3. Invoice OCR/field extraction and technical/commercial dual-stage authorization.
4. Real incident/log correlation and supported diagnostic recommendations.
5. Configurable multi-agent/tool authoring, natural-language configuration and governed tool registration.
6. Independent provider integrations, approved regional hosting, content-based provider routing and tested fallback.
7. Tamper-resistant central audit, retention/erasure, encryption and production secrets management.
8. Distributed recovery, scheduling, quotas, full workload sizing and 500-user/HA validation.
9. EN 301 549/WCAG audit, complete localization, DPIA/legal classification and Part-IS integration.
10. Supplier support arrangements, references, measured cost/benefit, certifications where applicable.

These are not marked done by mocks, documentation, local tests or installation of LangGraph. Some need further engineering; others require user/ACG access, decisions, contracts or independent assessment.

## Verification commands

### Observed release verification

- 102 regression tests passed twice (26.77s and 24.31s).
- Strict mypy passed for 21 source files; Ruff lint/format and dependency lock checks passed.
- Real English/German VPN and account-support inference passed through both native Ollama and the OpenAI-compatible local endpoint.
- Real-model Chromium test passed (11.10s), including approval/execution and the infrastructure/invoice form outputs.
- Built v0.4.0 source archive and wheel. No enterprise credentials, cloud inference or production actions were used.

`uv run --locked pytest -q` includes deterministic graph, financial, permission, parsing, configuration and browser checks. `uv run --locked python tests/test_real_inference_manual.py` uses the actual local model; set `ACG_TEST_COMPATIBLE=1` to verify the compatible API path. `ACG_TEST_REAL_MODEL=1 uv run --locked pytest tests/test_browser.py -q` runs the browser-to-real-model approval workflow. Run Ruff, strict mypy and `uv build` before release.

## Research

- https://docs.langchain.com/oss/python/langgraph/graph-api
- https://docs.langchain.com/oss/python/langgraph/interrupts
- https://pypdf.readthedocs.io/en/stable/user/extract-text.html
- https://fastapi.tiangolo.com/tutorial/request-files/
- https://platform.openai.com/docs/api-reference/chat/create

Google verification searches were attempted but returned a JavaScript gate. Ollama compatibility documentation endpoints were unavailable; the published Chat Completions contract was used and behavior verified against the actual local endpoint. No external AI credentials were required.
