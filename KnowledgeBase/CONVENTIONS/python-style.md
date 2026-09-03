# 🐍 Python 编码风格 (server/)

## 工具链

- **Linter**: ruff (line-length=100, target-version=py312)
- **测试**: pytest + pytest-asyncio (asyncio_mode=auto)
- **包管理**: uv (禁止直接使用 pip install)
- **Python 版本**: 3.12+

## 命名约定

| 类型 | 风格 | 示例 |
|------|------|------|
| 模块/文件 | snake_case | `auth_routes.py` |
| 类 | PascalCase | `TenantMiddleware` |
| 函数/变量 | snake_case | `get_current_tenant()` |
| 常量 | UPPER_SNAKE | `SECRET_KEY`, `DEFAULT_TENANT` |
| 私有函数 | _prefix | `_hash_pw()`, `_get_conn()` |
| Pydantic 模型 | PascalCase | `UserInDB`, `LoginRequest` |

## FastAPI 路由规范

- 每个路由模块导出 `router = APIRouter()`
- 使用 Pydantic BaseModel 定义请求/响应体
- 路由前缀在 `app.py` 的 `include_router()` 处统一指定
- 可选路由使用 `_try_include()` 模式，ImportError 时优雅降级

## 异步规范

- I/O 操作 (HTTP/DB/文件) 使用 `async def`
- SQLite 操作使用同步 `sqlite3` (不在 async 函数中阻塞事件循环时可直接用)
- 后台循环任务使用 `asyncio` (如 scheduler_engine)

## 导入顺序

```python
# 1. 标准库
import os, logging
from datetime import datetime

# 2. 第三方库
from fastapi import APIRouter
from pydantic import BaseModel

# 3. 项目内部
from szyg.auth import get_current_user
from szyg.tenant import get_current_tenant
```

## 错误处理

- 路由层使用 `HTTPException` 抛出 HTTP 状态码
- 引擎层使用自定义异常或日志记录
- 可选路由加载失败时 `logger.warning()` 并跳过，不阻塞启动
