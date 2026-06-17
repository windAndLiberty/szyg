#!/usr/bin/env python3
"""MCP Server: AI Agent Marketplace"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from pathlib import Path
from szyg.mcp_server import MCPServer

DATA_DIR = Path(os.environ.get("SZYG_DATA_DIR", "data"))
AGENTS_FILE = DATA_DIR / "agents.json"

server = MCPServer("szyg-agents", "AI agent marketplace with system prompt tiers")

def _read(): return json.loads(AGENTS_FILE.read_text(encoding='utf-8')) if AGENTS_FILE.exists() else []

@server.tool("agents_list", "List all AI agents with optional tier/category filter")
def agents_list(tier: str = "", category: str = "", search: str = ""):
    agents = _read()
    if tier: agents = [a for a in agents if a.get("tier") == tier]
    if category: agents = [a for a in agents if a.get("category") == category]
    if search:
        q = search.lower()
        agents = [a for a in agents if q in a.get("name","").lower() or q in a.get("description","").lower()]
    return [{"id": a["id"], "name": a["name"], "avatar": a.get("avatar","🤖"), "tier": a.get("tier",""),
             "description": a["description"], "tags": a.get("tags",[]), "rating": a.get("rating",0)} for a in agents]

@server.tool("agents_get", "Get a specific agent with full system prompt")
def agents_get(agent_id: str):
    agents = _read()
    for a in agents:
        if a["id"] == agent_id:
            a["usage_count"] = a.get("usage_count",0) + 1
            return {"id": a["id"], "name": a["name"], "system_prompt": a["system_prompt"],
                    "tier": a.get("tier",""), "temperature": a.get("temperature",0.7),
                    "model_preference": a.get("model_preference","")}
    return {"error": "Agent not found"}

@server.tool("agents_tiers", "List agent prompt tiers")
def agents_tiers():
    return [{"key":"base","label":"基础层-通用对话"},{"key":"domain","label":"领域层-行业专家"},{"key":"task","label":"任务层-场景执行"}]

@server.tool("agents_categories", "List agent categories")
def agents_categories():
    return list(set(a.get("category","general") for a in _read()))

if __name__ == "__main__":
    server.run()
