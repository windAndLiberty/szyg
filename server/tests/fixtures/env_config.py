"""Environment config helpers — API key detection and availability checks."""

import os
import httpx
import pytest

def get_volcengine_api_key() -> str:
    """Read VOLCENGINE_API_KEY from environment. Skip test if not set."""
    key = os.environ.get("VOLCENGINE_API_KEY", "")
    if not key:
        pytest.skip("VOLCENGINE_API_KEY not set — skipping test that requires API access")
    return key

def get_ollama_base_url() -> str:
    """Ollama default address, overridable via environment variable."""
    return os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

def is_ollama_available() -> bool:
    """Check if local Ollama is running and responding."""
    try:
        r = httpx.get(f"{get_ollama_base_url()}/api/tags", timeout=5)
        return r.status_code == 200
    except Exception:
        return False

def require_ollama():
    """Skip test if Ollama is not available."""
    if not is_ollama_available():
        pytest.skip("Ollama not available at " + get_ollama_base_url())

def require_volcengine():
    """Skip test if Volcengine API key is not configured."""
    get_volcengine_api_key()  # calls pytest.skip internally
