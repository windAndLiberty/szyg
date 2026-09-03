# 📋 SQLite 表结构详细定义

## 1. auth.db — 用户认证

### users 表

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | 用户 ID |
| username | TEXT | UNIQUE NOT NULL | 用户名 |
| hashed_password | TEXT | NOT NULL | 密码哈希 (PBKDF2-SHA256, 600000 iterations) |
| role | TEXT | DEFAULT 'user' | 角色: `user` / `admin` |
| email | TEXT | DEFAULT '' | 邮箱 |
| oem_id | TEXT | nullable | 租户 ID |
| is_active | INTEGER | DEFAULT 1 | 是否启用 (0=禁用) |
| created_at | TEXT | DEFAULT (datetime('now')) | 创建时间 |

**密码哈希格式**: `pbkdf2:sha256:600000:{salt}:{hex_hash}`

**默认管理员**: 首次初始化时自动创建 `admin / admin123`

## 2. knowledge.db — 知识库

> 待补充：文档分块表、FTS 虚拟表结构

## 3. memory.db — 长期记忆

> 待补充：记忆条目表、FTS 虚拟表结构

## 4. sop.db — SOP 工作流

> 待补充：SOP 定义表、步骤表结构

## Pydantic 模型映射

### User (auth.py)

```python
class User(BaseModel):
    id: int
    username: str
    role: str = "user"
    email: str = ""
    oem_id: str | None = None
    is_active: bool = True

class UserInDB(User):
    hashed_password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: User

class LoginRequest(BaseModel):
    username: str
    password: str
```
