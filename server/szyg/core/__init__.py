"""
szyg Core — Browser automation, scraping engine, and session management.

Exports the version-locked browser pool and commercial scraping primitives.
"""
from szyg.core.browser_pool import VersionLockedBrowserPool, get_browser_pool_v2
from szyg.core.scraper_engine import ScraperEngine

__all__ = [
    "VersionLockedBrowserPool",
    "get_browser_pool_v2",
    "ScraperEngine",
]
