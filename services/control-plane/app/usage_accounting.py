from __future__ import annotations

import json
from decimal import Decimal, ROUND_HALF_UP
from typing import Any


MICROS = Decimal("1000000")
CREDITS_PER_CNY = Decimal("100")
PROVIDER_COST_SHARE = Decimal("0.60")
PRICING_VERSION = "volc-2026-08"
VOLCENGINE_PRICING_SOURCE = "https://www.volcengine.com/product/ark"


DEFAULT_PRICING: dict[str, dict[str, Decimal]] = {
    "text.fast": {
        "input_million_cny": Decimal("0.6"),
        "output_million_cny": Decimal("3.6"),
    },
    "text.reasoning": {
        "input_million_cny": Decimal("3.2"),
        "output_million_cny": Decimal("16"),
    },
    "text.vision": {
        "input_million_cny": Decimal("3.2"),
        "output_million_cny": Decimal("16"),
    },
    "image.standard": {"image_cny": Decimal("0.25")},
    "video.standard": {"token_million_cny": Decimal("46")},
    "video.presenter": {"token_million_cny": Decimal("46")},
    "speech.tts": {"characters_10k_cny": Decimal("5")},
}


MODEL_PRICING: tuple[tuple[str, dict[str, Decimal], str], ...] = (
    (
        "deepseek-v4-flash",
        {
            "input_million_cny": Decimal("1"),
            "cached_input_million_cny": Decimal("0.02"),
            "output_million_cny": Decimal("2"),
        },
        "volc-deepseek-v4-flash-2026-08",
    ),
    (
        "doubao-seed-evolving",
        {
            "input_million_cny": Decimal("6"),
            "cached_input_million_cny": Decimal("1.2"),
            "output_million_cny": Decimal("30"),
        },
        "volc-seed-evolving-2026-08",
    ),
    (
        "doubao-seed-2-1-pro",
        {
            "input_million_cny": Decimal("6"),
            "cached_input_million_cny": Decimal("1.2"),
            "output_million_cny": Decimal("30"),
        },
        "volc-seed-2.1-pro-2026-08",
    ),
)


def _integer(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def normalize_provider_usage(capability: str, data: dict, payload: dict) -> dict[str, int]:
    raw = data.get("usage") if isinstance(data, dict) else {}
    raw = raw if isinstance(raw, dict) else {}
    input_tokens = _integer(raw.get("input_tokens") or raw.get("prompt_tokens"))
    output_tokens = _integer(raw.get("output_tokens") or raw.get("completion_tokens"))
    total_tokens = _integer(raw.get("total_tokens")) or input_tokens + output_tokens
    if total_tokens and not input_tokens and not output_tokens:
        input_tokens = total_tokens
    prompt_details = raw.get("prompt_tokens_details") or raw.get("input_tokens_details") or {}
    cached_tokens = _integer(prompt_details.get("cached_tokens") if isinstance(prompt_details, dict) else 0)

    image_count = _integer(raw.get("generated_images") or raw.get("image_count"))
    if capability == "image.standard" and not image_count:
        image_count = len(data.get("data") or []) if isinstance(data, dict) else 0

    speech_characters = _integer(raw.get("characters"))
    if capability == "speech.tts" and not speech_characters:
        speech_characters = len(str(payload.get("input") or payload.get("text") or ""))

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "cached_tokens": cached_tokens,
        "image_count": image_count,
        "video_tokens": total_tokens if capability in {"video.standard", "video.presenter"} else 0,
        "speech_characters": speech_characters,
    }


def _pricing(
    capability: str,
    route_config: dict | None,
    provider_model: str = "",
) -> tuple[dict[str, Decimal], str]:
    configured = (route_config or {}).get("pricing") or {}
    if configured:
        return {key: Decimal(str(value)) for key, value in configured.items()}, str(
            (route_config or {}).get("pricing_version") or "configured"
        )
    normalized_model = provider_model.strip().lower()
    for marker, pricing, version in MODEL_PRICING:
        if marker in normalized_model:
            return dict(pricing), version
    return DEFAULT_PRICING.get(capability, {}), PRICING_VERSION


def _pricing_snapshot(
    capability: str,
    provider_model: str,
    pricing: dict[str, Decimal],
    pricing_version: str,
    pricing_source: str,
) -> dict[str, Any]:
    return {
        "capability": capability,
        "provider_model": provider_model,
        "pricing_version": pricing_version,
        "pricing_source": pricing_source,
        "provider_cost_share": str(PROVIDER_COST_SHARE),
        "credits_per_cny": str(CREDITS_PER_CNY),
        "rates": {key: str(value) for key, value in pricing.items()},
    }


def settle_usage(
    capability: str,
    data: dict,
    payload: dict,
    route_config: dict | None,
    provider_model: str = "",
) -> tuple[dict[str, int], int, int, str, dict[str, Any]]:
    usage = normalize_provider_usage(capability, data, payload)
    pricing, pricing_version = _pricing(capability, route_config, provider_model)
    cost_cny = Decimal("0")

    if capability.startswith("text.") or capability == "embedding.standard":
        cached_tokens = min(usage["input_tokens"], usage["cached_tokens"])
        uncached_tokens = usage["input_tokens"] - cached_tokens
        cost_cny += Decimal(uncached_tokens) * pricing.get("input_million_cny", Decimal("0")) / Decimal("1000000")
        cost_cny += Decimal(cached_tokens) * pricing.get(
            "cached_input_million_cny",
            pricing.get("input_million_cny", Decimal("0")),
        ) / Decimal("1000000")
        cost_cny += Decimal(usage["output_tokens"]) * pricing.get("output_million_cny", Decimal("0")) / Decimal("1000000")
    elif capability == "image.standard":
        cost_cny = Decimal(usage["image_count"]) * pricing.get("image_cny", Decimal("0"))
    elif capability in {"video.standard", "video.presenter"}:
        cost_cny = Decimal(usage["video_tokens"]) * pricing.get("token_million_cny", Decimal("0")) / Decimal("1000000")
    elif capability == "speech.tts":
        cost_cny = Decimal(usage["speech_characters"]) * pricing.get("characters_10k_cny", Decimal("0")) / Decimal("10000")

    provider_cost_micros = int((cost_cny * MICROS).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    credits = cost_cny / PROVIDER_COST_SHARE * CREDITS_PER_CNY
    credits_micros = int((credits * MICROS).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    snapshot = _pricing_snapshot(
        capability,
        provider_model,
        pricing,
        pricing_version,
        str((route_config or {}).get("pricing_source") or VOLCENGINE_PRICING_SOURCE),
    )
    return usage, provider_cost_micros, credits_micros, pricing_version, snapshot


def estimate_credits_micros(
    capability: str,
    payload: dict,
    route_config: dict | None,
    provider_model: str = "",
) -> int:
    """预估算一次调用大致消耗的 credits（微单位，1 credits = 1e6 micros）。

    用于统一计费模式下的额度预检：credits 余额不足时直接拦截，
    实际扣减以 `settle_usage` 结算的真实用量为准。
    """
    pricing, _ = _pricing(capability, route_config, provider_model)
    cost_cny = Decimal("0")
    if capability.startswith("text.") or capability == "embedding.standard":
        input_tokens = max(1, len(json.dumps(payload, ensure_ascii=False)) // 2)
        output_tokens = max(1, int(payload.get("max_tokens") or payload.get("max_new_tokens") or 1024))
        cost_cny += Decimal(input_tokens) * pricing.get("input_million_cny", Decimal("0")) / Decimal("1000000")
        cost_cny += Decimal(output_tokens) * pricing.get("output_million_cny", Decimal("0")) / Decimal("1000000")
    elif capability == "image.standard":
        count = max(1, int(payload.get("n") or 1))
        cost_cny = Decimal(count) * pricing.get("image_cny", Decimal("0"))
    elif capability in {"video.standard", "video.presenter"}:
        duration = max(1, int(payload.get("duration") or 5))
        # Video token usage is materially higher than text token estimates.
        # Production observations are around 21.7k tokens/second for 720p;
        # reserve conservatively so settlement cannot push a prepaid account
        # negative after the provider task has already completed.
        tokens_per_second = Decimal(str((route_config or {}).get("video_tokens_per_second", 25000)))
        cost_cny = Decimal(duration) * tokens_per_second * pricing.get("token_million_cny", Decimal("0")) / Decimal("1000000")
    elif capability == "speech.tts":
        chars = max(1, len(str(payload.get("input") or payload.get("text") or "")))
        cost_cny = Decimal(chars) * pricing.get("characters_10k_cny", Decimal("0")) / Decimal("10000")
    credits = cost_cny / PROVIDER_COST_SHARE * CREDITS_PER_CNY
    return max(1, int((credits * MICROS).quantize(Decimal("1"), rounding=ROUND_HALF_UP)))
