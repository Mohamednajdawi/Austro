# Readiness and external gates

Prepared 2026-09-23. No platform purchase, ACG approval or submitting-company qualification is assumed.

## Observed environment

Python 3.11.9; Node 24.4.1; npm 11.4.2; Git 2.45.1.windows.1. Docker Desktop engine responds (29.7.2), Compose 5.3.1. No existing projects/credentials were inspected beyond parent directory listings. Workspace: `C:\Users\INT100313\apps\acg-agent-platform`.

## Levels

| Level | Status |
| --- | --- |
| Synthetic read-and-draft implementation | Implemented and tested; S01 done, portions of S02/S03 done |
| Working local AI pilot | Implemented: real Qwen inference, browser UI, separate reviewer approval and atomic sandbox note execution |
| Supported challenge solution | Not ready; platform selection/entitlement/integration required |
| ACG sandbox | Not ready; system access and policy decisions required |
| Production | Not ready; legal/security/operational/business acceptance required |

## External gates

| ID | Needed | Owner | Timing |
| --- | --- | --- | --- |
| G01 | Submitting company, product/IP, team, authorized project/data use | User/business owner | Before company/product claims or live use of employer resources |
| G02 | Supported platform selection, license/tenant and support commitment | User + vendor | Before S07; no purchase assumed |
| G03 | Approved hosting and all data-flow geographies | User/hosting/security | Before external processing |
| G04 | Model endpoint, terms, allowed data and authorized credentials | User + provider/security | Before real inference; never paste secrets into chat |
| G05 | Named source systems, sandbox APIs/schemas/rate limits/permissions | ACG system owners | Before real connectors |
| G06 | IdP/DLP/SIEM endpoints and test/service identities | ACG security/IT | Before enterprise integration claims |
| G07 | Intended use, legal classification, DPA/DPIA/retention decisions | ACG legal/DPO | Before personal/sensitive data |
| G08 | Approved action/approver catalog and separation rules | ACG business/security | Before real changes |
| G09 | Workloads, latency, SLO/RTO/RPO, accessibility scope and budget | ACG business/platform | Before production sizing/commitments |
| G10 | Business baseline, evaluation data, pilot acceptance and procurement agreement | ACG + supplier | Before pilot |

These do not block S01 using synthetic fixtures. Mock substitutes do not close them.

## IBM installation finding

Current Developer Edition setup requires license/inference access and warns Windows users with existing Docker to remove it before installing its managed environment. We will NOT remove Docker, purge containers, reset vendor tools, accept commercial terms or obtain a trial without authorization. Recommended: approved remote tenant or dedicated clean machine with vendor confirmation. Full IBM hardware requirements have not been verified and installation was not attempted.

## Assumptions

IT support first, infrastructure drafting second, invoice template later. No production/safety-critical/payment actions. Unknown systems use typed test adapters, not guessed vendors. Pricing in the strategy is illustrative, not a budget or purchase approval.

## Verification

Preparation originally passed 18 checks. Implementation has migrated to uv, src layout, pydantic-settings, Ruff and strict mypy, using the selected mo_skills guidance. `uv.lock` is now authoritative; old requirements files were removed. No global Python/Docker settings were changed.

Observed implementation verification: 56 tests passed, including an actual temporary Uvicorn loopback server with authenticated draft request. Ruff passes and strict mypy reports no issues in 11 source files. Warnings remain errors. Tests cover classification enforcement, role/workspace isolation, expiration/disablement, source revocation/reclassification, malformed output, policy outages and failure to persist evidence. They do not test real AI, vendor platform, enterprise DLP or production integrations.

v0.2.0 supersedes the preceding v0.1 verification: real local inference, grounded evidence selection, approval/execute/reject/cancel, transaction rollback, concurrency and browser flow are implemented and tested. See LOCAL_PILOT_RELEASE.md. G04 is satisfied for synthetic local Qwen use, not for ACG/company data or external providers. Enterprise gates otherwise remain open. Next: enterprise identity/connectors, durable workflow operations, richer curated knowledge and independent security/quality evaluation. No perfect-score or compliance claim is justified.
