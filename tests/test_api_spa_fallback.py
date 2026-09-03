import httpx
import pytest

from szyg.api.app import create_app


@pytest.mark.asyncio
async def test_unknown_api_path_is_not_served_by_spa(tmp_path, monkeypatch):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>SPA</title>", encoding="utf-8")
    monkeypatch.setenv("SZYG_FRONTEND_DIST", str(dist))

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/route-that-does-not-exist")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {"detail": "API endpoint not found"}
