"""Submit a creator form once and surface uncertain outcomes for review."""

from playwright.async_api import Locator, Page, TimeoutError


class PublishVerificationError(RuntimeError):
    """A publish click may have reached the platform without a visible receipt."""


async def submit_once(
    page: Page,
    button: Locator,
    receipt_url: str,
    *,
    confirmation: Locator | None = None,
) -> None:
    await button.wait_for(state="visible", timeout=10_000)
    try:
        await button.click(timeout=10_000)
        if confirmation is not None:
            try:
                await confirmation.wait_for(state="visible", timeout=5_000)
            except TimeoutError:
                pass
            else:
                await confirmation.click(timeout=10_000)
        await page.wait_for_url(receipt_url, timeout=30_000)
    except Exception as exc:
        raise PublishVerificationError(
            "提交结果待核实，请先在平台作品后台检查，避免重复发布。"
        ) from exc
