from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any


MICROS = Decimal("1000000")
CREDITS_PER_CNY = Decimal("100")
PROVIDER_COST_SHARE = Decimal("0.60")
PRICING_VERSION = "volc-2026-07"


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
    "speech.tts": {"characters_10k_cny": Decimal("5")},
}


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
        "video_tokens": total_tokens if capability == "video.standard" else 0,
        "speech_characters": speech_characters,
    }


def _pricing(capability: str, route_config: dict | None) -> tuple[dict[str, Decimal], str]:
    configured = (route_config or {}).get("pricing") or {}
    if configured:
        return {key: Decimal(str(value)) for key, value in configured.items()}, str(
            (route_config or {}).get("pricing_version") or "configured"
        )
    return DEFAULT_PRICING.get(capability, {}), PRICING_VERSION


def settle_usage(
    capability: str,
    data: dict,
    payload: dict,
    route_config: dict | None,
) -> tuple[dict[str, int], int, int, str]:
    usage = normalize_provider_usage(capability, data, payload)
    pricing, pricing_version = _pricing(capability, route_config)
    cost_cny = Decimal("0")

    if capability.startswith("text.") or capability == "embedding.standard":
        cost_cny += Decimal(usage["input_tokens"]) * pricing.get("input_million_cny", Decimal("0")) / Decimal("1000000")
        cost_cny += Decimal(usage["output_tokens"]) * pricing.get("output_million_cny", Decimal("0")) / Decimal("1000000")
    elif capability == "image.standard":
        cost_cny = Decimal(usage["image_count"]) * pricing.get("image_cny", Decimal("0"))
    elif capability == "video.standard":
        cost_cny = Decimal(usage["video_tokens"]) * pricing.get("token_million_cny", Decimal("0")) / Decimal("1000000")
    elif capability == "speech.tts":
        cost_cny = Decimal(usage["speech_characters"]) * pricing.get("characters_10k_cny", Decimal("0")) / Decimal("10000")

    provider_cost_micros = int((cost_cny * MICROS).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    credits = cost_cny / PROVIDER_COST_SHARE * CREDITS_PER_CNY
    credits_micros = int((credits * MICROS).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return usage, provider_cost_micros, credits_micros, pricing_version
