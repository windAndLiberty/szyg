"""
Lightweight MCP Server — stdio JSON-RPC 2.0
Each szyg module gets its own MCP server process.
"""
import sys, json, inspect
from typing import Callable, Any


class MCPServer:
    """Minimal MCP stdio server. Subclass and register tools."""

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self._tools: dict[str, dict] = {}

    def tool(self, name: str, description: str = "", parameters: dict | None = None):
        """Decorator to register a tool"""
        def decorator(func: Callable):
            # Infer parameters from function signature
            sig = inspect.signature(func)
            props = {}
            required = []
            for pname, param in sig.parameters.items():
                if pname in ('self', 'cls'):
                    continue
                ptype = "string"
                if param.annotation is int:
                    ptype = "integer"
                elif param.annotation is float:
                    ptype = "number"
                elif param.annotation is bool:
                    ptype = "boolean"
                props[pname] = {"type": ptype, "description": f"Parameter: {pname}"}
                if param.default is inspect.Parameter.empty:
                    required.append(pname)

            self._tools[name] = {
                "name": name,
                "description": description or func.__doc__ or "",
                "inputSchema": {
                    "type": "object",
                    "properties": props,
                    "required": required,
                },
                "handler": func,
            }
            return func
        return decorator

    def _handle_request(self, request: dict) -> dict:
        """Handle a single JSON-RPC request"""
        rid = request.get("id", 0)
        method = request.get("method", "")
        params = request.get("params", {})

        try:
            if method == "initialize":
                return {
                    "jsonrpc": "2.0", "id": rid,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "serverInfo": {"name": self.name, "version": "1.0.0"},
                        "capabilities": {"tools": {}},
                    }
                }
            elif method == "tools/list":
                tools = []
                for t in self._tools.values():
                    tools.append({
                        "name": t["name"],
                        "description": t["description"],
                        "inputSchema": t["inputSchema"],
                    })
                return {"jsonrpc": "2.0", "id": rid, "result": {"tools": tools}}
            elif method == "tools/call":
                tool_name = params.get("name", "")
                arguments = params.get("arguments", {})
                tool = self._tools.get(tool_name)
                if not tool:
                    return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": f"Tool not found: {tool_name}"}}
                try:
                    result = tool["handler"](**arguments)
                    if isinstance(result, (dict, list, str, int, float, bool, type(None))):
                        content = json.dumps(result, ensure_ascii=False, default=str)
                    else:
                        content = str(result)
                    return {
                        "jsonrpc": "2.0", "id": rid,
                        "result": {"content": [{"type": "text", "text": content}]}
                    }
                except Exception as e:
                    return {
                        "jsonrpc": "2.0", "id": rid,
                        "result": {"content": [{"type": "text", "text": f"Error: {e}"}], "isError": True}
                    }
            elif method == "notifications/initialized":
                return None  # No response for notifications
            else:
                return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": f"Method not found: {method}"}}
        except Exception as e:
            return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32603, "message": str(e)}}

    def run(self):
        """Run the MCP server on stdio"""
        sys.stderr.write(f"[{self.name}] MCP Server starting on stdio\n")
        sys.stderr.flush()
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
                response = self._handle_request(request)
                if response is not None:
                    sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
                    sys.stdout.flush()
            except json.JSONDecodeError:
                sys.stderr.write(f"[{self.name}] Invalid JSON: {line[:100]}\n")
                sys.stderr.flush()
            except Exception as e:
                sys.stderr.write(f"[{self.name}] Error: {e}\n")
                sys.stderr.flush()
