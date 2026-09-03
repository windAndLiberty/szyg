# 🔌 API 接口规格 索引

> 本目录存放域灵系统所有 API 路由的接口契约文档。Elite_Coder 编码时必须严格遵守此处的规格。

## 已填充文档

| 文件 | 对应源码 | 内容 | 状态 |
|------|----------|------|------|
| `welcome-case-cards-spec.md` | `hermes_chat.py` | 欢迎页精选案例卡片 API | ✅ 已填充 |

## 待填充的核心 API

以下路由模块已在后端实现，接口契约文档待补充：

| 路由文件 | 路由前缀 | 职责 |
|----------|----------|------|
| `auth_routes.py` | `/api/auth` | 认证/登录/JWT |
| `hermes_chat.py` | `/api/hermes` | 超级员工对话 SSE |
| `conversation_routes.py` | `/api/conversations` | 对话持久化 CRUD |
| `publisher_routes.py` | `/api/publisher` | 多平台发布 |
| `agent_routes.py` | `/api/agents` | 智能体管理 |
| `scheduler_routes.py` | `/api/scheduler` | 调度任务 |
| `acquisition_routes.py` | `/api/acquisition` | 获客/截流 |
| `skills_routes.py` | `/api/skills` | 技能市场 |
| `platform_routes.py` | `/api/platforms` | 平台操作 |

## 规约

- 每份 API 规格必须包含：路径、方法、请求体 Schema、响应体 Schema、错误码、认证要求
- 接口变更时必须先更新此目录文档，再修改代码
