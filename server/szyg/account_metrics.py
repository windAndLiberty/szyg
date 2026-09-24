"""Historical metrics for the customer's own connected channel accounts."""

from __future__ import annotations

from datetime import datetime, timedelta

from szyg.atomic_file import atomic_read, atomic_write
from szyg.data_path import DATA_DIR


METRICS_FILE = DATA_DIR / "account_metric_snapshots.json"
METRIC_KEYS = ("followers", "following", "works_count", "likes_count")
MAX_SNAPSHOTS = 5000


def record_account_metrics(account: dict) -> None:
    """Append a profile-sync snapshot without storing credentials or sessions."""
    if account.get("sync_status") != "success" or not account.get("id"):
        return
    row = {
        "account_id": str(account["id"]),
        "platform": str(account.get("platform") or ""),
        "label": str(account.get("nickname") or account.get("label") or ""),
        "recorded_at": str(account.get("last_profile_sync_at") or datetime.now().isoformat()),
        **{key: int(account.get(key) or 0) for key in METRIC_KEYS},
    }
    rows = atomic_read(METRICS_FILE)
    if rows and rows[-1].get("account_id") == row["account_id"] and rows[-1].get("recorded_at") == row["recorded_at"]:
        return
    atomic_write(METRICS_FILE, (rows + [row])[-MAX_SNAPSHOTS:])


def account_metrics_overview(days: int = 30, account_id: str = "") -> dict:
    cutoff = datetime.now() - timedelta(days=max(1, min(days, 365)))
    points = []
    for row in atomic_read(METRICS_FILE):
        if account_id and row.get("account_id") != account_id:
            continue
        try:
            if datetime.fromisoformat(str(row.get("recorded_at") or "")) < cutoff:
                continue
        except ValueError:
            continue
        points.append(row)

    grouped: dict[str, list[dict]] = {}
    for row in points:
        grouped.setdefault(str(row.get("account_id") or ""), []).append(row)

    accounts = []
    totals = {key: 0 for key in METRIC_KEYS}
    changes = {key: 0 for key in METRIC_KEYS}
    for rows in grouped.values():
        rows.sort(key=lambda item: str(item.get("recorded_at") or ""))
        first, latest = rows[0], rows[-1]
        delta = {key: int(latest.get(key) or 0) - int(first.get(key) or 0) for key in METRIC_KEYS}
        for key in METRIC_KEYS:
            totals[key] += int(latest.get(key) or 0)
            changes[key] += delta[key]
        accounts.append({
            "account_id": latest["account_id"],
            "platform": latest.get("platform", ""),
            "label": latest.get("label", ""),
            "latest": {key: int(latest.get(key) or 0) for key in METRIC_KEYS},
            "change": delta,
            "points": rows,
        })
    return {"days": days, "totals": totals, "change": changes, "accounts": accounts, "point_count": len(points)}
