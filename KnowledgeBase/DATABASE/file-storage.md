# 📁 文件存储规约

## data/ 目录结构

```
data/
├── auth.db                         # 用户认证数据库
├── knowledge.db                    # 知识库数据库
├── memory.db                       # 长期记忆数据库
├── sop.db                          # SOP 工作流数据库
├── agents.json                     # 智能体配置
├── announcements.json              # 公告数据
├── hub_tools.json                  # 工具Hub配置
├── oem.json                        # OEM/白标配置
├── audit/                          # 审计日志
│   ├── 01_logged_in.png
│   ├── 02_publish_page.png
│   └── publish_dom.json
├── comfyui_output/                 # ComfyUI 图像输出
├── conversations/                  # 对话历史持久化
│   ├── {conversation_id}.json
├── frontend/                       # 前端页面持久化数据
│   ├── agents.json
│   ├── chart_data.json
│   ├── content_assets.json
│   └── ... (22+ JSON 文件)
└── volcengine_output/              # 火山引擎 AIGC 产物
    ├── images/
    ├── videos/
    └── audio/
```

## 多租户文件隔离

```
data/
├── tenants/
│   ├── {tenant_id}/
│   │   ├── auth.db                 # 租户独立用户库 (可选)
│   │   ├── knowledge.db
│   │   ├── memory.db
│   │   └── ...
│   └── ...
```

- 默认租户 (`"default"`) 直接使用 `data/` 根目录
- 非默认租户使用 `data/tenants/{tenant_id}/` 子目录
- 路径获取: `get_tenant_data_dir()` / `get_tenant_data_file(filename)`

## 静态文件服务

| 挂载路径 | 物理目录 | 用途 |
|----------|----------|------|
| `/api/files/volcengine_output` | `data/volcengine_output/` | AIGC 产物访问 |
| `/assets` | `web/dist/assets/` | 前端静态资源 |

## 原子文件写入

使用 `server/szyg/atomic_file.py` 确保文件写入原子性：

```python
from szyg.atomic_file import atomic_write
atomic_write(path, content)  # 先写临时文件再 rename，防止写入中断导致文件损坏
```
