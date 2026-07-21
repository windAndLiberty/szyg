"""
Hermes Brain — deep integration of Hermes Agent v0.15 as szyg's AI core.
Replaces nanobot. Hermes runs invisibly, users interact via szyg WebUI.
"""
import os, sys, json, yaml
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
SERVER_DIR = PROJECT_ROOT / "server"
HERMES_HOME = PROJECT_ROOT / ".hermes"


class HermesBrain:
    """Hermes Agent deeply integrated as szyg's intelligence core."""

    def __init__(self):
        self.config = None
        self._setup_hermes_home()
        self._load_config()

    def _setup_hermes_home(self):
        """Initialize hermes home directory"""
        HERMES_HOME.mkdir(parents=True, exist_ok=True)
        (HERMES_HOME / "sessions").mkdir(exist_ok=True)
        (HERMES_HOME / "memory").mkdir(exist_ok=True)
        os.environ["HERMES_HOME"] = str(HERMES_HOME)

    def _load_config(self):
        """Load hermes YAML config"""
        config_path = PROJECT_ROOT / "hermes.yaml"
        if config_path.exists():
            with open(config_path, encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
        else:
            self.config = self._default_config()
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f)
        return self.config

    def _default_config(self):
        return {
            "model": {
                "default": "deepseek/deepseek-v4-pro",
                "provider": "deepseek",
                "base_url": "https://api.deepseek.com/v1",
            },
            "mcp_servers": {
                "publisher": {
                    "command": "python3",
                    "args": ["server/szyg/mcp_servers/publisher_mcp.py"],
                },
                "scheduler": {
                    "command": "python3",
                    "args": ["server/szyg/mcp_servers/scheduler_mcp.py"],
                },
                "tools": {
                    "command": "python3",
                    "args": ["server/szyg/mcp_servers/tools_mcp.py"],
                },
                "knowledge": {
                    "command": "python3",
                    "args": ["server/szyg/mcp_servers/knowledge_mcp.py"],
                },
                "agents": {
                    "command": "python3",
                    "args": ["server/szyg/mcp_servers/agents_mcp.py"],
                },
                "oem": {
                    "command": "python3",
                    "args": ["server/szyg/mcp_servers/oem_mcp.py"],
                },
                "platforms": {
                    "command": "python3",
                    "args": ["server/szyg/mcp_servers/platforms_mcp.py"],
                },
                "skills": {
                    "command": "python3",
                    "args": ["server/szyg/mcp_servers/skills_mcp.py"],
                },
                "video": {
                    "command": "python3",
                    "args": ["server/szyg/mcp_servers/video_mcp.py"],
                },
                "web_tools": {
                    "command": "python3",
                    "args": ["server/szyg/mcp_servers/web_tools_mcp.py"],
                },
            },
            "agent": {
                "name": "szyg",
                "icon": "⚡",
                "timezone": "Asia/Shanghai",
            },
        }

    def get_system_prompt(self) -> str:
        return """你是szyg智能矩阵运营系统的中枢AI助手，由Hermes Agent驱动。

你管理以下子系统:
- 📝 内容发布管道 (pub_*) — 创建/审核/排期/发布多平台内容
- 📡 平台自动化 (platform_*) — 管理抖音/小红书/微信登录态、发布内容到真实平台
- 🛠️ 技能工具集 (skill_*) — 办公文档(docx/xlsx/pptx/pdf) + 设计(canvas)
- 🎬 视频剪辑引擎 (video_*) — 裁剪/拼接/变速/字幕/混音/模板
- ⚡ 智能调度引擎 (sched_*) — cron/interval/manual定时任务，支持自动发布
- 🧰 工具市场 (tools_*) — AI工具目录/分类/搜索
- 📚 知识库 (kb_*) — FTS5全文检索/文档摄入/RAG
- 🤖 AI智能体 (agents_*) — 12个SME场景AI专家/提示词层级
- 🎨 品牌管理 (oem_*) — 主题切换/多租户配置

## 平台自动化发布流程
1. 使用 platform_list 查看所有平台状态
2. 使用 platform_status 确认目标平台已登录（如未登录，提示用户在Windows桌面扫码）
3. 通过 platform_publish_direct 一步发布内容
4. 或通过发布管道: pub_create → pub_submit → pub_approve → pub_publish
5. 使用 platform_health 进行全平台健康检查
6. 使用 platform_sessions 管理登录态有效期

## 内置营销技能 (Prompt-based Skills)
你内置以下营销专业技能，无需额外工具调用:

### 文案写作 (Copywriting)
精通转化率文案。原则: 清晰优于创意、利益优于功能、具体优于模糊。
- 标题: 用数字、痛点、对比、紧迫感
- 正文: PAS公式 (问题→激化→解决), AIDA公式 (注意→兴趣→欲望→行动)
- CTA: 用动词开头, 创造紧迫感, 减少摩擦

### 文案编辑 (Copy-editing)
审查和改进文案。检查: 清晰度、说服力、品牌语调、语法标点。
使用红笔标注模式: 删除线=建议删除, 粗体=建议添加, 注释=解释原因。

### 内容策略 (Content Strategy)
规划内容方向。核心概念:
- 内容支柱 (3-5个核心主题)
- 内容漏斗 (TOFU/MOFU/BOFU)
- 内容日历 (日/周/月规划)
- SEO + AI SEO 双优化

### AI搜索引擎优化 (AI SEO)
优化内容被ChatGPT/Perplexity/Claude等AI引用的概率:
- 结构化数据 (Schema Markup)
- 权威引用 (被其他可信源引用)
- 统计数据和具体数字
- 清晰的问答格式 (Q: / A:)
- 品牌监控: 在AI回答中被提及的频率

### 深度研究 (Deep Research)
系统性研究方法论:
- Phase 1: 广泛探索 (3-5个不同角度搜索)
- Phase 2: 深度挖掘 (针对每个角度深入)
- Phase 3: 交叉验证 (确认关键事实)
- Phase 4: 综合报告 (结构化输出+引用源)

Hermes Tool Search 让你按需加载工具schema，高效调用。
用自然语言理解用户意图，自动编排工具链完成任务。"""

    def get_mcp_servers(self) -> list[dict]:
        """Return legacy MCP declarations without implying they are running."""
        servers = self.config.get("mcp_servers", {})
        return [
            {
                "name": name,
                **config,
                "configured": True,
                "running": False,
                "execution_path": "legacy_stdio_config",
            }
            for name, config in servers.items()
        ]

    def get_status(self) -> dict:
        """Brain status for API"""
        cfg = self.config or self._load_config()
        try:
            from szyg.hermes_capabilities import get_hermes_capability_registry

            capabilities = get_hermes_capability_registry().list()
        except Exception:
            capabilities = []
        return {
            "engine": "hermes-agent",
            "version": "0.15",
            "model": cfg.get("model", {}).get("default", "unknown"),
            "provider": cfg.get("model", {}).get("provider", "auto"),
            "mcp_servers": len(cfg.get("mcp_servers", {})),
            "server_list": self.get_mcp_servers(),
            "mcp_runtime_attached": False,
            "business_capabilities": {
                "count": len(capabilities),
                "domains": sorted({item.get("domain", "") for item in capabilities if item.get("domain")}),
                "execution_path": "capability_registry",
            },
        }


# Singleton
_brain: HermesBrain | None = None

def get_brain() -> HermesBrain:
    global _brain
    if _brain is None:
        _brain = HermesBrain()
    return _brain
