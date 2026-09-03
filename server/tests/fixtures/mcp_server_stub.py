#!/usr/bin/env python3
"""Minimal MCP server for testing — responds to initialize and tools/list."""
import json
import sys

TOOLS = [
    {"name": "sample_tool", "description": "A sample tool for testing", "parameters": {"type": "object", "properties": {"key": {"type": "string"}}}}
]

for line in sys.stdin:
    try:
        req = json.loads(line.strip())
    except json.JSONDecodeError:
        continue

    method = req.get("method", "")
    req_id = req.get("id", 0)

    if method == "initialize":
        resp = {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "test-mcp-server", "version": "1.0.0"},
            },
        }
        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()

    elif method == "tools/list":
        resp = {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": TOOLS},
        }
        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()

    elif method == "tools/call":
        resp = {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"content": [{"type": "text", "text": "tool executed"}]},
        }
        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()
