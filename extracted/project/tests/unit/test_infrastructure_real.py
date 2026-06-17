"""
「域灵」数字员工系统 - 基础设施模块真单元测试
"""

import pytest

from yuling.infrastructure.database import get_sqlite_connection
from yuling.infrastructure.http_client import get_http_client, get_sync_client
from yuling.infrastructure.logger import configure_logging, get_logger


class TestDatabase:
    """数据库连接模块测试。"""

    def test_get_sqlite_connection_memory(self):
        """:memory: 数据库应能正常连接。"""
        conn = get_sqlite_connection(":memory:")
        assert conn is not None
        # row_factory 应被设置为 Row
        cursor = conn.execute("SELECT 1 AS test_col")
        row = cursor.fetchone()
        assert row["test_col"] == 1
        conn.close()

    def test_get_sqlite_connection_file(self, tmp_path):
        """文件数据库应能正常创建。"""
        db_path = str(tmp_path / "test.db")
        conn = get_sqlite_connection(db_path)
        conn.execute("CREATE TABLE IF NOT EXISTS t (id INTEGER)")
        conn.commit()
        conn.close()
        assert (tmp_path / "test.db").exists()

    def test_row_factory_is_set(self):
        """返回的连接应有 row_factory=Row。"""
        import sqlite3
        conn = get_sqlite_connection(":memory:")
        assert conn.row_factory == sqlite3.Row
        conn.close()


class TestHttpClient:
    """HTTP客户端模块测试。"""

    @pytest.mark.asyncio
    async def test_get_http_client_returns_async_client(self):
        """get_http_client 应返回 httpx.AsyncClient。"""
        import httpx
        client = await get_http_client()
        assert isinstance(client, httpx.AsyncClient)

    def test_get_sync_client_returns_client(self):
        """get_sync_client 应返回 httpx.Client。"""
        import httpx
        client = get_sync_client()
        assert isinstance(client, httpx.Client)


class TestLogger:
    """日志模块测试。"""

    def test_get_logger_returns_logger(self):
        """get_logger 应返回 structlog logger。"""
        logger = get_logger("test_module")
        assert logger is not None

    def test_get_logger_different_names(self):
        """不同名字应返回不同的 logger。"""
        logger_a = get_logger("module_a")
        logger_b = get_logger("module_b")
        assert logger_a is not None
        assert logger_b is not None

    def test_configure_logging_json(self):
        """JSON 格式日志配置不应崩溃。"""
        configure_logging(json_format=True, log_level="DEBUG")

    def test_configure_logging_console(self):
        """控制台彩色日志配置不应崩溃。"""
        configure_logging(json_format=False, log_level="INFO")

    def test_configure_and_log(self):
        """配置后应能正常记录日志。"""
        configure_logging(json_format=False, log_level="DEBUG")
        logger = get_logger("test")
        logger.info("test message from unit test", module="test")
