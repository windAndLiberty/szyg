.PHONY: backend frontend app test kill

# ── szyg 开发命令 ────────────────────────────────────────
# 每个命令在独立终端运行

kill:
	@fuser -k 8000/tcp 2>/dev/null; fuser -k 5173/tcp 2>/dev/null; echo "Ports freed"

backend:
	@fuser -k 8000/tcp 2>/dev/null || true
	@echo "Starting backend on :8000..."
	export VOLCANO_ENGINE_API_KEY=$$(grep VOLCANO_ENGINE_API_KEY .env | cut -d= -f2) && \
	unset ALL_PROXY HTTP_PROXY HTTPS_PROXY all_proxy http_proxy https_proxy && \
	PYTHONPATH=server python3 -m uvicorn szyg.api.app:create_app --host 127.0.0.1 --port 8000 --factory --reload

frontend:
	@fuser -k 5173/tcp 2>/dev/null || true
	@echo "Starting frontend on :5173..."
	cd web && npx next dev -p 5173

app:
	@echo "Opening Chrome app window..."
	google-chrome-stable --app="http://127.0.0.1:5173" --window-size=1300,760 --new-window

test:
	@echo "Running unit tests..."
	export VOLCANO_ENGINE_API_KEY=$$(grep VOLCANO_ENGINE_API_KEY .env | cut -d= -f2) && \
	unset ALL_PROXY HTTP_PROXY HTTPS_PROXY all_proxy http_proxy https_proxy && \
	source .venv/bin/activate && PYTHONPATH=server pytest server/tests/ -v --tb=short
