.PHONY: all lint typecheck test fmt
all: lint typecheck test
lint:
	uv run --locked ruff check src tests
	uv run --locked ruff format --check src tests
typecheck:
	uv run --locked mypy src
test:
	uv run --locked pytest -q
fmt:
	uv run --locked ruff format src tests
