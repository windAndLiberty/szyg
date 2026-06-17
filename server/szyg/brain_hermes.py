"""
Hermes Brain — 用仓库内置的 Hermes 源码（``server/`` 下的 AIAgent runtime）
作为 szyg 数字员工系统的内核，这里只做一层 *浅封装*。

职责：
- 准备 Hermes 运行环境（HERMES_HOME 指向项目内 ``.hermes``，与本机 ~/.hermes 隔离）。
- 把 szyg 业务能力注册成 Hermes 原生 toolset（见 ``szyg.agent_core.szyg_toolset``）。
- 用火山引擎（OpenAI 兼容）凭据构造 ``run_agent.AIAgent`` 实例，并暴露回调，
  供 SSE 路由驱动（streaming / 并发工具 / 重试 / guardrail 全部来自 Hermes 内核）。

注意：这里的 Hermes 是 *app 内置源码*，不是开发者本机安装的 hermes CLI。
"""
import os, sys, json, yaml
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
SERVER_DIR = PROJECT_ROOT / "server"
HERMES_HOME = PROJECT_ROOT / ".hermes"

# 确保仓库内置的 Hermes 源码（server/ 下的 run_agent / agent / tools / ...）可被 import。
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

# 火山引擎 ARK（OpenAI 兼容）默认配置 — 作为 Hermes runtime 的 provider。
VOLCANO_BASE_URL = os.environ.get(
    "VOLCANO_ENGINE_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3"
)
DEFAULT_MODEL = os.environ.get("SZYG_HERMES_MODEL", "deepseek-v4-pro-260425")
SZYG_TOOLSET = "szyg"


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
- ⚡ 智能调度引擎 (sched_*) — cron/interval/manual定时任务
- 🧰 工具市场 (tools_*) — AI工具目录/分类/搜索
- 📚 知识库 (kb_*) — FTS5全文检索/文档摄入/RAG
- 🤖 AI智能体 (agents_*) — 12个SME场景AI专家/提示词层级
- 🎨 品牌管理 (oem_*) — 主题切换/多租户配置

Hermes Tool Search 让你按需加载工具schema，高效调用。
用自然语言理解用户意图，自动编排工具链完成任务。"""

    def get_mcp_servers(self) -> list[dict]:
        """Return configured MCP servers"""
        servers = self.config.get("mcp_servers", {})
        return [{"name": k, **v} for k, v in servers.items()]

    # ------------------------------------------------------------------
    # Hermes runtime facade — build a real AIAgent (内置源码内核)
    # ------------------------------------------------------------------

    def szyg_tool_names(self) -> list[str]:
        """注册并返回 szyg 原生 toolset 的工具名列表。"""
        from szyg.agent_core.szyg_toolset import register_szyg_toolset

        return register_szyg_toolset()

    def build_agent(
        self,
        *,
        model: str | None = None,
        session_id: str | None = None,
        system_prompt: str | None = None,
        use_tools: bool = True,
        stream_delta_callback=None,
        tool_start_callback=None,
        tool_complete_callback=None,
        tool_progress_callback=None,
        reasoning_callback=None,
        max_iterations: int = 24,
    ):
        """构造一个绑定 szyg 业务能力的 Hermes ``AIAgent``。

        - 通过仓库内置的 Hermes 源码（``run_agent.AIAgent``）作为内核。
        - provider 走火山引擎 ARK（OpenAI 兼容 chat-completions）。
        - ``use_tools=True`` 时启用 ``szyg`` toolset（业务能力），否则纯提示词 + LLM
          （适合大多数轻量智能体，无工具噪音、响应更快）。
        - ``system_prompt`` 可按智能体覆盖默认中枢提示词。
        - 全部回调透传给调用方（SSE 路由），获得 token 级流式 + 并发工具反馈。
        """
        if use_tools:
            # 先注册业务工具，确保 enabled_toolsets=["szyg"] 能解析到工具。
            self.szyg_tool_names()
            enabled_toolsets = [SZYG_TOOLSET]
        else:
            enabled_toolsets = []

        # HERMES_HOME 已在 __init__ 中设置；此时 import 内核源码。
        from run_agent import AIAgent

        api_key = os.environ.get("VOLCANO_ENGINE_API_KEY", "")
        agent = AIAgent(
            model=model or DEFAULT_MODEL,
            api_key=api_key,
            base_url=VOLCANO_BASE_URL,
            provider="custom",
            api_mode="chat_completions",
            enabled_toolsets=enabled_toolsets,
            max_iterations=max_iterations,
            quiet_mode=True,
            verbose_logging=False,
            ephemeral_system_prompt=system_prompt or self.get_system_prompt(),
            session_id=session_id,
            platform="szyg",
            stream_delta_callback=stream_delta_callback,
            tool_start_callback=tool_start_callback,
            tool_complete_callback=tool_complete_callback,
            tool_progress_callback=tool_progress_callback,
            reasoning_callback=reasoning_callback,
        )
        return agent

    def get_status(self) -> dict:
        """Brain status for API"""
        try:
            tools = self.szyg_tool_names()
        except Exception:
            tools = []
        return {
            "engine": "hermes-agent (embedded source)",
            "kernel": "server/run_agent.py::AIAgent",
            "model": DEFAULT_MODEL,
            "provider": "volcano-engine (ark / openai-compatible)",
            "base_url": VOLCANO_BASE_URL,
            "toolset": SZYG_TOOLSET,
            "tools": len(tools),
            "tool_names": tools,
        }


# Singleton
_brain: HermesBrain | None = None

def get_brain() -> HermesBrain:
    global _brain
    if _brain is None:
        _brain = HermesBrain()
    return _brain
