# Research references

Reviewed 2026-09-23. Live documentation is not deployed-feature verification. Recheck release-specific details before adapters. Google queries returned JavaScript gates; findings rely on primary documentation.

## Challenge/security (preceding strategy research)

- https://www.ioeb-innovationsplattform.at/en/challenges/detail/secure-agentic-ai-in-the-enterprise-platform-for-controlled-and-secure-ai-agent-operations/
- https://www.ioeb-innovationsplattform.at/en/terms-of-use/
- https://www.ioeb-innovationsplattform.at/en/faq/
- https://www.austrocontrol.at/en/aviation_authority/safety/part-is
- https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai
- https://digital-strategy.ec.europa.eu/en/news/ai-omnibus-enters-force
- https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html
- https://cheatsheetseries.owasp.org/cheatsheets/RAG_Security_Cheat_Sheet.html
- https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices

## Platform readiness

- https://developer.watson-orchestrate.ibm.com/developer_edition/wxOde_setup.md — licensing/inference/hardware and Windows/Docker warning.
- https://developer.watson-orchestrate.ibm.com/developer_edition/wxOde_overview.md — local components, not production assurance.
- https://developer.watson-orchestrate.ibm.com/environment/onprem_compatibility.md — release compatibility, reviewed earlier.
- https://developer.watson-orchestrate.ibm.com/llm/managing_llm.md — provider/gateway warnings, reviewed earlier.
- https://learn.microsoft.com/en-us/microsoft-copilot-studio/admin-data-loss-prevention — connector governance, reviewed earlier.
- https://learn.microsoft.com/en-us/privacy/eudb/eu-data-boundary-learn — EU/EFTA and exceptions, reviewed earlier.

## Harness dependencies

- https://fastapi.tiangolo.com/tutorial/testing/ — TestClient/HTTPX/pytest.
- https://fastapi.tiangolo.com/virtual-environments/ — isolated environments.
- https://docs.pytest.org/en/stable/getting-started.html — collection/assertions/parametrization.
- https://docs.pydantic.dev/latest/concepts/strict_mode/ — strict schemas.
- https://www.python-httpx.org/ — TestClient dependency.
- https://pip.pypa.io/en/stable/cli/pip_freeze/ — installed-version snapshot, not universal lock solver.

## Dependency correction verified during preparation

- https://starlette.dev/testclient/ — Starlette now prefers HTTPX2; plain HTTPX emits a deprecation warning.
- https://pypi.org/pypi/httpx2/json — package identity/version/Python compatibility checked before installation.

Initial smoke-test collection failed because warnings are errors and Starlette 1.7.0 deprecated plain HTTPX. Replace the test dependency rather than suppressing the warning. No telemetry instrumentation was installed.
