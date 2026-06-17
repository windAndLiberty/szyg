"""共享HTTP客户端。"""

import httpx

_http_client: httpx.AsyncClient | None = None
_sync_client: httpx.Client | None = None


async def get_http_client() -> httpx.AsyncClient:
    """获取共享异步HTTP客户端。

    Returns:
        httpx.AsyncClient: 共享异步HTTP客户端实例。
    """
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient()
    return _http_client


def get_sync_client() -> httpx.Client:
    """获取共享同步HTTP客户端。

    Returns:
        httpx.Client: 共享同步HTTP客户端实例。
    """
    global _sync_client
    if _sync_client is None:
        _sync_client = httpx.Client()
    return _sync_client
