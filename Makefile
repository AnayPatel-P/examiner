.PHONY: dev test lint smoke api web web-test

dev:
	uv run uvicorn examiner.meridian.app:app --port 8001 --reload --env-file .env

test:
	uv run pytest -q

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run pyright

smoke:
	uv run examiner run --target http://localhost:8001 --pack smoke

api:
	uv run examiner serve --port 8002

web:
	npm --prefix web run dev

web-test:
	npm --prefix web test
	npm --prefix web run typecheck
