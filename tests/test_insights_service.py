import json
from datetime import datetime, timezone

from szyg.insights_service import InsightsService


class FakeKnowledge:
    def stats(self):
        return {"total_docs": 2, "total_chunks": 8, "updated_at": "2026-07-19T08:00:00+00:00"}

    def search_sync(self, query, limit=4):
        return [{
            "document_id": "doc_1",
            "filename": "产品资料.md",
            "heading": "目标用户",
            "locator": "第2节",
            "content": "面向需要英语口语练习的儿童和家长。",
            "score": 0.91,
        }]


def write_rows(path, rows):
    path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")


def test_global_insights_use_real_internal_and_market_data(tmp_path):
    now = datetime.now(timezone.utc).isoformat()
    write_rows(tmp_path / "generation_history.json", [
        {"id": "g1", "type": "image", "title": "英语学习图", "adopted": True, "created_at": now},
        {"id": "g2", "type": "copy", "title": "口语练习文案", "adopted": False, "created_at": now},
    ])
    write_rows(tmp_path / "execution_runs.json", [
        {"id": "r1", "task_type": "publish_note", "status": "success", "platform": "xhs", "created_at": now},
        {"id": "r2", "task_type": "publish_note", "status": "failed", "platform": "douyin", "created_at": now},
    ])
    write_rows(tmp_path / "leads.json", [{"id": "l1", "grade": "A", "created_at": now}])
    write_rows(tmp_path / "conversions.json", [{"id": "c1", "created_at": now}])
    write_rows(tmp_path / "intelligence_reports.json", [{
        "id": "report_1",
        "title": "AI英语市场",
        "query": "AI英语学习机会",
        "market_gap": [{"topic": "口语陪练", "market_score": 88, "enterprise_coverage": 20, "gap": 68}],
        "actions": [{"title": "测试口语陪练选题", "description": "连续发布三条内容"}],
        "evidence": [{"id": "e1", "title": "市场样本", "source": "B站"}],
        "data_scope": {"relevant_samples": 12, "confidence": "medium", "source_health": [{"status": "success"}]},
        "created_at": now,
        "updated_at": now,
    }])

    result = InsightsService(tmp_path, FakeKnowledge()).overview(days=30)

    assert result["summary"]["published"] == 1
    assert result["summary"]["publish_success_rate"] == 50.0
    assert result["summary"]["leads"] == 1
    assert result["summary"]["conversions"] == 1
    assert result["summary"]["market_opportunities"] == 1
    assert result["market_gap"][0]["topic"] == "口语陪练"
    assert result["knowledge"]["references"][0]["source"] == "产品资料.md"
    assert any(item["id"] == "market-gap-0" for item in result["insights"])


def test_content_insights_expose_real_funnel_without_fake_platform_metrics(tmp_path):
    now = datetime.now(timezone.utc).isoformat()
    write_rows(tmp_path / "generation_history.json", [
        {"id": "g1", "type": "image", "title": "图片", "adopted": True, "created_at": now},
        {"id": "g2", "type": "copy", "title": "文案", "adopted": False, "created_at": now},
    ])
    write_rows(tmp_path / "execution_runs.json", [
        {"id": "r1", "task_type": "publish_note", "status": "success", "platform": "xhs", "created_at": now}
    ])

    result = InsightsService(tmp_path, FakeKnowledge()).content(days=30)

    assert result["summary"]["generated"] == 2
    assert result["summary"]["adopted"] == 1
    assert result["summary"]["published"] == 1
    assert result["funnel"][-1]["count"] == 1
    assert result["limitations"]
