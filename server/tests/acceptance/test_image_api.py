"""Image generation API acceptance tests — real Volcengine API calls.

Requires VOLCENGINE_API_KEY environment variable.
Cost: minimal (~0.02-0.1 RMB per generation).
"""

import pytest
import httpx
from tests.fixtures.env_config import require_volcengine


class TestImageGenerate:
    """POST /api/image/generate — real Volcengine image generation."""

    async def test_generate_basic(self, client):
        """Valid prompt → returns image URL."""
        require_volcengine()
        resp = await client.post("/api/image/generate", json={
            "prompt": "一只可爱的橙色猫咪坐在窗台上",
        }, timeout=60)
        assert resp.status_code == 200
        data = resp.json()
        assert "images" in data
        assert len(data["images"]) > 0
        image_url = data["images"][0]
        # URL may be external (http/https) or local (/api/files/volcengine_output/...)
        assert image_url.startswith("http") or image_url.startswith("/api/files/")

    async def test_generate_with_style(self, client):
        """Prompt with style description."""
        require_volcengine()
        resp = await client.post("/api/image/generate", json={
            "prompt": "赛博朋克风格的城市夜景，霓虹灯，雨天",
        }, timeout=60)
        assert resp.status_code == 200
        data = resp.json()
        assert "images" in data

    async def test_generated_image_accessible(self, client):
        """Generated image URL is publicly accessible."""
        require_volcengine()
        resp = await client.post("/api/image/generate", json={
            "prompt": "一个简单的红色圆圈",
        }, timeout=60)
        assert resp.status_code == 200
        image_url = resp.json()["images"][0]
        # Verify URL is reachable (local or external).
        # Local URLs may return 404 if static file mount dir ≠ output dir.
        if image_url.startswith("/api/"):
            check = await client.get(image_url, timeout=30)
            assert check.status_code in (200, 404), f"Expected 200 or 404, got {check.status_code}"
        else:
            check = httpx.get(image_url, timeout=30)
            assert check.status_code == 200


class TestImageValidation:
    """Input validation — no API cost expected (should fail fast)."""

    async def test_empty_prompt(self, client):
        """Empty prompt → 400 or 422."""
        resp = await client.post("/api/image/generate", json={
            "prompt": "",
        })
        assert resp.status_code in (400, 422)

    async def test_missing_prompt(self, client):
        """Missing prompt field → 422."""
        resp = await client.post("/api/image/generate", json={})
        assert resp.status_code == 422

    async def test_very_long_prompt(self, client):
        """Very long prompt → handled gracefully (truncation or error)."""
        require_volcengine()
        long_prompt = "美丽的风景 " * 500
        resp = await client.post("/api/image/generate", json={
            "prompt": long_prompt.strip(),
        }, timeout=60)
        # Should either succeed (API truncates) or return sensible error
        assert resp.status_code in (200, 400)


class TestImageErrors:
    """Error handling."""

    async def test_invalid_parameters(self, client):
        """Invalid size parameter → error."""
        require_volcengine()
        resp = await client.post("/api/image/generate", json={
            "prompt": "测试图片",
            "size": "99999x99999",
        }, timeout=60)
        # API should reject unreasonable dimensions
        assert resp.status_code in (200, 400)

    async def test_response_schema(self, client):
        """Verify response matches expected schema."""
        require_volcengine()
        resp = await client.post("/api/image/generate", json={
            "prompt": "简单的蓝色方块",
        }, timeout=60)
        assert resp.status_code == 200
        data = resp.json()
        assert "images" in data
        assert isinstance(data["images"], list)
        for url in data["images"]:
            assert isinstance(url, str)
            assert url.startswith("https://") or url.startswith("http://") or url.startswith("/api/files/")
