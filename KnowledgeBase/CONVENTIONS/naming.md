# 📛 命名约定

## 后端 (Python / server/)

| 类型 | 规则 | 示例 |
|------|------|------|
| 文件 | snake_case | `auth_routes.py`, `scheduler_engine.py` |
| 路由模块 | `{name}_routes.py` 或 `{name}_endpoint.py` | `platform_routes.py`, `image_endpoint.py` |
| 引擎模块 | `{name}_engine.py` | `pipeline_engine.py`, `intercept_engine.py` |
| 类 | PascalCase | `TenantMiddleware`, `UserInDB` |
| 函数 | snake_case | `get_current_tenant()`, `create_access_token()` |
| 私有 | _前缀 | `_hash_pw()`, `_get_conn()`, `_try_include()` |
| 常量 | UPPER_SNAKE | `SECRET_KEY`, `DEFAULT_TENANT`, `VERSION` |
| Pydantic 模型 | PascalCase | `LoginRequest`, `Token`, `User` |

## 前端 (Vue / web/)

| 类型 | 规则 | 示例 |
|------|------|------|
| 页面文件 | PascalCase.vue | `ContentStudio.vue`, `Login.vue` |
| Shell 文件 | PascalCase + Shell.vue | `ContentShell.vue`, `MarketingShell.vue` |
| 路由 path | kebab-case | `/content/video-editor` |
| 组件名 | PascalCase | `<AppLayout />` |
| JS 变量 | camelCase | `const token = ...` |
| CSS 类 | kebab-case | `.tech-theme`, `.sidebar-item` |

## 数据库 (SQLite)

| 类型 | 规则 | 示例 |
|------|------|------|
| 表名 | snake_case 复数 | `users`, `conversations` |
| 列名 | snake_case | `hashed_password`, `oem_id`, `created_at` |
| 索引 | idx_{table}_{columns} | `idx_users_username` |

## 目录命名

| 位置 | 规则 | 示例 |
|------|------|------|
| 后端模块 | snake_case | `platforms/`, `agent_core/` |
| 前端目录 | kebab-case 或 camelCase | `pages/`, `components/`, `stores/` |
| 数据目录 | snake_case | `volcengine_output/`, `comfyui_output/` |
