.PHONY: setup dev demo check

setup:
	uv sync

dev:
	uv run uvicorn app.main:app --host 127.0.0.1 --port 8000

demo:
	uv run pytest -q

check:
	uv run pytest -q
