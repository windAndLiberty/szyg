#!/usr/bin/env python3
"""MCP Server: Knowledge Base"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from szyg.mcp_server import MCPServer

server = MCPServer("szyg-knowledge", "FTS5 knowledge base with RAG search")

def get_kb():
    from szyg.knowledge_service import get_knowledge_service
    return get_knowledge_service()

@server.tool("kb_search", "Search knowledge base with FTS5 full-text search")
def kb_search(query: str, limit: int = 5):
    results = get_kb().search_sync(query, limit)
    return [{
        "content": item["content"],
        "source": item["filename"],
        "locator": item.get("locator", ""),
        "relevance": item.get("score", 0),
    } for item in results]

@server.tool("kb_ingest", "Ingest a document into the knowledge base")
def kb_ingest(file_path: str):
    import asyncio
    from pathlib import Path

    path = Path(file_path).expanduser().resolve()
    if not path.is_file():
        return {"ok": False, "error": "文件不存在"}
    kb = get_kb()
    document = kb.create_document(path.name, path.read_bytes())
    if not document.get("duplicate"):
        document = asyncio.run(kb.process_document(document["id"]))
    return {"ok": document.get("status") == "ready", "document": document}

@server.tool("kb_stats", "Get knowledge base statistics")
def kb_stats():
    return get_kb().stats()

if __name__ == "__main__":
    server.run()
