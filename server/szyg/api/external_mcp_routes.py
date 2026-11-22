"""Local MCP connections granted by the signed-in desktop user."""
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
from contextlib import closing
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from szyg.api.business_mcp_routes import _dispatch, _error, _tool_catalog
from szyg.cloud_auth import cloud_auth
from szyg.data_path import get_data_dir

router = APIRouter()
ENDPOINT = "/api/mcp/xiaoyu"
CONNECTIONS = "/api/settings/mcp-connections"
# Adding an internal capability must never silently extend an existing grant.
TOOLS = {"knowledge.stats", "knowledge.search", "knowledge.documents",
         "knowledge.ingest", "content.copy.generate"}
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


class Grant(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    tools: set[str] = Field(min_length=1, max_length=len(TOOLS))


def _local(request: Request) -> None:
    if (request.url.hostname not in LOCAL_HOSTS or not request.client
            or request.client.host not in LOCAL_HOSTS):
        raise HTTPException(403, "Local connections only")
    origin = request.headers.get("origin")
    if origin and origin != f"{request.url.scheme}://{request.url.netloc}":
        raise HTTPException(403, "Invalid origin")


def _desktop(request: Request) -> str:
    _local(request)
    expected = os.getenv("SZYG_DESKTOP_TOKEN", "")
    supplied = request.cookies.get("szyg_desktop_token") or request.headers.get("X-SZYG-Desktop-Token", "")
    if not expected or not hmac.compare_digest(expected.encode(), supplied.encode()):
        raise HTTPException(403, "Open settings in the Xiaoyu desktop app")
    if not cloud_auth.active_user_id:
        raise HTTPException(403, "Sign in to manage connections")
    return cloud_auth.active_user_id


def _db():
    db = sqlite3.connect(get_data_dir() / "mcp-connections.sqlite3")
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE IF NOT EXISTS grants (
        id TEXT PRIMARY KEY, owner TEXT NOT NULL, name TEXT NOT NULL,
        digest TEXT NOT NULL UNIQUE, tools TEXT NOT NULL)""")
    return db


@router.get(CONNECTIONS)
def list_connections(owner: str = Depends(_desktop)):
    with closing(_db()) as db:
        rows = db.execute("SELECT id,name,tools FROM grants WHERE owner=? ORDER BY rowid", (owner,))
        connections = [dict(row) | {"tools": json.loads(row["tools"])} for row in rows]
    port = int(os.environ.get("SZYG_BACKEND_PORT", "8000"))
    return {"url": f"http://127.0.0.1:{port}{ENDPOINT}", "connections": connections,
            "tools": [tool for tool in _tool_catalog() if tool["name"] in TOOLS]}


@router.post(CONNECTIONS, status_code=201)
def grant_connection(grant: Grant, owner: str = Depends(_desktop)):
    if not grant.name.strip() or not grant.tools <= TOOLS:
        raise HTTPException(422, "Invalid connection name or tools")
    token = secrets.token_urlsafe(32)
    key = uuid4().hex
    with closing(_db()) as db, db:
        db.execute("INSERT INTO grants VALUES (?,?,?,?,?)", (
            key, owner, grant.name.strip(), hashlib.sha256(token.encode()).hexdigest(),
            json.dumps(sorted(grant.tools))))
    return JSONResponse({"id": key, "token": token}, status_code=201, headers={"Cache-Control": "no-store"})


@router.delete(CONNECTIONS + "/{key}", status_code=204)
def revoke_connection(key: str, owner: str = Depends(_desktop)):
    with closing(_db()) as db, db:
        db.execute("DELETE FROM grants WHERE id=? AND owner=?", (key, owner))
    return Response(status_code=204)


def _scope(request: Request) -> set[str]:
    _local(request)
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() == "bearer" and token and cloud_auth.active_user_id:
        with closing(_db()) as db:
            row = db.execute("SELECT tools FROM grants WHERE owner=? AND digest=?", (
                cloud_auth.active_user_id, hashlib.sha256(token.encode()).hexdigest())).fetchone()
        if row:
            return set(json.loads(row["tools"])) & TOOLS
    raise HTTPException(401, "Invalid or inactive MCP credential", headers={"WWW-Authenticate": "Bearer"})


@router.api_route(ENDPOINT, methods=["POST", "GET", "DELETE"])
async def external_mcp(request: Request, allowed: set[str] = Depends(_scope)):
    if request.method != "POST":
        return Response(status_code=405, headers={"Allow": "POST"})
    try:
        payload = await request.json()
    except ValueError:
        return JSONResponse(_error(None, -32700, "Invalid JSON"), status_code=400)
    if not isinstance(payload, dict) or payload.get("jsonrpc") != "2.0" or not isinstance(payload.get("method"), str):
        return JSONResponse(_error(None, -32600, "Invalid JSON-RPC request"), status_code=400)
    if "id" not in payload:
        return Response(status_code=202)
    response = await _dispatch(payload, allowed=allowed)
    return JSONResponse(response) if response else Response(status_code=202)
