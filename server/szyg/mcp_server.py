"""
Lightweight MCP Server — stdio JSON-RPC 2.0
Each szyg module gets its own MCP server process.

Supports both sync and async tool handlers.
v1.1 — added async handler support, improved type inference for list/dict params.
"""
import sys, json, inspect, asyncio
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
                annotation = param.annotation
                ptype = "string"
                if annotation is inspect.Parameter.empty:
                    ptype = "string"
                elif annotation is int:
                    ptype = "integer"
                elif annotation is float:
                    ptype = "number"
                elif annotation is bool:
                    ptype = "boolean"
                elif annotation is list or str(annotation).startswith("list"):
                    ptype = "array"
                    props[pname] = {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": f"Parameter: {pname}",
                    }
                    if param.default is inspect.Parameter.empty:
                        required.append(pname)
                    continue
                elif annotation is dict or str(annotation).startswith("dict"):
                    ptype = "object"
                    props[pname] = {
                        "type": "object",
                        "description": f"Parameter: {pname}",
                    }
                    if param.default is inspect.Parameter.empty:
                        required.append(pname)
                    continue
                props[pname] = {"type": ptype, "description": f"Parameter: {pname}"}
                if param.default is inspect.Parameter.empty:
                    required.append(pname)

            self._tools[name] = {
                "name": name,
                "description": description or (func.__doc__ or "").strip().split("\n")[0],
                "inputSchema": {
                    "type": "object",
                    "properties": props,
                    "required": required,
                },
                "handler": func,
                "is_async": inspect.iscoroutinefunction(func),
            }
            return func
        return decorator

    async def _handle_request(self, request: dict) -> dict | None:
        """Handle a single JSON-RPC request (async — supports await on tools)"""
        rid = request.get("id", 0)
        method = request.get("method", "")
        params = request.get("params", {})

        try:
            if method == "initialize":
                return {
                    "jsonrpc": "2.0", "id": rid,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "serverInfo": {"name": self.name, "version": "1.1.0"},
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
                    if tool["is_async"]:
                        result = await tool["handler"](**arguments)
                    else:
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

    async def _process_line(self, line: str) -> str | None:
        """Process one JSON-RPC line, return JSON response string or None."""
        if not line.strip():
            return None
        try:
            request = json.loads(line)
            response = await self._handle_request(request)
            if response is not None:
                return json.dumps(response, ensure_ascii=False)
        except json.JSONDecodeError:
            sys.stderr.write(f"[{self.name}] Invalid JSON: {line[:100]}\n")
            sys.stderr.flush()
        except Exception as e:
            sys.stderr.write(f"[{self.name}] Error: {e}\n")
            sys.stderr.flush()
        return None

    async def _run_async(self):
        """Async run loop using a stdin reader task."""
        sys.stderr.write(f"[{self.name}] MCP Server v1.1 starting on stdio\n")
        sys.stderr.flush()

        loop = asyncio.get_event_loop()

        async def read_stdin():
            """Read lines from stdin asynchronously."""
            while True:
                line = await loop.run_in_executor(None, sys.stdin.readline)
                if not line:
                    break  # EOF
                response = await self._process_line(line)
                if response is not None:
                    sys.stdout.write(response + "\n")
                    sys.stdout.flush()

        await read_stdin()

    def run(self):
        """Run the MCP server on stdio. Detects async tools and uses asyncio if needed."""
        has_async = any(t.get("is_async") for t in self._tools.values())
        if has_async:
            asyncio.run(self._run_async())
        else:
            # Fast path: synchronous loop (backward compatible)
            sys.stderr.write(f"[{self.name}] MCP Server starting on stdio\n")
            sys.stderr.flush()
            for line in sys.stdin:
                line = line.strip()
                if not line:
                    continue
                try:
                    request = json.loads(line)
                    # _handle_request is async; for sync tools it returns immediately
                    # Use asyncio.run for compatibility with async _handle_request
                    response = asyncio.run(self._handle_request(request))
                    if response is not None:
                        sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
                        sys.stdout.flush()
                except json.JSONDecodeError:
                    sys.stderr.write(f"[{self.name}] Invalid JSON: {line[:100]}\n")
                    sys.stderr.flush()
                except Exception as e:
                    sys.stderr.write(f"[{self.name}] Error: {e}\n")
                    sys.stderr.flush()
