#!/usr/bin/env python3
"""
MCP Server: Web Tools — industrial-grade scraping + search for Hermes agent.

Parsing:   BeautifulSoup 4 + html2text (no fragile regex)
Search:    Brave Search API + SearXNG (private env var → dynamic registry → aggressive retry)
SPA/SSR:   Playwright browser-pool hook for social media creator domains

Tools:
  web_fetch         — Raw HTTP GET with configurable headers
  web_scrape        — HTML → clean text or markdown (BeautifulSoup + html2text)
  web_search        — Auto-route between Brave Search and SearXNG
  web_search_brave  — Brave Search API wrapper
  web_search_searxng— SearXNG JSON API (private → dynamic public pool, 3-retry across instances)
  web_sitemap       — Extract URLs from sitemap.xml
"""
import sys, os, re, json, logging, asyncio, time
from pathlib import Path
from urllib.parse import urljoin, urlparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from szyg.mcp_server import MCPServer

logger = logging.getLogger(__name__)

server = MCPServer(
    "szyg-web-tools",
    "Web scraping (BeautifulSoup + html2text) and multi-engine search (Brave / SearXNG) for Hermes agent"
)

# ── Constants ────────────────────────────────────────────────

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

DEFAULT_TIMEOUT = 30.0
MAX_CONTENT_LENGTH = 2 * 1024 * 1024  # 2 MB max response
SCRAPE_TEXT_LIMIT = 100_000           # chars returned from web_scrape

# ── Social media domains that require Playwright (SPA / SSR / anti-bot) ──
PLAYWRIGHT_REQUIRED_DOMAINS = [
    "creator.douyin.com",
    "xiaohongshu.com",
    "creator.xiaohongshu.com",
    "bilibili.com",
    "kuaishou.com",
]

# SearXNG — private instance takes priority; public pool is fallback
_SEARXNG_PRIVATE = os.environ.get("SEARXNG_URL", "").rstrip("/")

# Dynamic instance registry URL (SearXNG official)
_SEARXNG_REGISTRY = "https://searx.space/data/instances.json"

# Static fallbacks — only used when dynamic registry fetch fails
_SEARXNG_STATIC_FALLBACKS = [
    "https://searx.be",
    "https://search.sapti.me",
    "https://searx.tiekoetter.com",
    "https://search.hbubli.cc",
    "https://search.im-in.space",
    "https://opnxng.com",
]

# Cache for dynamic instance list (TTL = 1 hour)
_searxng_cache: dict = {"instances": None, "fetched_at": 0}
_SEARXNG_CACHE_TTL = 3600


# ═══════════════════════════════════════════════════════════════
# HTML Parsing — BeautifulSoup + html2text (industrial-grade)
# ═══════════════════════════════════════════════════════════════

def _parse_html(html: str) -> "BeautifulSoup":
    """Parse HTML with BeautifulSoup using best-available parser."""
    from bs4 import BeautifulSoup
    # lxml is fastest; html.parser is stdlib fallback
    try:
        return BeautifulSoup(html, "lxml")
    except Exception:
        return BeautifulSoup(html, "html.parser")


def _html_to_text(html: str) -> str:
    """
    Extract clean readable text from HTML using BeautifulSoup.
    Strips scripts, styles, nav, footer; preserves paragraph structure.
    No fragile regex — proper DOM traversal.

    Returns:
        Clean plain text suitable for LLM consumption.
    """
    soup = _parse_html(html)

    # Remove non-content elements
    for tag_name in ("script", "style", "noscript", "iframe", "svg",
                     "canvas", "nav", "footer", "header", "aside",
                     "form", "button", "select", "textarea"):
        for tag in soup.find_all(tag_name):
            tag.decompose()

    # Remove hidden elements (display:none, aria-hidden, etc.)
    for tag in soup.find_all(style=re.compile(r"display\s*:\s*none", re.I)):
        tag.decompose()
    for tag in soup.find_all(attrs={"aria-hidden": "true"}):
        tag.decompose()

    # Extract title
    title = ""
    title_tag = soup.find("title")
    if title_tag:
        title = title_tag.get_text(strip=True)

    # Get body text with newline separation
    body = soup.find("body") or soup
    text = body.get_text(separator="\n", strip=True)

    # Collapse excessive whitespace
    text = re.sub(r'[ \t]{3,}', '  ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)

    result = text.strip()
    if title and not result.startswith(title):
        result = f"{title}\n\n{result}"

    return result


def _html_to_markdown(html: str, base_url: str = "") -> str:
    """
    Convert HTML to pristine Markdown using html2text.
    Configured to preserve links, images, headings, lists, and code blocks.
    Uses BeautifulSoup for pre-cleaning, html2text for the actual conversion.

    Args:
        html: Raw HTML string
        base_url: Base URL for resolving relative links/images

    Returns:
        Clean Markdown string.
    """
    import html2text as _h2t

    soup = _parse_html(html)

    # ── Extract page title before <head> is stripped ──
    page_title = soup.title.get_text(strip=True) if soup.title else ""

    # Remove noise elements
    for tag_name in ("script", "style", "noscript", "iframe", "svg",
                     "canvas", "nav", "footer", "aside",
                     "form", "button", "select", "textarea"):
        for tag in soup.find_all(tag_name):
            tag.decompose()

    # Remove hidden elements
    for tag in soup.find_all(style=re.compile(r"display\s*:\s*none|visibility\s*:\s*hidden", re.I)):
        tag.decompose()

    # Resolve relative URLs in <a href> and <img src>
    if base_url:
        for tag in soup.find_all("a", href=True):
            try:
                tag["href"] = urljoin(base_url, tag["href"])
            except Exception:
                pass
        for tag in soup.find_all("img", src=True):
            try:
                tag["src"] = urljoin(base_url, tag["src"])
            except Exception:
                pass

    # Focus on main content if available
    main = soup.find("main") or soup.find("article") or soup.find(role="main") or soup.find("body") or soup

    # Configure html2text
    converter = _h2t.HTML2Text()
    converter.body_width = 0           # No line wrapping
    converter.ignore_links = False     # Preserve links as [text](url)
    converter.ignore_images = False    # Preserve images as ![alt](src)
    converter.ignore_emphasis = False  # Preserve **bold** and *italic*
    converter.ignore_tables = False    # Convert tables to markdown
    converter.protect_links = True     # Don't break long URLs
    converter.unicode_snob = True      # Use Unicode instead of ASCII
    converter.skip_internal_links = False
    converter.inline_links = True      # Inline link format
    converter.wrap_links = False
    converter.mark_code = True         # Inline code → backticks
    converter.default_image_alt = "image"

    if base_url:
        converter.baseurl = base_url

    # Convert
    md = converter.handle(str(main))

    # Post-process: collapse excessive blank lines
    md = re.sub(r'\n{4,}', '\n\n\n', md)
    md = md.strip()

    # ── Prepend page title if extracted (avoids title loss since <head> is stripped) ──
    if page_title:
        md = f"# {page_title}\n\n{md}"

    return md


# ═══════════════════════════════════════════════════════════════
# HTTP Fetcher — CrewAI ScrapingTool core pattern
# ═══════════════════════════════════════════════════════════════

async def _fetch_url(
    url: str,
    headers: dict | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    max_length: int = MAX_CONTENT_LENGTH,
) -> dict:
    """
    Core HTTP fetcher with header handling, redirect following, and error classification.

    Returns:
        {"ok": bool, "status": int, "url": str, "content_type": str,
         "text": str, "headers": dict, "error": str}
    """
    import httpx

    default_headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
    }
    if headers:
        default_headers.update(headers)

    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            max_redirects=5,
            headers=default_headers,
            verify=True,
        ) as client:
            response = await client.get(url)
            content_type = response.headers.get("content-type", "")

            text = ""
            if response.status_code == 200:
                if len(response.content) > max_length:
                    text = response.content[:max_length].decode("utf-8", errors="replace")
                    text += "\n\n[Content truncated — exceeded 2 MB limit]"
                else:
                    text = response.text

            return {
                "ok": response.status_code < 400,
                "status": response.status_code,
                "url": str(response.url),
                "content_type": content_type,
                "text": text,
                "headers": dict(response.headers),
                "error": "" if response.status_code < 400 else f"HTTP {response.status_code}",
            }
    except httpx.TimeoutException:
        return {"ok": False, "status": 0, "url": url, "content_type": "",
                "text": "", "headers": {}, "error": f"Request timeout after {timeout}s"}
    except httpx.ConnectError as e:
        return {"ok": False, "status": 0, "url": url, "content_type": "",
                "text": "", "headers": {}, "error": f"Connection failed: {e}"}
    except Exception as e:
        return {"ok": False, "status": 0, "url": url, "content_type": "",
                "text": "", "headers": {}, "error": f"Fetch error: {type(e).__name__}: {e}"}


# ═══════════════════════════════════════════════════════════════
# Playwright Routing Hook — Social Media SPA / SSR domains
# ═══════════════════════════════════════════════════════════════

def _is_playwright_required(url: str) -> bool:
    """Check if URL domain requires Playwright browser rendering."""
    try:
        hostname = urlparse(url).hostname or ""
        return any(d in hostname for d in PLAYWRIGHT_REQUIRED_DOMAINS)
    except Exception:
        return False


async def _fetch_via_playwright(url: str, timeout: float = DEFAULT_TIMEOUT) -> dict:
    """
    Fetch fully-rendered DOM via Playwright browser pool.

    Uses the shared BrowserPool from szyg.platforms (same as Douyin/XHS adapters).
    Creates a fresh context with stealth injection, navigates, waits for network
    idle, and returns the rendered HTML.
    """
    # ── Failsafe: null-initialized refs for guaranteed cleanup ──
    context = None
    page = None

    try:
        from szyg.platforms.browser_pool import get_browser_pool
        from szyg.platforms.anti_detect import inject_stealth

        pool = get_browser_pool()
        await pool._ensure_browser()

        context = await pool._browser.new_context(
            user_agent=DEFAULT_USER_AGENT,
            viewport={"width": 1536, "height": 864},
            locale="zh-CN",
        )
        page = await context.new_page()

        await inject_stealth(page)
        await page.goto(url, wait_until="networkidle", timeout=timeout * 1000)
        # Extra settle time for SPA hydration
        await asyncio.sleep(2)
        html = await page.content()
        title = await page.title()
        final_url = page.url

        return {
            "ok": True,
            "status": 200,
            "url": final_url,
            "content_type": "text/html",
            "text": html,
            "headers": {},
            "error": "",
            "rendered_by": "playwright",
            "title_tag": title,
        }

    except ImportError as e:
        return {
            "ok": False, "status": 0, "url": url, "content_type": "",
            "text": "", "headers": {},
            "error": f"Playwright not available: {e}. Install: pip install playwright && playwright install chromium",
        }
    except Exception as e:
        return {
            "ok": False, "status": 0, "url": url, "content_type": "",
            "text": "", "headers": {},
            "error": f"Playwright fetch failed: {type(e).__name__}: {e}",
        }
    finally:
        # ── Guaranteed resource cleanup — null-safe, never throws ──
        if page is not None:
            try:
                await page.close()
            except Exception:
                pass
        if context is not None:
            try:
                await context.close()
            except Exception:
                pass


# ═══════════════════════════════════════════════════════════════
# SearXNG — Private Instance + Dynamic Registry + Retry
# ═══════════════════════════════════════════════════════════════

async def _fetch_searxng_instances() -> list[str]:
    """
    Fetch live SearXNG instances from the official searx.space registry.

    Returns a deduplicated list of working instance URLs sorted by
    reliability score (descending). Falls back to static list on failure.
    Cached for 1 hour.
    """
    global _searxng_cache

    # Return cached if fresh
    if (_searxng_cache["instances"] is not None and
            time.time() - _searxng_cache["fetched_at"] < _SEARXNG_CACHE_TTL):
        return _searxng_cache["instances"]

    instances = []

    try:
        import httpx
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                _SEARXNG_REGISTRY,
                headers={"User-Agent": DEFAULT_USER_AGENT},
            )
            resp.raise_for_status()
            data = resp.json()

        # Parse: instances.{url} — pick those with "network_type": "normal"
        # and good uptime. Sort by score descending.
        raw = data.get("instances", {})
        scored = []
        for inst_url, info in raw.items():
            if not isinstance(info, dict):
                continue
            # Prefer normal (clearnet), skip tor/i2p/onion
            if info.get("network_type") != "normal":
                continue
            # Skip if heavily rate-limited or down
            if info.get("generator") != "searxng":
                continue
            score = float(info.get("score", 0) or 0)
            # Minimum quality threshold
            if score < 0.5:
                continue
            timed_out = info.get("timed_out", True)
            if timed_out:
                continue
            scored.append((score, inst_url.rstrip("/")))

        scored.sort(key=lambda x: x[0], reverse=True)
        instances = [url for _, url in scored[:15]]  # Top 15

        if instances:
            _searxng_cache["instances"] = instances
            _searxng_cache["fetched_at"] = time.time()
            return instances
    except Exception:
        logger.warning("Failed to fetch SearXNG registry, using static fallbacks")

    # Fall back to static list
    instances = list(_SEARXNG_STATIC_FALLBACKS)
    _searxng_cache["instances"] = instances
    _searxng_cache["fetched_at"] = time.time()
    return instances


async def _searxng_search_with_retry(
    query: str,
    instances: list[str],
    count: int = 10,
    max_retries_per_instance: int = 3,
) -> dict:
    """
    Search across SearXNG instances with aggressive retry logic.

    Strategy:
      1. Try each instance in order (best score first).
      2. On 429 (rate limit) or 403 (blocked): retry up to N times on that instance
         with exponential backoff, then move to the next.
      3. On network error: immediately move to next instance.
      4. On success: return results immediately.

    Args:
        query: Search query
        instances: Ordered list of instance URLs
        count: Number of results to return
        max_retries_per_instance: Max retries per instance (for 429/403)

    Returns:
        {"query": str, "engine": str, "count": int, "results": list, "via": str}
        or {"error": str, ...}
    """
    import httpx

    count = max(1, min(count, 20))
    last_error = ""
    tried = []

    for base_url in instances:
        search_url = f"{base_url}/search"
        tried.append(base_url)

        for attempt in range(max_retries_per_instance):
            try:
                async with httpx.AsyncClient(timeout=12.0) as client:
                    resp = await client.get(
                        search_url,
                        params={
                            "q": query,
                            "format": "json",
                            "categories": "general",
                            "language": "zh-CN",
                            "pageno": 1,
                        },
                        headers={"User-Agent": DEFAULT_USER_AGENT},
                    )

                    if resp.status_code in (429, 403):
                        wait = 2 ** attempt  # 1s, 2s, 4s
                        last_error = f"HTTP {resp.status_code} from {base_url} (attempt {attempt + 1})"
                        await asyncio.sleep(wait)
                        continue  # Retry this instance

                    resp.raise_for_status()
                    data = resp.json()

                # Parse results
                results = []
                for r in (data.get("results", []) or [])[:count]:
                    results.append({
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "description": (r.get("content", "") or r.get("snippet", ""))[:500],
                        "engine": ", ".join(r.get("engines", [])) if isinstance(r.get("engines"), list) else "",
                    })

                # Some SearXNG instances return 200 with empty results on error
                if results:
                    return {
                        "query": query,
                        "engine": "searxng",
                        "count": len(results),
                        "results": results,
                        "via": base_url,
                        "tried": len(tried),
                    }
                else:
                    last_error = f"Empty results from {base_url}"
                    break  # Move to next instance

            except httpx.TimeoutException:
                last_error = f"Timeout from {base_url}"
                break  # Move to next instance
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (429, 403):
                    wait = 2 ** attempt
                    last_error = f"HTTP {e.response.status_code} from {base_url} (attempt {attempt + 1})"
                    await asyncio.sleep(wait)
                    continue
                last_error = f"HTTP {e.response.status_code} from {base_url}"
                break
            except Exception as e:
                last_error = f"{type(e).__name__}: {e} from {base_url}"
                break  # Move to next instance

    return {
        "error": f"All {len(tried)} SearXNG instances failed. Last error: {last_error}",
        "query": query,
        "results": [],
        "tried": len(tried),
    }


# ═══════════════════════════════════════════════════════════════
# Tool: web_fetch — raw HTTP GET
# ═══════════════════════════════════════════════════════════════

@server.tool(
    "web_fetch",
    "Fetch a URL and return raw response metadata + first 5000 chars of body. "
    "Use to inspect status codes, headers, and page content without full scraping."
)
async def web_fetch(
    url: str,
    custom_headers: str = "",
    timeout: float = DEFAULT_TIMEOUT,
) -> dict:
    """
    Raw HTTP GET — returns status, headers, and first 5000 chars of body.

    Args:
        url: Target URL to fetch
        custom_headers: JSON-encoded custom headers, e.g. '{"Authorization":"Bearer xyz"}'
        timeout: Request timeout in seconds (default 30)
    """
    headers = None
    if custom_headers:
        try:
            headers = json.loads(custom_headers)
        except json.JSONDecodeError:
            return {"error": f"Invalid JSON in custom_headers: {custom_headers[:100]}"}

    # Route through Playwright for SPA/SSR domains
    if _is_playwright_required(url):
        result = await _fetch_via_playwright(url, timeout=timeout)
    else:
        result = await _fetch_url(url, headers=headers, timeout=timeout)

    # Truncate body for tool response
    if len(result.get("text", "")) > 5000:
        result["text"] = result["text"][:5000] + "\n\n[Truncated — use web_scrape for full content]"
    result["text_length"] = len(result.get("text", ""))
    return result


# ═══════════════════════════════════════════════════════════════
# Tool: web_scrape — HTML → clean text/markdown
# ═══════════════════════════════════════════════════════════════

@server.tool(
    "web_scrape",
    "Scrape a URL and extract clean text or markdown content. "
    "Uses BeautifulSoup + html2text for robust parsing (no fragile regex). "
    "Social media creator domains auto-route through Playwright for rendered DOM. "
    "Use 'text' mode for LLM consumption, 'markdown' to preserve links/headings/structure."
)
async def web_scrape(
    url: str,
    extract_mode: str = "text",
    timeout: float = DEFAULT_TIMEOUT,
    force_playwright: bool = False,
) -> dict:
    """
    Smart web scraper — HTML → clean text or markdown via BeautifulSoup + html2text.

    Args:
        url: Target URL to scrape
        extract_mode: "text" for plain text (best for LLM consumption),
                      "markdown" to preserve links, headings, lists, code blocks
        timeout: Request timeout in seconds (default 30)
        force_playwright: Force Playwright rendering even for non-social-media URLs

    Returns:
        dict with "url", "title", "content", "length", "mode", "renderer"
    """
    if extract_mode not in ("text", "markdown"):
        return {"error": f"Invalid extract_mode: '{extract_mode}'. Use 'text' or 'markdown'."}

    # Route through Playwright for social media domains (or when forced)
    use_playwright = force_playwright or _is_playwright_required(url)

    if use_playwright:
        result = await _fetch_via_playwright(url, timeout=timeout)
    else:
        result = await _fetch_url(url, timeout=timeout)

    if not result["ok"]:
        return {
            "error": result["error"],
            "url": url,
            "status": result["status"],
            "renderer": "playwright" if use_playwright else "httpx",
        }

    content_type = result.get("content_type", "")
    if "text/html" not in content_type and "application/xhtml" not in content_type:
        # Non-HTML — return raw text as-is
        return {
            "url": result["url"],
            "title": result.get("title_tag", ""),
            "content": result["text"][:SCRAPE_TEXT_LIMIT],
            "length": len(result["text"]),
            "mode": "raw",
            "content_type": content_type,
            "renderer": "playwright" if use_playwright else "httpx",
        }

    # ── Parse with BeautifulSoup + html2text ──
    if extract_mode == "markdown":
        content = _html_to_markdown(result["text"], base_url=result["url"])
    else:
        content = _html_to_text(result["text"])

    # Extract title from parsed HTML
    soup = _parse_html(result["text"])
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""

    if len(content) > SCRAPE_TEXT_LIMIT:
        content = content[:SCRAPE_TEXT_LIMIT] + "\n\n[Content truncated at 100K characters]"

    return {
        "url": result["url"],
        "title": title,
        "content": content,
        "length": len(content),
        "mode": extract_mode,
        "renderer": "playwright" if use_playwright else "httpx",
    }


# ═══════════════════════════════════════════════════════════════
# Tool: web_search_brave — Brave Search API
# ═══════════════════════════════════════════════════════════════

@server.tool(
    "web_search_brave",
    "Search the web using Brave Search API. Requires a Brave API key (free tier: 2000 queries/month). "
    "Get key: https://brave.com/search/api/"
)
async def web_search_brave(
    query: str,
    api_key: str = "",
    count: int = 10,
    country: str = "CN",
) -> dict:
    """
    Brave Search API wrapper. Returns web results with title, url, description.

    Args:
        query: Search query string
        api_key: Brave Search API key (or set env BRAVE_API_KEY)
        count: Number of results (1-20, default 10)
        country: Country code for results (default: CN)
    """
    key = api_key or os.environ.get("BRAVE_API_KEY", "")
    if not key:
        return {
            "error": "Brave API key required. Get one at https://brave.com/search/api/ "
                      "or use web_search (auto-routes to SearXNG if no key).",
            "results": [],
        }

    count = max(1, min(count, 20))

    try:
        import httpx
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": count, "country": country},
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                    "X-Subscription-Token": key,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        results = []
        for r in (data.get("web", {}).get("results", []) or [])[:count]:
            results.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "description": (r.get("description", "") or "")[:500],
            })

        return {
            "query": query,
            "engine": "brave",
            "count": len(results),
            "results": results,
        }
    except Exception as e:
        return {"error": f"Brave search failed: {e}", "query": query, "results": []}


# ═══════════════════════════════════════════════════════════════
# Tool: web_search_searxng — SearXNG JSON API (resilient)
# ═══════════════════════════════════════════════════════════════

@server.tool(
    "web_search_searxng",
    "Search the web using SearXNG meta-search engine (privacy-respecting, no API key needed). "
    "Priority: ① $SEARXNG_URL env var (private instance) → ② Live registry from searx.space → "
    "③ Static fallbacks. Aggressive retry across instances on 429/403."
)
async def web_search_searxng(
    query: str,
    instance_url: str = "",
    count: int = 10,
) -> dict:
    """
    SearXNG JSON API wrapper with resilient multi-instance routing.

    Args:
        query: Search query string
        instance_url: Specific SearXNG instance URL (overrides env var and registry).
                      Use if you have your own private instance.
        count: Number of results (1-20, default 10)

    Returns:
        dict with "query", "engine", "count", "results", "via"
    """
    # ── Resolve instance list ──
    if instance_url:
        instances = [instance_url.rstrip("/")]
    elif _SEARXNG_PRIVATE:
        instances = [_SEARXNG_PRIVATE]
    else:
        # Fetch dynamic list from searx.space registry
        instances = await _fetch_searxng_instances()
        if not instances:
            return {
                "error": "No SearXNG instances available — registry fetch failed and no static fallbacks",
                "query": query,
                "results": [],
            }

    return await _searxng_search_with_retry(
        query=query,
        instances=instances,
        count=count,
    )


# ═══════════════════════════════════════════════════════════════
# Tool: web_search — auto-router (Brave → SearXNG)
# ═══════════════════════════════════════════════════════════════

@server.tool(
    "web_search",
    "Search the web using the best available engine. "
    "Auto-routes: Brave Search (if BRAVE_API_KEY set) → SearXNG (private/registry/fallback). "
    "Use this as the primary search tool — it picks the right backend automatically."
)
async def web_search(
    query: str,
    engine: str = "auto",
    api_key: str = "",
    count: int = 10,
) -> dict:
    """
    Web search with automatic engine selection.

    Args:
        query: Search query string
        engine: "auto" (default), "brave", or "searxng"
        api_key: Brave API key (optional, auto-detected from env BRAVE_API_KEY)
        count: Number of results (1-20, default 10)
    """
    count = max(1, min(count, 20))

    # Determine engine
    if engine == "auto":
        brave_key = api_key or os.environ.get("BRAVE_API_KEY", "")
        engine = "brave" if brave_key else "searxng"

    if engine == "brave":
        return await web_search_brave(query=query, api_key=api_key, count=count)
    else:
        return await web_search_searxng(query=query, count=count)


# ═══════════════════════════════════════════════════════════════
# Tool: web_sitemap — extract URLs from sitemap.xml
# ═══════════════════════════════════════════════════════════════

@server.tool(
    "web_sitemap",
    "Fetch and parse a sitemap.xml to extract all listed URLs. "
    "Useful for discovering all pages on a site for bulk scraping."
)
async def web_sitemap(
    url: str,
    timeout: float = 30.0,
) -> dict:
    """
    Extract all URLs from a sitemap.xml file.

    Args:
        url: URL to sitemap.xml (e.g., https://example.com/sitemap.xml)
        timeout: Request timeout in seconds (default 30)
    """
    result = await _fetch_url(url, timeout=timeout)
    if not result["ok"]:
        return {"error": result["error"], "url": url, "urls": []}

    text = result["text"]

    # Parse <url><loc>...</loc></url> from sitemap XML
    locs = re.findall(r'<loc>(.*?)</loc>', text, re.IGNORECASE)

    # Also check for sitemap index files
    sitemaps = re.findall(
        r'<sitemap>.*?<loc>(.*?)</loc>.*?</sitemap>',
        text, re.DOTALL | re.IGNORECASE
    )

    return {
        "url": url,
        "type": "sitemap_index" if sitemaps else "sitemap",
        "url_count": len(locs),
        "urls": locs[:500],  # Cap at 500 URLs
        "sub_sitemaps": sitemaps[:20] if sitemaps else [],
    }


if __name__ == "__main__":
    server.run()
