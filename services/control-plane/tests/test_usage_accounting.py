from decimal import Decimal

from app.usage_accounting import estimate_credits_micros, normalize_provider_usage, settle_usage


def test_chat_uses_provider_returned_token_counts():
    data = {"usage": {"prompt_tokens": 1000, "completion_tokens": 500, "total_tokens": 1500}}
    usage, cost_micros, credits_micros, pricing_version, snapshot = settle_usage("text.fast", data, {}, {})
    assert usage["input_tokens"] == 1000
    assert usage["output_tokens"] == 500
    assert usage["total_tokens"] == 1500
    assert cost_micros == 2400
    assert credits_micros == 400000
    assert pricing_version
    assert snapshot["pricing_version"] == pricing_version


def test_failed_or_empty_image_response_does_not_invent_usage():
    usage = normalize_provider_usage("image.standard", {"data": []}, {"n": 4})
    assert usage["image_count"] == 0


def test_route_pricing_overrides_default_price_book():
    config = {
        "pricing_version": "test-price-v1",
        "pricing": {"image_cny": str(Decimal("0.30"))},
    }
    _, cost_micros, credits_micros, version, snapshot = settle_usage(
        "image.standard",
        {"data": [{"url": "https://example.test/image.png"}]},
        {"n": 1},
        config,
    )
    assert cost_micros == 300000
    assert credits_micros == 50000000
    assert version == "test-price-v1"
    assert snapshot["rates"] == {"image_cny": "0.30"}


def test_estimate_credits_micros_returns_positive_and_honors_route_pricing():
    text_est = estimate_credits_micros("text.fast", {"messages": [{"role": "user", "content": "hello"}]}, {})
    assert text_est > 0

    default_image = estimate_credits_micros("image.standard", {"n": 1}, {})
    assert default_image == 41666667

    custom_image = estimate_credits_micros(
        "image.standard",
        {"n": 1},
        {"pricing": {"image_cny": "0.30"}},
    )
    assert custom_image == 50000000


def test_estimate_credits_micros_is_at_least_one_micro():
    assert estimate_credits_micros("speech.tts", {"input": "a"}, {}) >= 1


def test_video_estimate_uses_conservative_observed_token_rate():
    estimated = estimate_credits_micros(
        "video.standard",
        {"duration": 6, "resolution": "720p"},
        {},
    )

    # 6s * 25k tokens/s * CNY46/M tokens / 60% * 100 credits/CNY
    assert estimated == 1_150_000_000


def test_video_token_rate_can_be_tuned_per_route():
    estimated = estimate_credits_micros(
        "video.standard",
        {"duration": 4},
        {"video_tokens_per_second": 20000},
    )

    assert estimated == 613_333_333


def test_model_specific_price_and_cache_discount_are_snapshotted():
    usage, provider_cost, credits, version, snapshot = settle_usage(
        "text.reasoning",
        {
            "usage": {
                "input_tokens": 1_000_000,
                "output_tokens": 100_000,
                "prompt_tokens_details": {"cached_tokens": 250_000},
            }
        },
        {},
        {},
        "doubao-seed-evolving",
    )

    # 750k uncached * 6 + 250k cached * 1.2 + 100k output * 30 = CNY 7.8.
    assert usage["cached_tokens"] == 250_000
    assert provider_cost == 7_800_000
    assert credits == 1_300_000_000
    assert version == "volc-seed-evolving-2026-08"
    assert snapshot["provider_model"] == "doubao-seed-evolving"
    assert snapshot["rates"]["cached_input_million_cny"] == "1.2"
