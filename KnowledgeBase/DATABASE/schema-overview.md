# 🗄️ 全局数据库 Schema 概览

## 数据库清单

| 数据库 | 路径 | 引擎 | 用途 |
|--------|------|------|------|
| auth.db | `data/auth.db` | SQLite | 用户认证与授权 |
| knowledge.db | `data/knowledge.db` | SQLite + FTS | 知识库文档分块与全文检索 |
| memory.db | `data/memory.db` | SQLite + FTS | 长期记忆 (向量预留 + FTS) |
| sop.db | `data/sop.db` | SQLite | SOP 工作流定义 |

## 连接方式

```python
# 标准连接模式 (auth.py 示例)
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row  # 行工厂 → 字典式访问
```

- 无 ORM，直接使用 `sqlite3` 标准库
- 每次操作创建新连接 (SQLite 轻量级，无需连接池)
- `row_factory = sqlite3.Row` 确保结果可按列名访问

## 初始化策略

- **auth.db**: 模块导入时自动 `_init_db()` + `_default_admin()` (admin/admin123)
- **knowledge.db / memory.db / sop.db**: 按需创建表
- **迁移**: 使用 `ALTER TABLE ... ADD COLUMN` + `try/except sqlite3.OperationalError` 模式

## 多租户数据隔离

- 默认租户 (`"default"`): 直接使用 `data/` 目录
- 非默认租户: `data/tenants/{tenant_id}/` 目录下独立数据文件
- 通过 `get_tenant_data_dir()` / `get_tenant_data_file()` 获取路径
