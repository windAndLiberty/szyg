"""Sales Script API — 销冠话术库。

对标: 销氪AIsales 话术模板系统
"""

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/scripts", tags=["scripts"])

SCRIPT_DB = Path(__file__).parent.parent.parent.parent / "data" / "scripts.json"


def _load_scripts() -> list[dict]:
    if not SCRIPT_DB.exists():
        return []
    with open(SCRIPT_DB, encoding="utf-8") as f:
        return json.load(f)


@router.get("")
def list_scripts(
    industry: str | None = Query(None, description="行业筛选: 零售/B2B/本地服务/教育/健康"),
    scenario: str | None = Query(None),
    search: str | None = Query(None),
):
    """列出话术模板，支持按行业和场景筛选。"""
    scripts = _load_scripts()
    if industry:
        scripts = [s for s in scripts if s["industry"] == industry]
    if scenario:
        scripts = [s for s in scripts if s["scenario"] == scenario]
    if search:
        keyword = search.lower()
        scripts = [
            s for s in scripts
            if keyword in s["title"].lower()
            or keyword in s["scenario"].lower()
            or any(keyword in kw.lower() for kw in s.get("trigger_keywords", []))
        ]
    return {"total": len(scripts), "templates": scripts}


@router.get("/industries")
def list_industries():
    """列出所有行业。"""
    scripts = _load_scripts()
    industries = sorted(set(s["industry"] for s in scripts))
    return {"industries": industries}


@router.get("/{script_id}")
def get_script(script_id: str):
    """获取单个话术模板。"""
    scripts = _load_scripts()
    for s in scripts:
        if s["id"] == script_id:
            return s
    raise HTTPException(status_code=404, detail="Script not found")


@router.post("/generate")
def generate_script(request: dict):
    """根据行业和场景生成个性化话术。

    输入: { industry, scenario, customer_context, product_info }
    输出: 填充了具体信息的完整话术
    """
    industry = request.get("industry", "")
    scenario = request.get("scenario", "")
    product_info = request.get("product_info", "")
    customer_context = request.get("customer_context", "")

    scripts = _load_scripts()
    matches = [
        s for s in scripts
        if s["industry"] == industry and scenario.lower() in s["scenario"].lower()
    ]
    if not matches:
        matches = [s for s in scripts if s["industry"] == industry]

    if not matches:
        raise HTTPException(
            status_code=404,
            detail=f"No template found for industry={industry}, scenario={scenario}"
        )

    template = matches[0]
    filled = {}
    for key, text in template["template"].items():
        # Simple placeholder filling
        text = text.replace("[卖点1]", product_info[:50] or "核心功能")
        text = text.replace("[卖点2]", product_info[50:100] if len(product_info) > 50 else "附加服务")
        text = text.replace("[具体效果]", "效率提升30%以上")
        filled[key] = text

    return {
        "template": template,
        "generated": filled,
        "tips": template.get("tips", []),
        "persona": template.get("persona", ""),
    }
