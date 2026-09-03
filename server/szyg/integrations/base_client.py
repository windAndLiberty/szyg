"""集成客户端基类，提供通用功能."""

from typing import Any

import httpx

from szyg.models.common import IntegrationError


class BaseClient:
    """集成客户端基类"""

    def __init__(self, base_url: str, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def _post(
        self, path: str, json: dict = None, **kwargs
    ) -> httpx.Response:
        """发送POST请求"""
        try:
            response = await self.client.post(
                f"{self.base_url}{path}", json=json, **kwargs
            )
            response.raise_for_status()
            return response
        except httpx.TimeoutException:
            raise IntegrationError(f"Request timeout after {self.timeout}s")
        except httpx.HTTPStatusError as e:
            raise IntegrationError(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            raise IntegrationError(f"Request failed: {e}")

    async def _get(
        self, path: str, params: dict = None, **kwargs
    ) -> httpx.Response:
        """发送GET请求"""
        try:
            response = await self.client.get(
                f"{self.base_url}{path}", params=params, **kwargs
            )
            response.raise_for_status()
            return response
        except httpx.TimeoutException:
            raise IntegrationError(f"Request timeout after {self.timeout}s")
        except httpx.HTTPStatusError as e:
            raise IntegrationError(f"HTTP error: {e.response.status_code}")
        except Exception as e:
            raise IntegrationError(f"Request failed: {e}")

    async def close(self):
        """关闭HTTP客户端"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
