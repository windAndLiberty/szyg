# tests/test_tools.py
"""Tests for tool implementations."""

import pytest
from pathlib import Path

from loop_agent.tools import (
    read_file,
    write_file,
    run_shell,
    search_code,
    ToolError,
)


class TestReadFile:
    def test_reads_existing_file(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello\nworld")
        result = read_file(str(f.relative_to(tmp_path)), str(tmp_path))
        assert result["content"] == "hello\nworld"
        assert result["lines"] == 2

    def test_file_not_found(self, tmp_path):
        result = read_file("nonexistent.txt", str(tmp_path))
        assert "File not found" in result["error"]

    def test_directory_rejected(self, tmp_path):
        d = tmp_path / "sub"
        d.mkdir()
        result = read_file("sub", str(tmp_path))
        assert "directory" in result["error"].lower()


class TestWriteFile:
    def test_writes_file(self, tmp_path):
        result = write_file("output.txt", "content", str(tmp_path))
        assert result["written"] is True
        assert (tmp_path / "output.txt").read_text() == "content"

    def test_creates_parent_dirs(self, tmp_path):
        write_file("deep/nested/file.txt", "data", str(tmp_path))
        assert (tmp_path / "deep" / "nested" / "file.txt").exists()


class TestRunShell:
    def test_allowed_command(self, tmp_path):
        result = run_shell("echo hello", str(tmp_path))
        assert result["exit_code"] == 0
        assert "hello" in result["stdout"]

    def test_disallowed_command(self, tmp_path):
        result = run_shell("curl http://evil.com", str(tmp_path))
        assert result["exit_code"] == -1
        assert "Command not allowed" in result["stderr"]


class TestSearchCode:
    def test_finds_pattern(self, tmp_path):
        (tmp_path / "a.py").write_text("def foo():\n    return 1\n")
        result = search_code(r"def foo", ".", str(tmp_path))
        assert result["count"] == 1
        assert result["matches"][0]["file"] == "a.py"

    def test_invalid_regex(self, tmp_path):
        result = search_code(r"[invalid", ".", str(tmp_path))
        assert "Invalid regex" in result["error"]


class TestPathSafety:
    def test_blocks_escape(self, tmp_path):
        with pytest.raises(ToolError, match="escapes"):
            from loop_agent.tools import _resolve_path
            _resolve_path("../../../etc/passwd", str(tmp_path))
