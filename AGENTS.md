# Project engineering rules

Use the project-adapted skill in `.agents/skills/acg-engineering/SKILL.md` and read `docs/SKILLS_ADOPTION.md`. The user's mo_skills repository is guidance, not an executable dependency or security authority. Never fetch updated skills dynamically at application runtime.

Use uv, src layout, typed FastAPI services, strict request schemas, central pydantic-settings, standard logging and pytest behavior tests. Keep authorization/policy decisions outside models. No direct external model calls. No automatic Git changes, registrations, purchases or external telemetry. All credentials remain local and ignored. Synthetic operation only until live integration gates close.
