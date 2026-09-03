"""Business background workers shared by every API entry point."""

from __future__ import annotations

import asyncio
import contextlib
import logging

from fastapi import FastAPI

logger = logging.getLogger(__name__)

PROFILE_SYNC_PLATFORMS = {"douyin", "xhs", "kuaishou", "bilibili", "tencent", "weibo"}


def _profile_sync_eligible(account: dict) -> bool:
    platform = str(account.get("platform") or "")
    session_valid = bool((account.get("session") or {}).get("valid"))
    return bool(
        account.get("enabled", True)
        and account.get("status") == "connected"
        and platform in PROFILE_SYNC_PLATFORMS
        and (session_valid or platform in {"tencent", "weibo"})
    )


async def _comment_retry_loop() -> None:
    from szyg.comment_engine import process_due_comments

    while True:
        await asyncio.sleep(30)
        try:
            result = await process_due_comments(limit=10)
            if result.get("processed"):
                logger.info("Marketing comment worker requeued %s item(s)", result["processed"])
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Marketing comment worker iteration failed: %s", exc)


async def _account_profile_sync_loop() -> None:
    """Refresh connected own-account metrics at most once per day."""
    from szyg.account_profile_sync import profile_sync_due, sync_account_profile
    from szyg.channel_accounts import list_accounts

    await asyncio.sleep(60)
    while True:
        try:
            accounts = [
                account for account in list_accounts(include_defaults=True)
                if _profile_sync_eligible(account) and profile_sync_due(account)
            ]
            for account in accounts:
                try:
                    await sync_account_profile(str(account["id"]), force=False)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    logger.warning("Account metric sync failed for %s: %s", account.get("id"), exc)
                await asyncio.sleep(2)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Account metric worker iteration failed: %s", exc)
        await asyncio.sleep(3600)


async def _geo_audit_loop() -> None:
    from szyg.geo_service import geo_audit_worker_loop

    await geo_audit_worker_loop()


def configure_background_workers(app: FastAPI) -> None:
    """Register workers on the app factory so desktop and service modes match."""

    @app.on_event("startup")
    async def start_business_workers() -> None:
        existing = getattr(app.state, "business_workers", [])
        if any(not task.done() for task in existing):
            return
        app.state.business_workers = [
            asyncio.create_task(_comment_retry_loop(), name="comment-retry-worker"),
            asyncio.create_task(_account_profile_sync_loop(), name="account-profile-sync-worker"),
            asyncio.create_task(_geo_audit_loop(), name="geo-audit-worker"),
        ]

    @app.on_event("shutdown")
    async def stop_business_workers() -> None:
        workers = list(getattr(app.state, "business_workers", []))
        for task in workers:
            task.cancel()
        for task in workers:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        app.state.business_workers = []
