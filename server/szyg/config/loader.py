"""
配置加载器 — YAML + 环境变量。

加载 config.yaml，自动替换 ${ENV_VAR} 和 ${ENV_VAR:default}。
环境变量优先级高于 YAML 文件。

用法:
    from szyg.config.loader import load_config
    cfg = load_config()
    print(cfg["llm"]["openrouter"]["api_key"])
"""

import os
import re
from pathlib import Path
from typing import Any

import yaml


def _resolve(value: Any) -> Any:
    """递归替换字符串中的 ${VAR} 和 ${VAR:default}。"""
    if isinstance(value, str):
        # ${VAR:default}
        value = re.sub(
            r"\$\{(\w+):([^}]*)\}",
            lambda m: os.environ.get(m.group(1), m.group(2)),
            value,
        )
        # ${VAR} (无默认值)
        value = re.sub(
            r"\$\{(\w+)\}",
            lambda m: os.environ.get(m.group(1), ""),
            value,
        )
        return value
    elif isinstance(value, dict):
        return {k: _resolve(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_resolve(v) for v in value]
    return value


def load_config(path: str | Path = "config.yaml") -> dict:
    """加载并解析配置文件。

    搜索顺序:
        1. 指定路径
        2. 当前目录 config.yaml
        3. 项目根目录 config.yaml

    Returns:
        dict: 解析后的配置字典(环境变量已替换)
    """
    configured_path = os.environ.get("SZYG_CONFIG_PATH", "").strip()
    config_path = Path(configured_path or path)
    if not config_path.exists():
        # 尝试项目根目录
        alt = Path(__file__).parent.parent.parent.parent / "config.yaml"
        if alt.exists():
            config_path = alt
        else:
            raise FileNotFoundError(
                f"Config file not found: {path} or {alt}"
            )

    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    return _resolve(raw) if raw else {}


def get_api_key(config: dict, *path: str) -> str:
    """从配置中安全获取 API key (优先环境变量)。

    Args:
        config: 配置字典
        *path: 配置路径，如 ("llm", "openrouter", "api_key")

    Returns:
        str: API key 或空字符串
    """
    value = config
    for key in path:
        value = value.get(key, {}) if isinstance(value, dict) else {}
    return value if isinstance(value, str) else ""
