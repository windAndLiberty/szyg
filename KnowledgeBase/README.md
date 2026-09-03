# 📚 域灵知识库 — 唯一真理源 (Single Source of Truth)

> 本目录是整个多智能体协作系统的**设计终点**。所有智能体在动手编码前，**必须**先读取本目录中对应的规格文档。

## 📖 导航索引

| 目录 | 用途 | 写入者 | 目标读者 |
|------|------|--------|----------|
| `PRD/` | 产品需求文档（业务层） | Architect_Agent | 全体智能体 |
| `DESIGN/` | 全局设计系统 + **功能设计方案** | Architect_Agent | 全体前端智能体 |
| `ARCHITECTURE/` | 系统架构设计（技术层 + 专项规范） | Architect_Agent | Elite_Coder |
| `API_SPECS/` | API 接口契约 | Architect_Agent | Elite_Coder 严格遵守 |
| `DATABASE/` | 数据模型与存储设计 | Architect_Agent | Elite_Coder |
| `CONVENTIONS/` | 工程编码规约 | Architect_Agent | 全体智能体遵守 |
| `DECISIONS/` | 架构决策记录 (ADR) | Architect_Agent | 全体智能体参考 |

## 🏗️ 项目概要

- **项目名称**: 域灵 (szyg) — 智能矩阵运营系统
- **版本**: 1.0.0
- **定位**: 自托管 AI 工具平台，面向多平台内容营销自动化
- **对标**: 炼刀AI式超级员工自动化营销平台
- **技术栈**: Python 3.12 + FastAPI + Vue 3 + Element Plus + Electron + SQLite
- **核心引擎**: Hermes 超级员工 (brain_hermes.py) + 火山引擎方舟 LLM

## ⚠️ 铁律

1. **Architect_Agent 是唯一写入者**，其他智能体只读。
2. 需求变更时，**必须先更新本目录**，再动代码。
3. 文档精度要求：数据类型、错误码、文件边界必须明确定义，不留猜测空间。
4. 任何与本目录文档冲突的代码实现，视为 **目标偏移 (Mission Drift)**，需 QA_Guardian 标记。

## 🗺️ 关键文档速查

| 想了解... | 读这个 |
|-----------|-------|
| 系统整体要做什么 | `PRD/product-requirements.md` |
| 功能设计方案与路线图 | `DESIGN/functional-design.md` |
| 系统技术架构 | `ARCHITECTURE/system-overview.md` |
| 后端代码在哪 | `ARCHITECTURE/backend-structure.md` |
| 前端页面路由 | `ARCHITECTURE/frontend-structure.md` |
| UI长什么样 | `DESIGN/design-system.md` |
| 超级员工页面规格 | `DESIGN/page-super-agent.md` |
| 对话消息规范 | `ARCHITECTURE/specs/chat-message-ui.md` |
| 视频卡片规范 | `ARCHITECTURE/specs/chat-video-card.md` |
| 抖音搜索方案 | `ARCHITECTURE/specs/douyin-mcp-integration.md` |
| LLM输出规则 | `CONVENTIONS/llm-output-rules.md` |
| 为什么用火山引擎 | `DECISIONS/ADR-001-volcengine-as-default-llm.md` |
