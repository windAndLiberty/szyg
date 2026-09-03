"""
Unit tests for szyg.tool_runtime — plugin execution engine.
"""

import json
import os
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from szyg.tool_runtime import ToolRuntime


@pytest.fixture
def runtime(tmp_path: Path):
    """Create a ToolRuntime with isolated temp directories."""
    with patch("szyg.tool_runtime.INSTALL_FILE", tmp_path / "install.json"):
        rt = ToolRuntime(base_dir=tmp_path)
        yield rt


@pytest.fixture
def sample_zip(tmp_path: Path) -> str:
    """Create a sample tool ZIP file."""
    zip_path = str(tmp_path / "tool.zip")
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("main.py", "print('hello')")
        zf.writestr("config.json", '{"name": "test_tool"}')
    return zip_path


class TestToolRuntimeListInstalled:
    def test_empty_when_no_install_file(self, runtime: ToolRuntime, tmp_path: Path):
        with patch("szyg.tool_runtime.INSTALL_FILE", tmp_path / "nonexistent.json"):
            assert runtime.list_installed() == []

    def test_returns_installed_tools(self, runtime: ToolRuntime, tmp_path: Path):
        install_file = tmp_path / "install.json"
        data = [{"soft_id": "t1", "soft_code": "tool1", "version": "1.0"}]
        install_file.write_text(json.dumps(data), encoding="utf-8")
        with patch("szyg.tool_runtime.INSTALL_FILE", install_file):
            result = runtime.list_installed()
            assert len(result) == 1
            assert result[0]["soft_id"] == "t1"


class TestToolRuntimeIsInstalled:
    def test_false_when_not_installed(self, runtime: ToolRuntime, tmp_path: Path):
        with patch("szyg.tool_runtime.INSTALL_FILE", tmp_path / "empty.json"):
            assert runtime.is_installed("nonexistent") is False

    def test_true_when_installed(self, runtime: ToolRuntime, tmp_path: Path):
        install_file = tmp_path / "install.json"
        data = [{"soft_id": "t1", "soft_code": "tool1", "version": "1.0"}]
        install_file.write_text(json.dumps(data), encoding="utf-8")
        with patch("szyg.tool_runtime.INSTALL_FILE", install_file):
            assert runtime.is_installed("t1") is True
            assert runtime.is_installed("t2") is False


class TestToolRuntimeInstallFromZip:
    def test_extracts_and_registers(self, runtime: ToolRuntime, sample_zip: str, tmp_path: Path):
        install_file = tmp_path / "install.json"
        with patch("szyg.tool_runtime.INSTALL_FILE", install_file):
            entry = runtime.install_from_zip(sample_zip, "s1", "my_tool", "2.0")
            assert entry["soft_id"] == "s1"
            assert entry["soft_code"] == "my_tool"
            assert entry["version"] == "2.0"
            # Check files extracted
            tool_dir = runtime.tools_dir / "my_tool"
            assert (tool_dir / "main.py").exists()
            assert (tool_dir / "config.json").exists()

    def test_overwrites_existing_tool_dir(self, runtime: ToolRuntime, sample_zip: str, tmp_path: Path):
        install_file = tmp_path / "install.json"
        with patch("szyg.tool_runtime.INSTALL_FILE", install_file):
            # First install
            runtime.install_from_zip(sample_zip, "s1", "my_tool", "1.0")
            # Second install should overwrite
            entry = runtime.install_from_zip(sample_zip, "s1", "my_tool", "2.0")
            assert entry["version"] == "2.0"


class TestToolRuntimeUninstall:
    def test_uninstall_existing(self, runtime: ToolRuntime, sample_zip: str, tmp_path: Path):
        install_file = tmp_path / "install.json"
        with patch("szyg.tool_runtime.INSTALL_FILE", install_file):
            runtime.install_from_zip(sample_zip, "s1", "my_tool", "1.0")
            assert runtime.uninstall("s1") is True
            # Directory should be removed
            assert not (runtime.tools_dir / "my_tool").exists()

    def test_uninstall_nonexistent_returns_false(self, runtime: ToolRuntime, tmp_path: Path):
        install_file = tmp_path / "install.json"
        install_file.write_text("[]", encoding="utf-8")
        with patch("szyg.tool_runtime.INSTALL_FILE", install_file):
            assert runtime.uninstall("nonexistent") is False


class TestToolRuntimeLaunch:
    def test_returns_none_for_unknown_tool(self, runtime: ToolRuntime, tmp_path: Path):
        install_file = tmp_path / "install.json"
        install_file.write_text("[]", encoding="utf-8")
        with patch("szyg.tool_runtime.INSTALL_FILE", install_file):
            assert runtime.launch("unknown") is None

    def test_raises_if_no_executable(self, runtime: ToolRuntime, tmp_path: Path):
        install_file = tmp_path / "install.json"
        tool_dir = runtime.tools_dir / "empty_tool"
        tool_dir.mkdir(parents=True)
        data = [{"soft_id": "e1", "soft_code": "empty_tool", "version": "1.0", "file_path": str(tool_dir)}]
        install_file.write_text(json.dumps(data), encoding="utf-8")
        with patch("szyg.tool_runtime.INSTALL_FILE", install_file):
            with pytest.raises(FileNotFoundError, match="No executable found"):
                runtime.launch("e1")


class TestToolRuntimeStop:
    def test_stop_unknown_returns_false(self, runtime: ToolRuntime):
        assert runtime.stop("unknown") is False

    def test_stop_running_process(self, runtime: ToolRuntime):
        from unittest.mock import MagicMock
        mock_proc = MagicMock()
        runtime._processes["p1"] = mock_proc
        assert runtime.stop("p1") is True
        mock_proc.terminate.assert_called_once()
        assert "p1" not in runtime._processes


class TestToolRuntimeGetStats:
    def test_empty_stats(self, runtime: ToolRuntime, tmp_path: Path):
        install_file = tmp_path / "install.json"
        install_file.write_text("[]", encoding="utf-8")
        with patch("szyg.tool_runtime.INSTALL_FILE", install_file):
            stats = runtime.get_stats()
            assert stats["tools_installed"] == 0
            assert stats["running"] == 0

    def test_stats_reflect_state(self, runtime: ToolRuntime, sample_zip: str, tmp_path: Path):
        install_file = tmp_path / "install.json"
        with patch("szyg.tool_runtime.INSTALL_FILE", install_file):
            runtime.install_from_zip(sample_zip, "s1", "t1", "1.0")
            from unittest.mock import MagicMock
            runtime._processes["s1"] = MagicMock()
            stats = runtime.get_stats()
            assert stats["tools_installed"] == 1
            assert stats["running"] == 1
