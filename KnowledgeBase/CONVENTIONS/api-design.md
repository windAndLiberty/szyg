# 🔌 API 设计规范

## 基本原则

- RESTful 风格，资源名复数 (`/api/agents`, `/api/platforms`)
- 所有 API 路径以 `/api/` 开头 (可选路由 `/v1/` 除外)
- 使用标准 HTTP 方法: GET / POST / PUT / DELETE / PATCH

## 响应格式

### 成功响应

```json
{
  "data": { ... },
  "message": "success"
}
```

或直接返回数据对象/列表（FastAPI 默认行为）。

### 错误响应

```json
{
  "detail": "错误描述信息"
}
```

FastAPI `HTTPException` 默认格式。

## 认证

- 除 `/api/auth/login` 和 `/api/health` 外，所有接口需要 JWT
- 请求头: `Authorization: Bearer {token}`
- Token 有效期: 7 天 (60 * 24 * 7 分钟)
- 算法: HS256

## 多租户

- 请求头: `X-OEM-ID: {tenant_id}` (可选)
- 缺省租户: `"default"`
- 后端通过 `TenantMiddleware` 自动解析并设置上下文

## 分页

- Query 参数: `?page=1&page_size=20`
- 响应: `{ "items": [...], "total": 100, "page": 1, "page_size": 20 }`

## SSE (Server-Sent Events)

- AI 对话/流式响应使用 `sse-starlette`
- Content-Type: `text/event-stream`
- 事件格式: `data: {json}\n\n`
