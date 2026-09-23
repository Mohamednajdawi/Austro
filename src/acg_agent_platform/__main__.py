"""Local demo administration and loopback server; never a public login route."""

import argparse
import logging
import sys
from pathlib import Path

import uvicorn

from acg_agent_platform.config import Settings
from acg_agent_platform.main import create_app
from acg_agent_platform.services.store import Store


def main() -> None:
    parser = argparse.ArgumentParser(description="Synthetic control demonstrator only")
    parser.add_argument("command", choices=("seed", "token", "serve"))
    parser.add_argument(
        "--principal",
        choices=("alice", "reviewer", "bob", "finance-reviewer"),
        default="alice",
    )
    parser.add_argument("--env-file", type=Path)
    args = parser.parse_args()
    settings = Settings(_env_file=args.env_file)
    logging.basicConfig(level=logging.INFO)
    if args.command == "serve":
        uvicorn.run(
            create_app(settings),
            host=settings.host,
            port=settings.port,
            access_log=False,
            proxy_headers=False,
        )
        return
    store = Store(settings.database_path)
    store.initialize()
    if args.command == "seed":
        store.seed_demo()
        store.add_knowledge_examples()
        store.seed_business_examples()
        logging.getLogger(__name__).info("Synthetic fixtures ready")
    else:
        # Intentional local credential output, never a logging sink.
        sys.stdout.write(
            store.issue_session(args.principal, settings.session_seconds) + "\n"
        )


if __name__ == "__main__":
    main()
