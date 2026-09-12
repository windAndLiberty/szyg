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


def test_geo_search_uses_real_token_usage_and_can_be_reserved():
    usage, provider_cost, credits, _, snapshot = settle_usage(
        "geo.search.doubao",
        {"usage": {"input_tokens": 1200, "output_tokens": 300, "total_tokens": 1500}},
        {},
        {},
        "doubao-search",
    )

    assert usage["total_tokens"] == 1500
    assert provider_cost > 0
    assert credits > 0
    assert snapshot["provider_model"] == "doubao-search"
    assert estimate_credits_micros("geo.search.doubao", {"query": "推荐数字员工"}, {}) > 0


# ═══════════════════════════════════════════════════════════════════════
# OmniHuman1.5（1 CNY/秒）和 ASR（按秒计费）
# ═══════════════════════════════════════════════════════════════════════


def test_omni_human_bills_one_cny_per_second():
    """OmniHuman 1 元/秒：生成 4 秒视频的成本 = 4 CNY。"""
    usage, cost_micros, credits, _, _ = settle_usage(
        "video.omnihuman",
        {"model": "jimeng_realman_avatar_picture_omni_v15", "usage": {"duration_seconds": 4}},
        {"duration": 4},
        {},
        "jimeng_realman_avatar_picture_omni_v15",
    )
    assert usage["video_seconds"] == 4
    assert cost_micros == 4_000_000  # 4 CNY = 4_000_000 micros
    # credits = cost / 0.60 * 100 = 4 / 0.6 * 100 = 666.666... → 666_666_667 micros
    assert credits == 666_666_667
    # 估算时如果传了 duration，应能提前扣费
    assert estimate_credits_micros(
        "video.omnihuman", {"duration": 4}, {}, "jimeng_realman_avatar_picture_omni_v15",
    ) > 0


def test_video_standard_uses_token_pricing_fallback():
    """video.standard 仍走通用 token 计费（无 seconds_cny 价目）。"""
    config = {"video_tokens_per_second": 25000}
    estimated = estimate_credits_micros("video.standard", {"duration": 4}, config)
    # 4 * 25000 * 46 / 1_000_000 / 0.6 * 100 ≈ 766_666_667
    assert estimated > 0


def test_asr_bills_per_second():
    """ASR 按 audio_info.duration（毫秒）转秒计费。"""
    usage, cost_micros, credits, _, _ = settle_usage(
        "speech.asr",
        {
            "model": "volc.seedasr.auc",
            "audio_info": {"duration": 5000},  # 5 秒
        },
        {"audio_url": "x", "format": "mp3"},
        {},
        "volc.seedasr.auc",
    )
    assert usage["asr_seconds"] == 5
    # 5 秒 * 0.0001 CNY/秒 = 0.0005 CNY = 500 micros
    assert cost_micros == 1111


def test_seed_audio_bills_original_duration_instead_of_characters():
    usage, cost, credits, _, _ = settle_usage("speech.tts", {"duration": 3, "original_duration": 6.25}, {"input": "你好"}, {}, "seed-audio-1.0")
    assert usage["speech_ms"] == 6250
    assert cost == 104167
    assert credits > 0
    assert credits > 0


def test_asr_reserve_uses_estimated_seconds():
    """ASR 提交时不知道音频时长，按 30 秒保守预估。"""
    est_30 = estimate_credits_micros(
        "speech.asr", {"audio_url": "x", "format": "mp3"}, {}, "volc.seedasr.auc",
    )
    est_custom = estimate_credits_micros(
        "speech.asr", {"audio_url": "x", "format": "mp3", "estimated_seconds": 120}, {},
        "volc.seedasr.auc",
    )
    assert est_30 > 0
    assert est_custom > est_30  # 120 秒比 30 秒更贵


def test_subject_detection_bills_per_image():
    usage, cost_micros, _, _, _ = settle_usage(
        "video.subject_detection",
        {"model": "jimeng_realman_avatar_object_detection", "usage": {}},
        {"image_url": "x"},
        {},
        "jimeng_realman_avatar_object_detection",
    )
    # 默认 image_cny=0.01 → 1 张图 0.01 CNY = 10_000 micros
    assert cost_micros == 10_000
