from pathlib import Path

import pytest

from szyg.knowledge_service import KnowledgeService


@pytest.fixture
def knowledge(tmp_path: Path) -> KnowledgeService:
    return KnowledgeService(
        storage_dir=tmp_path / "knowledge-files",
        db_path=tmp_path / "knowledge.db",
        enable_execution_kernel=False,
    )


@pytest.mark.asyncio
async def test_markdown_document_is_persisted_normalized_and_searchable(knowledge: KnowledgeService):
    document = knowledge.create_document(
        "产品手册.md",
        "# 海马英语\n\n每天学习十分钟，适合英语启蒙。".encode("utf-8"),
        collection="产品资料",
    )

    completed = await knowledge.process_document(document["id"])

    assert completed["status"] == "ready"
    assert completed["chunk_count"] >= 1
    assert completed["source_available"] is True
    assert completed["markdown_available"] is True
    assert Path(completed["original_path"]).read_bytes().startswith(b"#")
    assert "source_filename" in Path(completed["markdown_path"]).read_text(encoding="utf-8")

    results = knowledge.search_sync("海马英语")
    assert results
    assert results[0]["filename"] == "产品手册.md"
    assert results[0]["collection"] == "产品资料"
    assert knowledge.search_sync("海马英语的核心卖点是什么")


@pytest.mark.asyncio
async def test_csv_is_converted_to_markdown_table(knowledge: KnowledgeService):
    document = knowledge.create_document(
        "客户.csv",
        "客户,需求\n张三,英语口语\n李四,亲子启蒙".encode("utf-8"),
    )

    completed = await knowledge.process_document(document["id"])
    markdown = Path(completed["markdown_path"]).read_text(encoding="utf-8")

    assert completed["status"] == "ready"
    assert "| 客户 | 需求 |" in markdown
    assert knowledge.search_sync("亲子启蒙")


def test_duplicate_content_is_not_ingested_twice(knowledge: KnowledgeService):
    content = "同一份企业知识".encode("utf-8")
    first = knowledge.create_document("资料一.txt", content)
    duplicate = knowledge.create_document("资料二.txt", content)

    assert duplicate["id"] == first["id"]
    assert duplicate["duplicate"] is True
    assert knowledge.stats()["total_docs"] == 1


@pytest.mark.asyncio
async def test_delete_removes_source_markdown_and_index(knowledge: KnowledgeService):
    document = knowledge.create_document("待移除.txt", "需要移除的内容".encode("utf-8"))
    completed = await knowledge.process_document(document["id"])
    source = Path(completed["original_path"])
    markdown = Path(completed["markdown_path"])

    assert knowledge.delete_document(document["id"]) is True
    assert source.exists() is False
    assert markdown.exists() is False
    assert knowledge.search_sync("需要移除") == []
    assert knowledge.stats()["total_docs"] == 0


def test_rejects_unsupported_file_type(knowledge: KnowledgeService):
    with pytest.raises(ValueError, match="暂不支持"):
        knowledge.create_document("程序.exe", b"not-an-executable")
