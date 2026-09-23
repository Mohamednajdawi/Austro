---
name: acg-engineering
description: Apply selected mo_skills conventions to ACG control-demonstrator implementation and review.
---

# ACG engineering profile

Project-specific adaptation of guidance reviewed from https://github.com/Mohamednajdawi/mo_skills on 2026-09-23. See docs/SKILLS_ADOPTION.md for source URLs, exclusions and precedence.

1. Use `src/acg_agent_platform`, `pyproject.toml`, `uv.lock`, Ruff, strict mypy and pytest. Python 3.11 is retained for the verified host.
2. Keep schemas in models and behavior in services. Use small interfaces, dependency injection, single-line docstrings, enums for states, modern unions and no barrel exports.
3. Centralize validated configuration in pydantic-settings; use SecretStr for credentials and never log raw values or validation inputs.
4. Only the model gateway invokes the injected model adapter. Check complete input/context/output at each boundary. Fail closed on policy failures. Prompts are versioned resources; TOML is used here rather than YAML to avoid an unnecessary parser dependency.
5. No Redis caching until ACL/version/deletion semantics are implemented. No fixed commercial model names, Supabase, Stripe, Resend or external tracing required by generic examples.
6. Implement negative authorization tests before adding network integrations. Test through public APIs and model-adapter seams; distinguish fake-model tests from live evidence.
7. Defer React/frontend framework choice. Accessibility, visible focus, readable contrast and reduced motion take priority over decorative effects.
8. Never stage, commit, reset, force-push, email or submit unless explicitly authorized.
9. Report verified behaviors and remaining gates; never equate test passes with perfect jury scores or regulatory certification.
