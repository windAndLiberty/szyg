from decimal import Decimal

from app.usage_accounting import normalize_provider_usage, settle_usage


def test_chat_uses_provider_returned_token_counts():
    data = {"usage": {"prompt_tokens": 1000, "completion_tokens": 500, "total_tokens": 1500}}
    usage, cost_micros, credits_micros, pricing_version = settle_usage("text.fast", data, {}, {})
    assert usage["input_tokens"] == 1000
    assert usage["output_tokens"] == 500
    assert usage["total_tokens"] == 1500
    assert cost_micros == 2400
    assert credits_micros == 400000
    assert pricing_version


def test_failed_or_empty_image_response_does_not_invent_usage():
    usage = normalize_provider_usage("image.standard", {"data": []}, {"n": 4})
    assert usage["image_count"] == 0


def test_route_pricing_overrides_default_price_book():
    config = {
        "pricing_version": "test-price-v1",
        "pricing": {"image_cny": str(Decimal("0.30"))},
    }
    _, cost_micros, credits_micros, version = settle_usage(
        "image.standard",
        {"data": [{"url": "https://example.test/image.png"}]},
        {"n": 1},
        config,
    )
    assert cost_micros == 300000
    assert credits_micros == 50000000
    assert version == "test-price-v1"
