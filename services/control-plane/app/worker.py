from __future__ import annotations

import logging
import time
from datetime import timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import delete

from .config import get_settings
from .database import ProviderBillingDaily, RefreshSession, SessionLocal, utcnow
from .provider_billing import ProviderBillingClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("szyg-control-worker")


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


def main() -> None:
    while True:
        try:
            cutoff = utcnow() - timedelta(days=7)
            with SessionLocal.begin() as db:
                result = db.execute(delete(RefreshSession).where(
                    RefreshSession.expires_at < cutoff,
                ))
            if result.rowcount:
                logger.info("Removed %s expired sessions", result.rowcount)
            _sync_provider_billing()
        except Exception:
            logger.exception("Control worker cycle failed")
        time.sleep(3600)


if __name__ == "__main__":
    main()
