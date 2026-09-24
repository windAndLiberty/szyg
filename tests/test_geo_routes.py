from fastapi import FastAPI
from fastapi.testclient import TestClient

import szyg.api.geo_routes as geo_routes


class FakeGeoService:
    def get_profile(self):
        return {"product_name": "领鹿", "website": "https://example.com"}

    def overview(self, days):
        return {
            "days": days,
            "valid_sample_count": 2,
            "mention_rate": 50.0,
            "providers": [],
        }

    def get_questions(self):
        return ["推荐几款数字员工"]

    def list_question_details(self):
        return [{"id": "q1", "text": "推荐几款数字员工", "source": "manual"}]

    def create_audit(self, *_args, **_kwargs):
        return {"id": "geo-test", "status": "queued", "total": 2}

    def cancel_audit(self, audit_id):
        return {"id": audit_id, "status": "failed", "error": "你已停止本次浏览器检测"}


def test_geo_overview_is_json_and_legacy_audit_request_remains_supported(monkeypatch):
    service = FakeGeoService()
    monkeypatch.setattr(geo_routes, "get_geo_service", lambda: service)
    app = FastAPI()
    app.include_router(geo_routes.router)

    with TestClient(app) as client:
        overview = client.get("/api/geo/overview?days=30")
        audit = client.post("/api/geo/audits", json={
            "provider_ids": ["doubao"],
            "questions": ["推荐几款数字员工"],
            "sample_count": 2,
        })
        cancelled = client.post("/api/geo/audits/geo-test/cancel")

    assert overview.status_code == 200
    assert overview.headers["content-type"].startswith("application/json")
    assert overview.json()["valid_sample_count"] == 2
    assert audit.status_code == 202
    assert audit.json()["status"] == "queued"
    assert cancelled.status_code == 200
    assert cancelled.json()["error"] == "你已停止本次浏览器检测"
