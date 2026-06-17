"""Script Templates — 单元测试。

测试销冠话术库的核心功能：模板加载、行业筛选、AI 话术生成。
"""

import json
import pytest
from pathlib import Path


SCRIPT_DB = Path(__file__).parent.parent.parent / "data" / "scripts.json"


# ── Template Loading ─────────────────────────────────────

class TestScriptTemplates:
    """话术模板加载与验证。"""

    @pytest.fixture(autouse=True)
    def load_templates(self):
        if not SCRIPT_DB.exists():
            pytest.skip("scripts.json not found")
        with open(SCRIPT_DB, encoding="utf-8") as f:
            self.templates = json.load(f)

    def test_templates_exist(self):
        """至少存在基本模板。"""
        assert len(self.templates) >= 4, f"Expected >=4 templates, got {len(self.templates)}"

    def test_all_have_required_fields(self):
        """每个模板必须有必需字段。"""
        required = ["id", "industry", "scenario", "title", "persona", "template", "tips"]
        for t in self.templates:
            for field in required:
                assert field in t, f"Missing field '{field}' in {t.get('id', 'unknown')}"

    def test_all_template_keys_are_strings(self):
        """模板样例的 key 必须是字符串。"""
        for t in self.templates:
            for key, value in t["template"].items():
                assert isinstance(key, str), f"Template key should be str"
                assert isinstance(value, str), f"Template value should be str"

    def test_industries_covered(self):
        """覆盖核心行业。"""
        industries = {t["industry"] for t in self.templates}
        expected = {"零售", "B2B", "本地服务", "教育", "健康"}
        for ind in expected:
            assert ind in industries, f"Missing industry: {ind}"

    def test_unique_ids(self):
        """ID 唯一。"""
        ids = [t["id"] for t in self.templates]
        assert len(ids) == len(set(ids)), "Template IDs must be unique"

    def test_filter_by_industry(self):
        """按行业筛选。"""
        retail = [t for t in self.templates if t["industry"] == "零售"]
        assert len(retail) >= 2
        for t in retail:
            assert t["industry"] == "零售"

    def test_search_by_keyword(self):
        """关键词搜索。"""
        keyword = "价格"
        matches = [
            t for t in self.templates
            if keyword in t["title"]
            or any(keyword in kw for kw in t.get("trigger_keywords", []))
        ]
        assert len(matches) >= 1, f"Should find templates matching '{keyword}'"

    def test_all_have_tips(self):
        """每个模板都有销售技巧提示。"""
        for t in self.templates:
            assert len(t["tips"]) >= 1, f"Template {t['id']} should have tips"


# ── Script Generation API ────────────────────────────────

class TestScriptGeneration:
    """话术生成 API 测试（无需真实 LLM）。"""

    def test_placeholder_filling(self):
        """占位符替换。"""
        template_text = "我们的产品核心优势是[卖点1]和[卖点2]"
        filled = template_text.replace("[卖点1]", "快速交付").replace("[卖点2]", "优质服务")
        assert "快速交付" in filled
        assert "优质服务" in filled
        assert "[卖点1]" not in filled

    def test_all_template_steps_present(self):
        """每个模板都有完整的销售步骤。"""
        if not SCRIPT_DB.exists():
            pytest.skip("scripts.json not found")
        with open(SCRIPT_DB, encoding="utf-8") as f:
            templates = json.load(f)
        for t in templates:
            keys = list(t["template"].keys())
            # At minimum: greeting + cta
            assert len(keys) >= 3, f"Template {t['id']} should have >=3 steps, got {len(keys)}"
            has_opening = any("greeting" in k.lower() or "acknowledge" in k.lower() for k in keys)
            has_closing = any(
                kw in k.lower() for kw in ["cta", "close", "confirm"] for k in keys
            )
            assert has_opening, f"Template {t['id']} needs opening step"
            assert has_closing, f"Template {t['id']} needs CTA step"
