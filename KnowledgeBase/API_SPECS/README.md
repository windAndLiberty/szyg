# 🔌 API 接口规格 索引

> 本目录存放域灵系统所有 API 路由的接口契约文档。Elite_Coder 编码时必须严格遵守此处的规格。

## 文档列表

| 文件 | 对应源码 | 路由前缀 | 状态 |
|------|----------|----------|------|
| `auth-routes.md` | `auth_routes.py` | `/api/auth` | 待填充 |
| `infra-routes.md` | `infra_routes.py` | `/api/infra` | 待填充 |
| `platform-routes.md` | `platform_routes.py` | `/api/platforms` | 待填充 |
| `publisher-routes.md` | `publisher_routes.py` | `/api/publisher` | 待填充 |
| `staff-routes.md` | `staff_routes.py` | `/api/staff` | 待填充 |
| `data-routes.md` | `data_routes.py` | `/api/data` | 待填充 |
| `skills-routes.md` | `skills_routes.py` | `/api/skills` | 待填充 |
| `scheduler-routes.md` | `scheduler_routes.py` | `/api/scheduler` | 待填充 |
| `acquisition-routes.md` | `acquisition_routes.py` | `/api/acquisition` | 待填充 |
| `chat-routes.md` | `chat.py` + `hermes_chat.py` | `/api/chat` + `/api/hermes` | 待填充 |
| `frontend-routes.md` | `frontend_routes.py` | `/api/frontend` | 待填充 |

## 规约

- 每份 API 规格必须包含：路径、方法、请求体 Schema、响应体 Schema、错误码、认证要求
- 接口变更时必须先更新此目录文档，再修改代码
