"""
Unified Brain — embeds nanobot as the szyg intelligence core.
Users don't see nanobot, they interact through szyg's WebUI and API.
"""
import os, sys, json, asyncio
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent


class SzygBrain:
    """Wraps nanobot as the invisible intelligence brain of szyg."""

    def __init__(self):
        self._config = None
        self._agent = None

    def load_config(self):
        """Load szyg + nanobot merged config"""
        config_path = PROJECT_ROOT / ".nanobot" / "config.json"
        if config_path.exists():
            self._config = json.loads(config_path.read_text(encoding='utf-8'))
        else:
            self._config = self._default_config()
        return self._config

    def _default_config(self):
        return {
            "agentDefaults": {
                "model": "ollama/qwen3",
                "provider": "ollama",
                "maxTokens": 4096,
                "temperature": 0.1,
                "botName": "szyg",
                "botIcon": "⚡",
                "timezone": "Asia/Shanghai",
            },
            "channels": {"webui": {}},
            "tools": {"mcpServers": {}},
        }

    def get_system_prompt(self) -> str:
        return """你是szyg智能矩阵运营系统的中枢AI助手。你的能力包括:

1. 📝 内容发布管道: 创建、审核、排期、发布内容到多平台 (pub_* 系列工具)
2. ⚡ 智能调度引擎: 创建和管理定时任务 cron/interval/manual (sched_* 系列工具)
3. 🧰 工具市场: 浏览和管理AI工具 (tools_* 系列工具)
4. 📚 知识库: FTS5全文检索和文档摄入 (kb_* 系列工具)
5. 🤖 AI智能体广场: 12个中小企业场景AI专家 (agents_* 系列工具)
6. 🎨 OEM品牌: 主题切换和品牌配置 (oem_* 系列工具)

当用户用自然语言提出需求时,自动识别意图并调用MCP工具完成任务。回复简洁实用,直击要点。"""

    def get_mcp_server_list(self) -> list[dict]:
        """List configured MCP servers for status display"""
        cfg = self.load_config()
        servers = cfg.get("tools", {}).get("mcpServers", {})
        result = []
        for name, s in servers.items():
            result.append({
                "name": name,
                "command": s.get("command", ""),
                "args": s.get("args", []),
            })
        return result


# Singleton
_brain: SzygBrain | None = None

def get_brain() -> SzygBrain:
    global _brain
    if _brain is None:
        _brain = SzygBrain()
    return _brain
