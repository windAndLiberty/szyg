from __future__ import annotations

import pytest

from szyg import digital_human_service as service


@pytest.fixture
def isolated_assets(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "_ASSET_DIR", tmp_path / "assets")
    monkeypatch.setattr(service, "_ASSET_INDEX", tmp_path / "assets.json")


def test_public_config_requires_real_seedance_endpoint(monkeypatch):
    monkeypatch.setattr(
        service,
        "_config",
        lambda: {
            "model_label": "Seedance 2.5",
            "model": "doubao-seedance-2.5",
            "endpoint": "",
            "require_endpoint": True,
            "max_duration": 30,
        },
    )

    config = service.public_config()

    assert config["configured"] is False
    assert config["model_label"] == "Seedance 2.5"
    assert config["durations"] == list(range(4, 31))
    assert config["native_audio"] is True


def test_asset_lifecycle_uses_isolated_storage(isolated_assets, monkeypatch):
    monkeypatch.setattr(service, "_config", lambda: {"max_upload_mb": 80})

    asset = service.save_asset(
        "presenter.png",
        "image/png",
        b"\x89PNG\r\n\x1a\nfixture",
        "avatar_reference",
    )

    assert service.get_asset(asset["id"])["role"] == "avatar_reference"
    assert service.delete_asset(asset["id"]) is True
    assert service.get_asset(asset["id"]) is None


@pytest.mark.asyncio
async def test_render_does_not_fall_back_without_endpoint(monkeypatch):
    monkeypatch.setattr(
        service,
        "_config",
        lambda: {
            "model": "doubao-seedance-2.5",
            "endpoint": "",
            "require_endpoint": True,
        },
    )

    with pytest.raises(RuntimeError, match="Seedance 2.5"):
        await service.create_render({"script": "test", "asset_ids": ["missing"]})


@pytest.mark.asyncio
async def test_render_requires_avatar_reference(isolated_assets, monkeypatch):
    monkeypatch.setattr(
        service,
        "_config",
        lambda: {
            "model": "doubao-seedance-2.5",
            "endpoint": "ep-test",
            "require_endpoint": True,
            "max_upload_mb": 80,
        },
    )
    product = service.save_asset(
        "product.png",
        "image/png",
        b"\x89PNG\r\n\x1a\nfixture",
        "product_reference",
    )

    with pytest.raises(ValueError, match="人物参考图片"):
        await service.create_render({"script": "test", "asset_ids": [product["id"]]})
