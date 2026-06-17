#!/usr/bin/env python3
"""MCP Server: Tool Marketplace"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from pathlib import Path
from szyg.mcp_server import MCPServer

DATA_DIR = Path(os.environ.get("SZYG_DATA_DIR", "data"))
TOOLS_FILE = DATA_DIR / "tools.json"
INSTALL_FILE = DATA_DIR / "install.json"

server = MCPServer("szyg-tools", "AI tool marketplace with install/launch capabilities")

def _read(f: Path): return json.loads(f.read_text(encoding='utf-8')) if f.exists() else []

@server.tool("tools_catalog", "List all tools in the marketplace")
def tools_catalog(category: str = "", search: str = ""):
    tools = _read(TOOLS_FILE)
    if category: tools = [t for t in tools if t.get("category") == category]
    if search:
        q = search.lower()
        tools = [t for t in tools if q in t.get("title","").lower() or q in t.get("desc","").lower()]
    return [{"id": t["id"], "title": t["title"], "desc": t["desc"], "category": t.get("category",""),
             "is_yun": t.get("is_yun",True), "icon": t.get("icon",""), "version": t.get("version","")} for t in tools]

@server.tool("tools_categories", "List all tool categories")
def tools_categories():
    tools = _read(TOOLS_FILE)
    return list(set(t.get("category","general") for t in tools))

@server.tool("tools_installed", "List installed tools")
def tools_installed():
    return _read(INSTALL_FILE)

@server.tool("tools_stats", "Get tool statistics")
def tools_stats():
    tools = _read(TOOLS_FILE)
    installed = _read(INSTALL_FILE)
    return {"total": len(tools), "installed": len(installed)}

@server.tool("tools_search", "Search tools by keyword")
def tools_search(query: str):
    q = query.lower()
    tools = _read(TOOLS_FILE)
    results = [t for t in tools if q in t.get("title","").lower() or q in t.get("desc","").lower() or q in t.get("category","").lower()]
    return [{"id": t["id"], "title": t["title"], "desc": t["desc"], "category": t.get("category","")} for t in results[:10]]

if __name__ == "__main__":
    server.run()
