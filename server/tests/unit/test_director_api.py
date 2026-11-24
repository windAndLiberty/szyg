import asyncio
import io
import sqlite3
import threading
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from szyg import conversation_media, director_jobs
from szyg.api import director_routes
from szyg.api.business_mcp_routes import _dispatch, _tool_catalog
from szyg.api.external_mcp_routes import TOOLS


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(director_jobs, "get_data_dir", lambda: tmp_path)
    app = FastAPI()
    app.include_router(director_routes.router)
    with TestClient(app) as http:
        yield http


def test_director_catalog_uses_actual_shapes_and_keeps_grants_isolated():
    tools = {item["name"]: item for item in _tool_catalog()}
    edit = tools["director.edit"]["inputSchema"]
    assert edit["required"] == ["project_id", "scenes"]
    assert edit["properties"]["scenes"]["items"]["properties"]["source"]
    assert tools["director.guide"]["annotations"]["readOnlyHint"]
    assert not tools["director.render"]["annotations"]["readOnlyHint"]
    assert "offset" in tools["director.guide"]["inputSchema"]["properties"]
    assert "offset" in tools["director.catalog"]["inputSchema"]["properties"]
    assert not TOOLS.intersection(name for name in tools if name.startswith("director."))
    req = {"id":1, "method":"tools/call", "params":{"name":"director_install","arguments":{"confirmed":True}}}
    assert asyncio.run(_dispatch(req, allowed=TOOLS))["error"]["code"] == -32602


def test_director_requires_confirmation_and_managed_media(client, monkeypatch):
    class Engine:
        def tool_info(self, key):
            return {"requires_approval": True, "provider":"example"}
        def run_tool(self, *args):
            pytest.fail("unconfirmed external operation")
    monkeypatch.setattr(director_routes, "_engine", Engine)
    path = "/api/director/projects/" + str(uuid4())
    assert client.post(path + "/tools", json={"key":"create_image","request_id":str(uuid4())}).json()["status"] == "confirmation_required"
    assert client.post("/api/director/install", json={"request_id":str(uuid4())}).status_code == 422
    for source in ("/etc/profile","https://host/asset.mp4","/api/media/files/video/../x.mp4","/api/media/files/video/file.mp3"):
        res = client.put(path, json={"scenes":[{"duration":1,"source":source}]})
        assert res.status_code == 422
    assert client.post("/api/director/transcribe", json={"source":"/api/media/files/audio/a.wav","request_id":str(uuid4())}).status_code == 422


def test_same_job_only_runs_once_under_race_and_is_recoverable(tmp_path,monkeypatch):
    monkeypatch.setattr(director_jobs, "get_data_dir", lambda: tmp_path)
    runs = []
    release = threading.Event()
    started = threading.Event()
    def render():
        started.set()
        runs.append(1)
        assert release.wait(5)
        return {"url":"/api/media/files/video/result.mp4"}
    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(director_jobs.submit, "request","render:p:1",render)
        assert started.wait(4)
        duplicate = director_jobs.submit("request","render:p:1",render)
        assert duplicate["status"] == "running"
        release.set()
        result = first.result(timeout=4)
    assert len(runs) == 1 and result["job_id"] == duplicate["job_id"] and result["status"] == "succeeded"
    assert director_jobs.submit("request","render:p:1",render) == result and len(runs)==1
    with pytest.raises(HTTPException) as info:
        director_jobs.submit("request","render:p:2",render)
    assert info.value.status_code == 409
    with sqlite3.connect(tmp_path / "director-jobs.sqlite3") as db:
        db.execute("UPDATE director_jobs SET status='running', pid=99999999")
    assert director_jobs.status(result["job_id"])["status"] == "interrupted"
    assert director_jobs.submit("request","render:p:1",render)["status"] == "interrupted" and len(runs)==1


def test_import_verifies_and_publishes_only_complete_local_media(client, tmp_path, monkeypatch):
    monkeypatch.setattr(conversation_media, "get_media_output_dir", lambda _: tmp_path)
    monkeypatch.setattr(conversation_media, "media_url_for_path", lambda path:"/api/media/files/audio/" + path.name)
    buf = io.BytesIO()
    with wave.open(buf,"wb") as out:
        out.setparams((1,2,16000,0,"NONE","not compressed"))
        out.writeframes(bytes(3200))
    response = client.post("/api/director/assets", files={"file":("旁白.wav",buf.getvalue(),"audio/wav")})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["name"]=="旁白.wav" and data["kind"]=="audio" and data["size"]==len(buf.getvalue())
    assert (tmp_path / data["url"].split("/")[-1]).read_bytes()==buf.getvalue()
    invalid = client.post("/api/director/assets", files={"file":("f.mp4",b"not video", "video/mp4")})
    assert invalid.status_code == 422 and len(list(tmp_path.iterdir())) == 1


def test_project_render_returns_persistent_delivery(client, monkeypatch, tmp_path):
    pid = str(uuid4())
    class Engine:
        def get_project(self, key):
            assert key==pid
            return {"revision":1}
        def render_project(self,key,expected_revision):
            assert key==pid and expected_revision==1
            (tmp_path/"final.mp4").write_bytes(b"movie")
            return {"url":"/api/media/files/video/final.mp4","path":str(tmp_path/"final.mp4"),"revision":1}
    monkeypatch.setattr(director_routes, "_engine", Engine)
    job = client.post("/api/director/projects/" + pid + "/render",json={}).json()
    assert job["status"]=="succeeded" and job["url"].endswith(".mp4")
    assert client.get("/api/director/jobs/"+job["job_id"]).json()==job
    assert client.post("/api/director/projects/"+pid+"/render",json={}).json()==job
    (tmp_path/"final.mp4").unlink()
    replacement = client.post("/api/director/projects/"+pid+"/render",json={}).json()
    assert replacement["job_id"] != job["job_id"] and (tmp_path/"final.mp4").is_file()



def test_render_card_exposes_only_persisted_local_render_outputs(client, tmp_path, monkeypatch):
    from szyg import media_storage
    monkeypatch.setattr(media_storage, "get_media_output_dir", lambda kind: tmp_path)
    pid = str(uuid4())
    key = "render:" + pid + ":3"
    url = "/api/media/files/video/clip.mp4"
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"video")
    job = director_jobs.submit(key, key, lambda: {"url": url, "path": str(clip), "notes": "internal"})
    endpoint = "/api/director/jobs/" + job["job_id"] + "/render"
    assert client.get(endpoint).json() == {"status":"succeeded","project_id":pid,"revision":3,
                                          "url":url,"job_id":job["job_id"]}
    clip.unlink()
    missing = client.get(endpoint).json()
    assert missing["status"] == "succeeded" and missing.get("error") and "url" not in missing
    unrelated = director_jobs.submit("private", "narrate:" + pid, lambda: {"notes":"internal"})
    assert client.get("/api/director/jobs/" + unrelated["job_id"] + "/render").status_code == 404
    assert client.get("/api/director/jobs/" + str(uuid4()) + "/render").status_code == 404
