# 🗄️ 数据模型与存储设计 索引

> 本目录存放域灵系统的数据库 Schema 和文件存储规约。

## 文档列表

| 文件 | 内容 | 状态 |
|------|------|------|
| `schema-overview.md` | 全局数据库 Schema 概览 | 待填充 |
| `sqlite-tables.md` | SQLite 表结构详细定义 | 待填充 |
| `file-storage.md` | 文件存储规约 (data/ 目录结构) | 待填充 |

## 数据库清单

| 数据库 | 路径 | 用途 |
|--------|------|------|
| auth.db | `data/auth.db` | 用户认证 (users 表) |
| knowledge.db | `data/knowledge.db` | 知识库 (文档分块 + FTS) |
| memory.db | `data/memory.db` | 长期记忆 (向量 + FTS) |
| sop.db | `data/sop.db` | SOP 工作流 |
