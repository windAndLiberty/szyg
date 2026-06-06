#!/usr/bin/env python3
"""MCP Server: Knowledge Base"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from szyg.mcp_server import MCPServer

server = MCPServer("szyg-knowledge", "FTS5 knowledge base with RAG search")

# Lazy init
_kb = None
def get_kb():
    global _kb
    if _kb is None:
        from szyg.agent_core.knowledge import KnowledgeBase
        _kb = KnowledgeBase()
    return _kb

@server.tool("kb_search", "Search knowledge base with FTS5 full-text search")
def kb_search(query: str, limit: int = 5):
    from szyg.agent_core.memory import Memory
    m = Memory("./data/knowledge.db")
    results = m.search(query, limit)
    return [{"content": r["content"][:300], "type": r["entry_type"], "source": r.get("source",""),
             "relevance": str(r.get("relevance_score",""))} for r in results]

@server.tool("kb_ingest", "Ingest a document into the knowledge base")
def kb_ingest(file_path: str):
    kb = get_kb()
    await_result = kb.ingest_file(file_path)
    return {"ok": True, "file": file_path}

@server.tool("kb_stats", "Get knowledge base statistics")
def kb_stats():
    m = Memory("./data/knowledge.db")
    return {"status": "active"}

# Fix: import at top level to avoid local-vs-global issues
from szyg.agent_core.memory import Memory

if __name__ == "__main__":
    server.run()
