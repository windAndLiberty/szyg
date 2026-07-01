"""
Unit tests for szyg.atomic_file — atomic JSON read/write operations.
"""

import asyncio
import json
import threading
from pathlib import Path

import pytest

from szyg.atomic_file import (
    _get_file_lock,
    atomic_read,
    atomic_read_async,
    atomic_write,
    atomic_write_async,
)


class TestGetFileLock:
    def test_returns_lock_for_path(self, tmp_path: Path):
        lock = _get_file_lock(tmp_path / "test.json")
        assert hasattr(lock, 'acquire') and hasattr(lock, 'release')

    def test_same_path_returns_same_lock(self, tmp_path: Path):
        path = tmp_path / "test.json"
        lock1 = _get_file_lock(path)
        lock2 = _get_file_lock(path)
        assert lock1 is lock2

    def test_different_paths_return_different_locks(self, tmp_path: Path):
        lock1 = _get_file_lock(tmp_path / "a.json")
        lock2 = _get_file_lock(tmp_path / "b.json")
        assert lock1 is not lock2


class TestAtomicRead:
    def test_returns_empty_list_for_missing_file(self, tmp_path: Path):
        result = atomic_read(tmp_path / "nonexistent.json")
        assert result == []

    def test_reads_valid_json_array(self, tmp_path: Path):
        path = tmp_path / "data.json"
        data = [{"id": 1, "name": "test"}]
        path.write_text(json.dumps(data), encoding="utf-8")
        assert atomic_read(path) == data

    def test_returns_empty_on_corrupt_json(self, tmp_path: Path):
        path = tmp_path / "corrupt.json"
        path.write_text("{invalid json[", encoding="utf-8")
        assert atomic_read(path) == []

    def test_creates_parent_dirs_if_missing(self, tmp_path: Path):
        path = tmp_path / "sub" / "dir" / "data.json"
        result = atomic_read(path)
        assert result == []
        assert path.parent.exists()

    def test_reads_empty_array(self, tmp_path: Path):
        path = tmp_path / "empty.json"
        path.write_text("[]", encoding="utf-8")
        assert atomic_read(path) == []

    def test_reads_unicode_content(self, tmp_path: Path):
        path = tmp_path / "unicode.json"
        data = [{"title": "测试中文", "emoji": "🎉"}]
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        assert atomic_read(path) == data


class TestAtomicWrite:
    def test_writes_json_array(self, tmp_path: Path):
        path = tmp_path / "out.json"
        data = [{"x": 1}, {"x": 2}]
        atomic_write(path, data)
        assert json.loads(path.read_text(encoding="utf-8")) == data

    def test_creates_parent_dirs(self, tmp_path: Path):
        path = tmp_path / "a" / "b" / "out.json"
        atomic_write(path, [{"key": "val"}])
        assert path.exists()
        assert json.loads(path.read_text(encoding="utf-8")) == [{"key": "val"}]

    def test_overwrites_existing_file(self, tmp_path: Path):
        path = tmp_path / "data.json"
        atomic_write(path, [{"v": 1}])
        atomic_write(path, [{"v": 2}])
        assert json.loads(path.read_text(encoding="utf-8")) == [{"v": 2}]

    def test_writes_unicode(self, tmp_path: Path):
        path = tmp_path / "cn.json"
        data = [{"name": "域灵数字员工"}]
        atomic_write(path, data)
        content = json.loads(path.read_text(encoding="utf-8"))
        assert content == data

    def test_tmp_file_is_cleaned_up(self, tmp_path: Path):
        path = tmp_path / "clean.json"
        atomic_write(path, [{"done": True}])
        tmp_file = path.with_suffix(".json.tmp")
        assert not tmp_file.exists()

    def test_concurrent_writes_are_safe(self, tmp_path: Path):
        """Multiple threads writing should not corrupt the file."""
        path = tmp_path / "concurrent.json"
        results = []

        def writer(n):
            atomic_write(path, [{"writer": n}])
            results.append(n)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # File should contain valid JSON from the last writer
        data = json.loads(path.read_text(encoding="utf-8"))
        assert len(data) == 1
        assert data[0]["writer"] in range(10)


class TestAtomicReadAsync:
    @pytest.mark.asyncio
    async def test_reads_valid_json(self, tmp_path: Path):
        path = tmp_path / "async_read.json"
        path.write_text('[{"async": true}]', encoding="utf-8")
        result = await atomic_read_async(path)
        assert result == [{"async": True}]

    @pytest.mark.asyncio
    async def test_returns_empty_for_missing(self, tmp_path: Path):
        result = await atomic_read_async(tmp_path / "nope.json")
        assert result == []


class TestAtomicWriteAsync:
    @pytest.mark.asyncio
    async def test_writes_json(self, tmp_path: Path):
        path = tmp_path / "async_write.json"
        await atomic_write_async(path, [{"async": "write"}])
        assert json.loads(path.read_text(encoding="utf-8")) == [{"async": "write"}]
