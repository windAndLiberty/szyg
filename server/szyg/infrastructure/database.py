"""数据库连接管理。"""

import sqlite3


def get_sqlite_connection(db_path: str) -> sqlite3.Connection:
    """创建带row_factory的SQLite连接。

    Args:
        db_path: 数据库文件路径。

    Returns:
        sqlite3.Connection: 配置好的SQLite连接。
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn
