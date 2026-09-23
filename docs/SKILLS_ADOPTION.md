# Selected mo_skills integration

Reviewed six public SKILL.md files on 2026-09-23. Integrated a project-scoped adaptation in `.agents/skills/acg-engineering/SKILL.md`, discoverable through AGENTS.md; no upstream scripts were executed or global skills changed. Public source references below are moving main-branch references, not a pinned upstream snapshot. Do not claim a vendored or byte-identical copy.

| Upstream skill | Adopt | Adapt/defer |
| --- | --- | --- |
| python-modern-structure | uv, src layout, pyproject, Ruff, strict mypy, validated settings | Retain tested Python 3.11; no automatic Git hooks; avoid empty utility folders |
| python_backend | FastAPI/Pydantic, SOLID seams, enums, SecretStr, logging, short docstrings | No Supabase, Stripe, Resend, Langfuse or LangChain dependency without need; no barrel exports (modern-structure takes precedence) |
| backend-llm-integration | One model-service boundary, versioned prompts, structured results | TOML resource instead of YAML; no fixed model choice; no cache without permission checks; no permissive security-field defaults |
| git_workflow | Conventional Commits when requested | No automatic branching/commits/resets/squashing/force-push; project has no assumed Test branch |
| frontend | Separation, strict types, localized strings | Frontend implementation deferred; do not impose cloud auth/payments |
| ux_ui_pro_max | Focus/active states, responsive layout, generous targets | Contrast, clarity and reduced motion override glassmorphism/mandatory animation |

## Sources actually read

- https://raw.githubusercontent.com/Mohamednajdawi/mo_skills/main/python-modern-structure/SKILL.md
- https://raw.githubusercontent.com/Mohamednajdawi/mo_skills/main/python_backend/SKILL.md
- https://raw.githubusercontent.com/Mohamednajdawi/mo_skills/main/backend-llm-prompt%20/SKILL.md
- https://raw.githubusercontent.com/Mohamednajdawi/mo_skills/main/git_workflow/SKILL.md
- https://raw.githubusercontent.com/Mohamednajdawi/mo_skills/main/frontend/SKILL.md
- https://raw.githubusercontent.com/Mohamednajdawi/mo_skills/main/ux_ui_pro_max/SKILL.md

Upstream local `file:///d:/...` examples are author-machine paths, not available files. GitHub CLI was unavailable; public webfetch fallback used. The repository landing page did not show a license; this profile summarizes project decisions, rather than republishing the full upstream skill corpus.
