from __future__ import annotations

import logging
import json
import time
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select, update

from .config import get_settings
from .database import ProviderBillingDaily, RefreshSession, SessionLocal, UsageEvent, utcnow
from .provider_billing import ProviderBillingClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("szyg-control-worker")


def _cleanup_reference_uploads() -> int:
    settings = get_settings()
    root = Path(settings.reference_temp_dir).resolve()
    if not root.exists():
        return 0
    removed = 0
    now = int(time.time())
    for metadata_path in root.glob("*.json"):
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            if int(metadata.get("expires_at") or 0) > now:
                continue
            (root / str(metadata.get("stored_name") or "")).unlink(missing_ok=True)
            metadata_path.unlink(missing_ok=True)
            removed += 1
        except (OSError, ValueError, json.JSONDecodeError):
            continue
    return removed


def _sync_provider_billing() -> None:
    settings = get_settings()
    if not settings.provider_billing_enabled:
        return
    client = ProviderBillingClient()
    today = utcnow().astimezone(ZoneInfo("Asia/Shanghai")).date()
    for days_ago in range(0, 4):
        billing_date = today - timedelta(days=days_ago)
        cost_micros, line_count, request_id = client.fetch_daily_cost(billing_date)
        with SessionLocal.begin() as db:
            item = db.query(ProviderBillingDaily).filter_by(
                provider="volcengine",
                billing_date=billing_date,
            ).with_for_update().one_or_none()
            if item is None:
                item = ProviderBillingDaily(provider="volcengine", billing_date=billing_date)
                db.add(item)
            item.actual_cost_micros = cost_micros
            item.line_count = line_count
            item.provider_request_id = request_id
            item.synced_at = utcnow()
            zone = ZoneInfo("Asia/Shanghai")
            start_local = datetime.combine(billing_date, datetime.min.time(), tzinfo=zone)
            start = start_local.astimezone(ZoneInfo("UTC"))
            end = (start_local + timedelta(days=1)).astimezone(ZoneInfo("UTC"))
            settled_cost, credits_revenue = db.execute(select(
                func.coalesce(func.sum(UsageEvent.provider_cost_micros), 0),
                func.coalesce(func.sum(UsageEvent.credits_charged_micros), 0),
            ).where(
                UsageEvent.status == "succeeded",
                UsageEvent.completed_at >= start,
                UsageEvent.completed_at < end,
            )).one()
            revenue_micros = int(Decimal(int(credits_revenue or 0)) / Decimal("100"))
            if revenue_micros > 0 and cost_micros / revenue_micros > 0.65:
                logger.error(
                    "Provider cost guard triggered for %s: actual cost share %.2f%%",
                    billing_date,
                    cost_micros / revenue_micros * 100,
                )
            if int(settled_cost or 0) > 0:
                variance = abs(cost_micros - int(settled_cost)) / int(settled_cost)
                if variance > 0.05:
                    logger.warning(
                        "Provider billing variance for %s is %.2f%%",
                        billing_date,
                        variance * 100,
                    )


def main() -> None:
    while True:
        try:
            cutoff = utcnow() - timedelta(days=7)
            stale_usage_cutoff = utcnow() - timedelta(hours=24)
            with SessionLocal.begin() as db:
                result = db.execute(delete(RefreshSession).where(
                    RefreshSession.expires_at < cutoff,
                ))
                stale = db.execute(update(UsageEvent).where(
                    UsageEvent.status == "reserved",
                    UsageEvent.created_at < stale_usage_cutoff,
                ).values(
                    status="failed",
                    units=0,
                    credits_charged_micros=0,
                    error_code="reservation_expired",
                    error_message="智能服务任务已超时",
                    completed_at=utcnow(),
                ))
            if result.rowcount:
                logger.info("Removed %s expired sessions", result.rowcount)
            if stale.rowcount:
                logger.warning("Released %s stale usage reservations", stale.rowcount)
            removed_references = _cleanup_reference_uploads()
            if removed_references:
                logger.info("Removed %s expired inference references", removed_references)
            _sync_provider_billing()
        except Exception:
            logger.exception("Control worker cycle failed")
        time.sleep(3600)


if __name__ == "__main__":
    main()
