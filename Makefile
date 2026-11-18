.PHONY: dev test lint smoke

dev:
	uv run uvicorn examiner.meridian.app:app --port 8001 --reload

test:
	uv run pytest -q

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run pyright

smoke:
	uv run examiner run --target http://localhost:8001 --pack smoke
