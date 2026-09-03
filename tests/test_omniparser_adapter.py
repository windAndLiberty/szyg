import pytest

from szyg.integrations.omniparser_adapter import OmniParserProvider, normalize_omniparser_elements


def test_normalize_omniparser_elements_marks_vision_source():
    result = {
        "width": 1000,
        "height": 500,
        "parsed_content_list": [
            {"idx": 0, "type": "icon", "content": "发布按钮", "bbox": [0.1, 0.2, 0.4, 0.3], "confidence": 0.92},
            {"idx": 1, "type": "text", "content": "标题", "bbox": [100, 120, 220, 150]},
        ],
    }

    elements = normalize_omniparser_elements(result)

    assert elements[0]["source"] == "vision"
    assert elements[0]["role"] == "button"
    assert elements[0]["confidence"] == 0.85
    assert elements[0]["bounds"] == {"x": 100, "y": 100, "width": 300, "height": 49}
    assert elements[1]["role"] == "text"
    assert elements[1]["bounds"] == {"x": 100, "y": 120, "width": 120, "height": 30}


@pytest.mark.asyncio
async def test_omniparser_status_missing_weights_is_non_fatal(tmp_path):
    source = tmp_path / "OmniParser-master"
    source.mkdir()
    provider = OmniParserProvider(source_dir=source, url="http://127.0.0.1:9", python_path="python")

    status = await provider.status()

    assert status["source_available"] is True
    assert status["weights_ready"] is False
    assert status["available"] is False
    assert "权重未就绪" in status["message"]


@pytest.mark.asyncio
async def test_omniparser_parse_missing_file_returns_readable_error(tmp_path):
    provider = OmniParserProvider(source_dir=tmp_path, url="http://127.0.0.1:9", python_path="python")

    result = await provider.parse_image_file(str(tmp_path / "missing.png"))

    assert result["ok"] is False
    assert result["elements"] == []
    assert "不存在" in result["error"]
