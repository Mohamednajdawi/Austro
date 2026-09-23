# Control Room — local AI-agent pilot

**v0.4.0:** LangGraph now coordinates IT support, structured invoice review and infrastructure dependency-review workflows. Added reviewer-owned template versions, document extraction/publication, source search, heuristic content inspection, run monitoring, an OpenAI-compatible local model API and post-commit reconciliation. See [the current capability matrix](docs/PLATFORM_RELEASE.md). This is still a local pilot, not a fully implemented or certified ACG enterprise platform.

Working local application with real Qwen inference, a browser workspace and approval-gated sandbox ticket updates. Built for the ACG challenge investigation, not affiliated with or approved by ACG. This is a usable local pilot, NOT a production-certified enterprise platform.

Implemented: real model classification and evidence selection, verified verbatim source quotations, DE/EN interface, ticket creation, authorized source inspection, exact-action proposals, separate-person approval, rejection/cancellation, transactional execution, audit history and replay/concurrency protection. An approved action appends exactly one note to a local ticket. No production systems are connected.

See [challenge evidence](docs/CHALLENGE_EVIDENCE.md), [skill adoption](docs/SKILLS_ADOPTION.md), [backlog](docs/BACKLOG.md) and [readiness](docs/READINESS.md).

## Local verification (PowerShell)

```powershell
uv sync --locked
uv run --locked playwright install chromium
uv run --locked pytest -q
uv run --locked ruff check src tests
uv run --locked ruff format --check src tests
uv run --locked mypy src
```

`pyproject.toml` is the dependency/tooling source of truth; `uv.lock` replaces the preparation-stage requirements files. Source code follows `src/acg_agent_platform`. `make all` runs lint, formatting check, strict source typing and tests when Make is installed.

## Run locally (PowerShell)

```powershell
./start-local.ps1
```

Open **http://127.0.0.1:8765**. The launcher starts the already-provisioned `acg-local-ollama` container, seeds a separate sandbox database and starts the application. In a second terminal, issue session tokens:

```powershell
uv run --locked python -m acg_agent_platform token --principal alice --env-file local-model.env.example
uv run --locked python -m acg_agent_platform token --principal reviewer --env-file local-model.env.example
uv run --locked python -m acg_agent_platform token --principal bob --env-file local-model.env.example
uv run --locked python -m acg_agent_platform token --principal finance-reviewer --env-file local-model.env.example
```

Paste Alice's token into the UI. Select a ticket or create one, generate a draft, inspect sources and send it for approval. Disconnect, connect with the reviewer token, open Review queue, approve the exact action, then execute it. Return to the ticket to see the persisted note. Tokens expire after 15 minutes and are hashed in storage; the browser keeps them only in memory. Local CLI administration is trusted and can issue either identity, so this is NOT enterprise SSO or separation from the local machine owner. Seeding never restores revoked accounts.

Configuration is centralized; env files load only with `--env-file`. `local-model.env.example` selects Ollama and `runtime/local-pilot.sqlite3`. Without an env file the code defaults to fake mode for deterministic tests, visibly labeled TEST DOUBLE. Do not mistake that mode for live AI. Remote model addresses, cloud model names, telemetry and production writes are rejected. Trusted test/developer adapters are not an untrusted plugin sandbox.

### New workflows and controls

- **Invoice review:** connect as `bob`; expand Invoice review and submit the example. The €12,400 invoice is compared against the €10,000 local order/contract, producing a €2,400 deviation. Arithmetic uses Decimal, not an LLM. Use `finance-reviewer` to approve filing the review note. No payment/posting occurs. Invoice fields are structured, user-entered data; PDF extraction does NOT automatically populate or validate them.
- **Infrastructure:** connect as `alice`; analyze `ASSET-EDGE`. The local dependency graph includes `ASSET-APP`. Stale/missing records and safety-critical assets are flagged. A reviewer can approve filing the report; there is no infrastructure mutation or rollback tool.
- **Sources:** reviewers can publish reviewed text and retire sources. Content indicators force suspicious imports to restricted classification. Search filters by workspace, role and source type. Incident/log records are imported knowledge, not live integrations or automated root-cause diagnosis.
- **Documents:** extract text from digital PDF, UTF-8 TXT/MD/CSV/JSON/LOG and plain EML, then manually review and publish. Limits: 1 MB input, 20 PDF pages, 20,000 output characters, 10-second worker timeout. No OCR, Office parsing or malware scanning. The worker is process-isolated, not an OS security sandbox or hard memory limit; synthetic files only.
- **Configuration:** reviewers name/enable/disable three predefined templates and set the IT retrieval count. Every change creates a revision and invalidates earlier approval execution. This is a limited form-based configuration interface, not natural-language agent authoring or arbitrary graph/tool editing.
- **Monitoring:** own latest 100 completed/failed/blocked intake records, model-call counts and proposal status. No live progress stream, monetary cost meter, SIEM integration or HA monitoring.
- **Model API portability:** set `MODEL_PROVIDER=openai-compatible` to call `/v1/chat/completions` and `/v1/models` on the same configured loopback endpoint. Native Ollama remains available. Both paths were tested against the same local Qwen model: this is two API protocols, NOT two independent vendors or automatic cloud/local routing.
- **Recovery:** POST `/api/proposals/{id}/reconcile` repairs the final graph checkpoint when the independent action ledger proves the note already committed. It never retries an unknown remote action; generic mid-run retries and disaster recovery remain unimplemented.

Run `seed --env-file local-model.env.example` after upgrading to provision example business sources and the finance reviewer without overwriting existing records. Keep existing databases/checkpoints protected; source-schema changes may invalidate old fingerprints, requiring a fresh run.

### Provision the model on another machine

```powershell
docker run -d --name acg-local-ollama --cpus=4 --memory=6g -p 127.0.0.1:11435:11434 -e OLLAMA_NO_CLOUD=1 -e OLLAMA_NUM_PARALLEL=1 -v acg-ollama-models:/root/.ollama ollama/ollama@sha256:7ab595e4ead391f6818c7215297781282babe0701f6d9a9f8862ac591360a58b
docker exec acg-local-ollama ollama pull qwen2.5:1.5b
```

The model is about 986 MB, plus the runtime image. Qwen2.5-1.5B-Instruct's model card lists Apache-2.0 licensing. The installed model ID observed during validation was `65ec06548149`; tags can move. No GPU required for this small pilot. Downloads need internet; inference uses only the loopback service. The container still has outbound networking; this is not verified air-gap isolation.

### Live verification

```powershell
uv run --locked python tests/test_real_inference_manual.py
$env:ACG_TEST_REAL_MODEL = "1"
uv run --locked pytest tests/test_browser.py -q
Remove-Item Env:ACG_TEST_REAL_MODEL
```

These run actual English/German/account-support inference and Chromium generation → proposal → different reviewer → execution. Ordinary tests use fakes/mocked transport so they remain repeatable. The real model chooses passages; the server rejects fabricated quotes and assembles a cited note. This intentionally trades fluent free-form troubleshooting for verified evidence. It does not establish source truth, expert-quality reasoning or resistance to every prompt injection.

## Safety and scope

- Implemented API: tickets, sources, runs, model status, proposal/review/execute/cancel/reject. Business routes require bearer sessions. `/readiness` reports local-pilot readiness only when the configured local model is available; `production_ready` remains false.
- No company/ACG data, existing-project credentials or commercial entitlements assumed.
- Built-in policy enforces classification and length, NOT enterprise content-scanning DLP. No sensitive or real company data should be entered.
- Tests terminate their temporary servers. The dedicated model container can remain running for interactive use; stop it with `docker stop acg-local-ollama`. Stop an interactively launched app with Ctrl+C.
- No cloud purchase, signup, email or challenge submission performed. Git commits/pushes are made only at the user's request.
- Preserve the existing Docker installation; do not reset/purge other workloads.
- A supported enterprise operating model, real source/security connectors, enterprise identity, legal/security review, resilience and workload testing remain required before ACG deployment. No natural-language authoring, autonomous diagnostics, invoice OCR, production writes, certifications or 500-user claim.
- SQLite stores sandbox data in plaintext. Audit events and ticket mutation are atomic, not externally anchored or administrator-tamper-proof. Retention, encryption, append-only central audit and distributed recovery remain future work. Model calls have inactivity timeouts, output caps and one-call concurrency limits, not a guaranteed global wall-clock deadline.
- UI uses text-only rendering, restrictive CSP, same-origin mutations and no browser token persistence. No anonymous login or cookie authentication. Accessibility basics and mobile layout tested; no EN 301 549 certification.

## Documents

- [Implementation brief](docs/IMPLEMENTATION_BRIEF.md)
- [Backlog](docs/BACKLOG.md)
- [Acceptance matrix](docs/ACCEPTANCE.md)
- [Readiness and gates](docs/READINESS.md)
- [Moderator questions — not sent](docs/CLARIFICATION_REQUEST.md)
- [Sources](docs/SOURCES.md)
