#!/usr/bin/env python3
"""MCP Server: OEM Branding"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from pathlib import Path
from szyg.mcp_server import MCPServer

DATA_DIR = Path(os.environ.get("SZYG_DATA_DIR", "data"))
OEM_FILE = DATA_DIR / "oem.json"

server = MCPServer("szyg-oem", "OEM branding and multi-tenant configuration")

def _read():
    if OEM_FILE.exists(): return json.loads(OEM_FILE.read_text(encoding='utf-8'))
    return {"name":"szyg","theme":"default","copyright":"© 2024"}

@server.tool("oem_config", "Get current OEM branding configuration")
def oem_config():
    return _read()

@server.tool("oem_themes", "List available themes")
def oem_themes():
    return ["default","dark","green","sunset","starry"]

if __name__ == "__main__":
    server.run()
