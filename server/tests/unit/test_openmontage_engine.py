from pathlib import Path
from uuid import uuid4

import pytest

from szyg import media_storage
from szyg import openmontage_engine as director


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setattr(director.runtime, "STORE", tmp_path / "director")
    monkeypatch.setenv("SZYG_USER_HOME", str(tmp_path / "user"))
    monkeypatch.setattr(media_storage, "_CONFIG_PATH", tmp_path / "media-config.json")
    monkeypatch.setattr(
        director,
        "_guides",
        lambda: {"pipeline:documentary-montage": tmp_path / "pipeline.yaml"},
    )
    (tmp_path / "pipeline.yaml").write_text(
        "stages:\n  - name: edit\n    produces: [edit_decisions]\n", encoding="utf-8"
    )
    return director.create_project("测试片", "为新品创作一个短片。")["id"]


def test_versions_protect_director_storyboard_and_export(project):
    row = director.edit_project(
        project, [{"duration": 2, "caption": "春季上新"}], expected_revision=1
    )
    assert row["revision"] == 2
    assert director.list_projects()[0]["id"] == project
    with pytest.raises(ValueError, match="版本已变更"):
        director.edit_project(
            project, [{"duration": 3, "caption": "旧版"}], expected_revision=1
        )
    with pytest.raises(ValueError, match="已被修改"):
        director.render_project(project, expected_revision=1)
    assert director.get_project(project)["scenes"][0]["caption"] == "春季上新"


def test_library_urls_round_trip_and_stay_in_media_root(project, tmp_path):
    fixture = media_storage.get_media_output_dir("video") / "素材.mp4"
    fixture.write_bytes(b"fixture")
    src = media_storage.media_url_for_path(fixture)
    assert media_storage.resolve_managed_media_path(src) == fixture
    assert (
        director.edit_project(project, [{"source": src, "duration": 1}])["scenes"][0][
            "source"
        ]
        == src
    )
    for value in [
        str(fixture),
        "https://example.com/foo.mp4",
        src + "/trailing",
        "/api/media/files/video/../secret.mp4",
        str(tmp_path / "arbitrary"),
    ]:
        with pytest.raises(ValueError):
            director.edit_project(project, [{"source": value, "duration": 1}])


def test_provider_retry_uses_receipt_and_does_not_replace_input(project, monkeypatch):
    source = media_storage.get_media_output_dir("audio") / "sample.wav"
    source.write_bytes(b"audio fixture")
    media = media_storage.media_url_for_path(source)
    calls = []
    monkeypatch.setattr(
        director,
        "tool_info",
        lambda _: {
            "available": True,
            "executable": True,
            "input_schema": {"properties": {"input_path": {}}},
        },
    )

    def worker(request, cwd, **kwargs):
        calls.append(request["key"])
        staged = Path(request["settings"]["input_path"])
        assert staged.is_relative_to(cwd) and staged.read_bytes() == source.read_bytes()
        (cwd / "new.wav").write_bytes(staged.read_bytes())
        return {
            "data": {"path": str(cwd / "new.wav"), "token": "private"},
            "cost_usd": 0,
        }

    monkeypatch.setattr(director.runtime, "invoke", worker)
    request_id = str(uuid4())
    args = (project, "audio_enhance", {"input_path": media}, request_id)
    first = director.run_tool(*args)
    assert first == director.run_tool(*args)
    assert calls == ["audio_enhance"]
    assert first["data"] == {"path": first["artifacts"][0]["url"]}
    assert media_storage.resolve_managed_media_path(
        first["artifacts"][0]["url"]
    ).is_file()
    with pytest.raises(ValueError, match="不同操作"):
        director.run_tool(project, "another_tool", {"input_path": media}, request_id)


def test_provider_failure_is_not_silently_retried(project, monkeypatch):
    monkeypatch.setattr(
        director,
        "tool_info",
        lambda _: {
            "available": True,
            "executable": True,
            "input_schema": {"properties": {}},
        },
    )
    calls = []

    def uncertain(*args, **kwargs):
        calls.append(1)
        raise ValueError("provider timeout")

    monkeypatch.setattr(director.runtime, "invoke", uncertain)
    args = (project, "test", {}, str(uuid4()))
    with pytest.raises(ValueError, match="provider timeout"):
        director.run_tool(*args)
    with pytest.raises(ValueError, match="已记录"):
        director.run_tool(*args)
    assert len(calls) == 1
