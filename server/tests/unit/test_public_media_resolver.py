from szyg.integrations.public_media_resolver import _best_candidate, extract_media_candidates


def test_kling_creative_response_prefers_generated_output():
    payload = {
        "data": {
            "resource": {
                "resource": "https://v15-kling.klingai.com/jobs/demo-output.mp4",
                "cover": {"resource": "https://v15-kling.klingai.com/jobs/demo-cover.jpg"},
            },
            "source": {"resource": "https://v15-kling.klingai.com/jobs/input-source.mp4"},
        }
    }

    best = _best_candidate(extract_media_candidates(payload, "response"))

    assert best is not None
    assert best["url"].endswith("demo-output.mp4")


def test_candidate_extraction_ignores_non_media_urls():
    payload = {
        "share": "https://kling.ai/app/work/123",
        "avatar": "https://cdn.example.com/avatar.png",
        "video_url": "https://cdn.example.com/final.mp4",
    }

    best = _best_candidate(extract_media_candidates(payload))

    assert best is not None
    assert best["url"] == "https://cdn.example.com/final.mp4"
