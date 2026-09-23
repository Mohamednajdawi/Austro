# v0.3.0 — LangGraph IT workflow migration

The IT workflow now runs on LangGraph with SQLite checkpoints, named classification/retrieval/evidence nodes, a durable human-review interrupt, and a separate approval-enforced execution node. LangSmith tracing is disabled around graph operations. Existing v0.2 local model and browser functionality remains.

The restart test verifies a pending graph survives application recreation, resumes against a matching approved proposal and executes a sandbox note once. `/api/runs/{id}/graph` exposes authorized graph status, not raw checkpoint contents. Checkpoints are local plaintext and contain ticket/run snapshots; they require the same protection and retention policy as other local data.

This release does NOT complete the entire challenge description. Invoice and infrastructure workflows, enterprise connectors, enterprise identity/DLP, multiple production model providers, agent authoring, operational HA and production acceptance remain pending. No certification or perfect-score claim is made.

SQLite checkpointing supports this local pilot, not a claim of distributed recovery or production-scale reliability. Approval and action persistence remain separate from graph checkpoint commits; action execution is independently guarded against replay. The current resume API supports pending approval; generalized failed-node recovery is not yet exposed.

The push requested during implementation publishes this tested checkpoint of work, not the remainder of the earlier roadmap.
