from szyg import account_metrics


def test_account_metrics_records_only_successful_own_profile_snapshots(tmp_path, monkeypatch):
    monkeypatch.setattr(account_metrics, "METRICS_FILE", tmp_path / "metrics.json")
    account_metrics.record_account_metrics({"id": "a1", "platform": "douyin", "sync_status": "failed", "followers": 9})
    account_metrics.record_account_metrics({
        "id": "a1", "platform": "douyin", "nickname": "经营号", "sync_status": "success",
        "followers": 100, "following": 10, "works_count": 5, "likes_count": 300,
        "last_profile_sync_at": "2026-08-18T10:00:00",
    })
    account_metrics.record_account_metrics({
        "id": "a1", "platform": "douyin", "nickname": "经营号", "sync_status": "success",
        "followers": 120, "following": 11, "works_count": 7, "likes_count": 360,
        "last_profile_sync_at": "2026-08-19T10:00:00",
    })

    overview = account_metrics.account_metrics_overview(days=30)
    assert overview["totals"]["followers"] == 120
    assert overview["change"]["followers"] == 20
    assert overview["accounts"][0]["change"]["works_count"] == 2
    assert overview["point_count"] == 2
