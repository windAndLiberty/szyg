"""
Unit tests for szyg.data_path — cross-platform data path resolution.
"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from szyg.data_path import get_data_dir


class TestGetDataDir:
    def test_env_var_takes_priority(self, tmp_path: Path):
        # Create tools.json in the env dir
        (tmp_path / "tools.json").write_text("{}")
        with patch.dict(os.environ, {"SZYG_DATA_DIR": str(tmp_path)}):
            # Re-call to test logic (avoid module-level caching)
            result = get_data_dir()
            assert result == tmp_path

    def test_env_var_without_tools_json_is_initialized(self, tmp_path: Path):
        # A clean desktop install starts with an empty private data directory.
        env_dir = tmp_path / "no_tools"
        with patch.dict(os.environ, {"SZYG_DATA_DIR": str(env_dir)}):
            result = get_data_dir()
            assert result == env_dir
            assert env_dir.is_dir()

    def test_empty_env_var_skipped(self):
        with patch.dict(os.environ, {"SZYG_DATA_DIR": ""}):
            result = get_data_dir()
            # Should not raise and should return a Path
            assert isinstance(result, Path)

    def test_whitespace_env_var_skipped(self):
        with patch.dict(os.environ, {"SZYG_DATA_DIR": "   "}):
            result = get_data_dir()
            assert isinstance(result, Path)

    def test_returns_path_object(self, tmp_path: Path):
        with patch.dict(os.environ, {"SZYG_DATA_DIR": ""}):
            result = get_data_dir()
            assert isinstance(result, Path)

    def test_project_relative_with_tools_json(self, tmp_path: Path):
        """If project-relative data/ has tools.json, it is chosen."""
        # Simulate the project structure: __file__ is at server/szyg/data_path.py
        # proj = Path(__file__).parent.parent.parent / "data"
        # We can't easily test the real file path, but we verify the function
        # returns a Path in all cases.
        with patch.dict(os.environ, {"SZYG_DATA_DIR": ""}):
            result = get_data_dir()
            assert isinstance(result, Path)
