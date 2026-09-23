# v0.2.0 — working local pilot

This supersedes the earlier read-only/fake-only status statements in planning documents. The overall enterprise challenge roadmap is not complete.

## Observed live evidence

- Official Ollama image installed by immutable digest; separate `acg-local-ollama` container, 4 CPUs/6 GB cap, loopback port 11435, dedicated volume.
- Real qwen2.5:1.5b classification verified against a VPN ticket.
- Actual Chromium workflow passed: Alice creates a proposal from model-backed draft; different reviewer approves exact SHA-256-bound action; separate execution writes exactly one sandbox note; replay blocked.
- Actual English/German VPN and account-support checks passed after grounding correction.
- Free-form small-model drafting initially invented unsupported instructions. Replaced with strict source-ID/quote selection and exact substring verification. Invented evidence now fails instead of becoming an approvable note.
- Responsive German UI tested at 390px width; no JavaScript errors or browser token persistence in the end-to-end test.

## Security delivered

## Final verification and running instance

- 77 regression tests passed twice (12.72s and 13.09s).
- Explicit real-model Chromium workflow passed again (6.25s).
- Strict mypy passed for 14 source files; Ruff lint/format and uv lock check passed.
- Built v0.2.0 source archive and wheel under dist/.
- Interactive app started at http://127.0.0.1:8765 with PID 403472 for this session. GET / returned 200; GET /readiness returned 200, agent_workflow_ready=true and production_ready=false.
- Model container: acg-local-ollama, API bound to 127.0.0.1:11435. No other containers modified.
- Stop this recorded app instance using PowerShell `Stop-Process -Id 403472` after confirming the PID still belongs to this application (PIDs can be reused). Stop the model with `docker stop acg-local-ollama`. For subsequent foreground launches use start-local.ps1 and Ctrl+C.

## Approval controls

Action binds requester/workspace, target content fingerprint/version, full note, source fingerprints, policy version and expiry. A different active reviewer must approve. Execution rechecks active requester/reviewer, permissions, source content, classification, destination audience, target and digest inside a SQLite BEGIN IMMEDIATE transaction. Ticket mutation and execution event commit together. Cancellation/rejection/replay/concurrent execution/expired approval and changed source are tested.

## Limits

Local administration can issue both users' tokens; enterprise identity remains missing. Only sandbox note appending is an executable tool. No real ACG source/security integration, no vendor support arrangement, no high availability, no externally immutable audit, no no-code agent authoring. Local inference is real; enterprise readiness and perfect jury scores are not claimed. The model is small and the corpus is tiny; live test success is not a quality benchmark.

## Sources consulted

- https://hub.docker.com/r/ollama/ollama
- https://raw.githubusercontent.com/ollama/ollama/main/docs/api.md
- https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct
- https://playwright.dev/python/docs/intro
- https://pydantic.dev/docs/httpx2/advanced/timeouts/

Google queries were attempted; direct Ollama documentation was unreachable, so upstream API markdown was used. Existing containers and credentials were not modified. No public deployment, commercial purchase, challenge submission or Git commit performed.
