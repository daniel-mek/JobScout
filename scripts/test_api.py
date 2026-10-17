"""Start an isolated API for browser tests; never touches the configured development database."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
folder = Path(tempfile.mkdtemp(prefix="applyos-e2e-"))
os.chdir(root)
os.environ.update(
    DATABASE_URL=f"sqlite:///{folder}/test.db",
    STORAGE_PATH=str(folder / "files"),
    WEB_ORIGIN="http://localhost:3000",
    ENVIRONMENT="test",
    COOKIE_SECURE="false",
)
subprocess.run([sys.executable, "-m", "alembic", "-c", "apps/api/alembic.ini", "upgrade", "head"], check=True)
os.execv(
    sys.executable,
    [sys.executable, "-m", "uvicorn", "apps.api.applyos.main:app", "--host", "127.0.0.1", "--port", "8000"],
)
