# 🔒 认证/鉴权/租户隔离模型

## 1. 认证 (Authentication)

### 机制: JWT + PBKDF2-SHA256

| 配置项 | 值 |
|--------|-----|
| 算法 | HS256 |
| Secret Key | 环境变量 `SZYG_SECRET_KEY` (默认: `dev-secret-change-in-production`) |
| Token 有效期 | 7 天 (10080 分钟) |
| 密码哈希 | PBKDF2-SHA256, 600000 iterations |
| 存储 | `data/auth.db` → `users` 表 |

### 登录流程（后端 API 保留，前端不再有登录页）

```
POST /api/auth/login { username, password }
  → authenticate(username, password)
  → 验证密码 (PBKDF2)
  → 生成 JWT (sub=user_id, username, exp)
  → 返回 { access_token, token_type, user }
```

### 前端自动认证策略

- **无登录页**：应用启动时直接进入功能页面，不经过登录流程。
- 应用启动时自动使用默认管理员凭据 (`admin` / `admin123`) 调用 `POST /api/auth/login` 获取 JWT。
- 获取的 token 存入 `localStorage.setItem('token', access_token)`。
- 用户信息存入 `localStorage.setItem('user', JSON.stringify(user))`。
- axios 拦截器自动附加 `Authorization: Bearer {token}`。
- 若 token 过期（401 响应），自动重新获取 token，不跳转登录页。

### 路由守卫

```javascript
// Vue Router beforeEach
// 不再检查 token 或重定向到 /login
// 所有路由直接放行
next()
```

## 2. 授权 (Authorization)

### 角色

| 角色 | 权限 |
|------|------|
| `user` | 访问业务功能 (内容/营销/工作流/知识库/数据洞察) |
| `admin` | `user` 权限 + 品牌配置 + 团队管理 + 计费管理 |

### 接口保护

- 前端: `meta.requiresAdmin: true` 路由守卫
- 后端: 路由内检查 `user.role == "admin"` (需在路由实现中补充)

## 3. 租户隔离 (Multi-Tenancy)

### 机制: ContextVar + ASGI Middleware

```
HTTP 请求进入
  │
  ▼
TenantMiddleware.__call__
  │  解析 X-OEM-ID header
  │  set_current_tenant(tenant_id)
  ▼
路由处理 (当前协程内 get_current_tenant() 可用)
  │
  ▼
get_tenant_data_dir() → data/tenants/{tenant_id}/
  │
  ▼
请求结束 → ContextVar 自动重置
```

### 租户解析优先级

1. `X-OEM-ID` HTTP header
2. `?oem_id` query 参数
3. JWT token claim (`oem_id` 或 `tenant`)
4. 默认值: `"default"`

### 数据隔离

| 租户 | 数据目录 |
|------|----------|
| `default` | `data/` (根目录) |
| `{tenant_id}` | `data/tenants/{tenant_id}/` (子目录) |

### 用户与租户绑定

- `users.oem_id` 字段关联用户所属租户
- 创建用户时可指定 `oem_id`
- 同一用户名在不同租户下可重复 (需扩展唯一约束)

## 4. 安全注意事项

- ⚠️ `SECRET_KEY` 默认值仅用于开发，生产环境必须设置环境变量
- ⚠️ CORS 配置为 `allow_origins=["*"]`，生产环境应限制来源
- ⚠️ `config.yaml` 中包含火山引擎 API Key，生产环境应使用 `${VAR}` 引用
- ⚠️ 默认管理员密码 `admin123`，前端自动认证使用此凭据，生产环境应修改并实现真正的认证流程
