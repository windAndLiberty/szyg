import os
from pathlib import Path

DB_PATH = Path(__file__).parent / "control-test.db"
DB_PATH.unlink(missing_ok=True)
os.environ.update({
    "CONTROL_DATABASE_URL": f"sqlite:///{DB_PATH.as_posix()}",
    "CONTROL_JWT_SECRET": "test-secret-that-is-longer-than-thirty-two-characters",
    "CONTROL_BOOTSTRAP_ADMIN_EMAIL": "admin@example.com",
    "CONTROL_BOOTSTRAP_ADMIN_PASSWORD": "correct-horse-battery-staple",
    "CONTROL_ENVIRONMENT": "test",
})
