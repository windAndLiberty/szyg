"""Acceptance test fixtures."""

import sys
from pathlib import Path

# Ensure project root (parent of tests/) is on sys.path so `szyg` is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from httpx import ASGITransport, AsyncClient

from szyg.api.app import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
