@echo off
cd /d D:\szyg
set PYTHONPATH=D:\szyg\server
set SZYG_DATA_DIR=D:\szyg\data
D:\szyg\.venv\Scripts\python.exe -m uvicorn szyg.api.app:create_app --host 0.0.0.0 --port 8000 --factory
pause
