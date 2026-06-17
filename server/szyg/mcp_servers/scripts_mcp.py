#!/usr/bin/env python3
"""MCP Server: Sales Script Library — 销冠话术库。

挂载到 Hermes，提供话术模板查询和 AI 生成。
Hermes 可以结合 leads 评分结果，自动为不同客户生成个性化话术。
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from pathlib import Path
from szyg.mcp_server import MCPServer

server = MCPServer("szyg-scripts", "Sales script templates and AI-powered script generation")

SCRIPT_DB = Path(__file__).parent.parent.parent.parent / "data" / "scripts.json"


def _load_scripts() -> list[dict]:
    if not SCRIPT_DB.exists():
        return []
    with open(SCRIPT_DB, encoding="utf-8") as f:
        return json.load(f)


@server.tool("script_industries", "List all available industries for script templates")
def script_industries():
    scripts = _load_scripts()
    industries = sorted(set(s["industry"] for s in scripts))
    return {"industries": industries, "template_count": len(scripts)}


@server.tool("script_list", "List script templates filtered by industry and/or scenario")
def script_list(industry: str = "", scenario: str = "", search: str = ""):
    scripts = _load_scripts()
    if industry:
        scripts = [s for s in scripts if s["industry"] == industry]
    if scenario:
        scripts = [s for s in scripts if scenario.lower() in s["scenario"].lower()]
    if search:
        kw = search.lower()
        scripts = [s for s in scripts if kw in s["title"].lower() or
                   any(kw in k.lower() for k in s.get("trigger_keywords", []))]
    return [
        {"id": s["id"], "industry": s["industry"], "scenario": s["scenario"],
         "title": s["title"], "persona": s["persona"],
         "keywords": s.get("trigger_keywords", []),
         "tips": s.get("tips", [])}
        for s in scripts
    ]


@server.tool("script_generate", "Generate a personalized sales script for a specific scenario")
def script_generate(industry: str, scenario: str, product_info: str = "",
                    customer_context: str = ""):
    """根据行业、场景和产品信息生成填充后的话术。
    Hermes 可以将此结果用于自动回复或人工审核。
    """
    scripts = _load_scripts()
    matches = [s for s in scripts if s["industry"] == industry and
               scenario.lower() in s["scenario"].lower()]
    if not matches:
        matches = [s for s in scripts if s["industry"] == industry]
    if not matches:
        return {"error": f"No template for industry={industry}"}

    template = matches[0]
    filled = {}
    for key, text in template["template"].items():
        text = text.replace("[卖点1]", product_info[:50] if product_info else "核心优势")
        text = text.replace("[卖点2]", product_info[50:100] if len(product_info) > 50 else "品质保障")
        text = text.replace("[具体效果]", "客户满意度95%以上")
        filled[key] = text

    return {
        "template_id": template["id"],
        "title": template["title"],
        "persona": template["persona"],
        "steps": filled,
        "tips": template.get("tips", []),
    }


if __name__ == "__main__":
    server.run()
