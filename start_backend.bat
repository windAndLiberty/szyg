@echo off
set PYTHONPATH=D:\szyg\server
D:\szyg\.venv\Scripts\python.exe -m uvicorn szyg.api.app:create_app --host 127.0.0.1 --port 8000 --factory
