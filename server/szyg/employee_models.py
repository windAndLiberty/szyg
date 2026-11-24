"""Public Ark model IDs and on-demand text prices (CNY per million tokens)."""

PRICE_SOURCE = "https://docs.volcengine.com/docs/ark/model-pricing?lang=zh"
PRICE_DATE = "2026-11-23"
EMPLOYEE_PREFIX = "text.employee."

EMPLOYEE_MODELS = {
    "doubao-seed-evolving": {
        "name": "Doubao-Seed-Evolving",
        "pricing": {"input": 6, "cached_input": 1.2, "output": 30},
    },
    "deepseek-v4-1-flash-economy-261017": {
        "name": "DeepSeek-V4.1-Flash（经济版）",
        "pricing": {
            "input": 0.8, "cached_input": 0.016, "output": 3.2,
            "peak": {"input": 1.6, "cached_input": 0.032, "output": 6.4},
        },
    },
    "kimi-k3-1-pro-261024": {
        "name": "Kimi-K3.1-Pro",
        "pricing": {"input": 13, "cached_input": 1.3, "output": 68},
    },
}


def employee_model_catalog(capabilities: dict | None) -> dict:
    """Availability means configured for this account, not an inference probe."""
    aliases = {
        row["alias"]: row.get("available") is True
        for row in (capabilities or {}).get("items", [])
        if isinstance(row, dict) and isinstance(row.get("alias"), str)
    }
    supported = (capabilities or {}).get("employee_models_version") == 1
    items = []
    for model_id, definition in EMPLOYEE_MODELS.items():
        available = supported and aliases.get(EMPLOYEE_PREFIX + model_id, False)
        if available:
            status = "available"
        elif capabilities is None:
            status = "unknown"
        elif not supported:
            status = "gateway_upgrade_required"
        else:
            status = "unavailable"
        items.append({"id": model_id, **definition, "available": available, "status": status})
    return {"items": items, "pricing_source": PRICE_SOURCE, "as_of": PRICE_DATE}
