"""
「域灵」数字员工系统 - 云推理客户端图片尺寸归一化测试

云网关对面积 < 3,686,400 像素的图片尺寸确定性返回 502。
generate_image 必须把非法尺寸（例如 1024x1024、512x512、1920x1080）
归一化为 SUPPORTED_IMAGE_SIZES 中的合法值后才发起请求。
"""

import asyncio
import base64
import json

import pytest
import respx
from httpx import Response

from szyg.integrations.cloud_inference_client import DEFAULT_IMAGE_SIZE

URL = "https://gateway.test/api/v1/inference/image"


def _png_response() -> Response:
    item = {
        "url": "https://gateway.test/out.png",
        "b64_json": base64.b64encode(b"image-bytes").decode(),
    }
    return Response(200, json={"data": {"data": [item]}})


@pytest.fixture
def cloud_config(monkeypatch):
    from szyg.cloud_auth import cloud_auth

    monkeypatch.setenv("SZYG_CLOUD_ENABLED", "true")
    monkeypatch.setenv("SZYG_CONTROL_URL", "https://gateway.test")
    monkeypatch.delenv("SZYG_DATA_DIR", raising=False)
    monkeypatch.setattr(cloud_auth, "access_token", lambda *a, **kw: "test-token")
    return cloud_auth


@pytest.fixture
def client(tmp_path, cloud_config):
    from szyg.integrations.cloud_inference_client import CloudInferenceClient
    return CloudInferenceClient(timeout=30, output_dir=str(tmp_path / "images"))


class TestCloudInferenceImageSizeNormalization:
    """云推理客户端必须将非法图片尺寸归一化到支持列表。"""

    @pytest.mark.parametrize(
        "size",
        [
            "1024x1024",  # 原默认值，云网关 502
            "512x512",
            "1920x1080",
            "768*768",
            "invalid",
        ],
    )
    def test_unsupported_size_is_normalized(self, client, size):
        """非法尺寸应归一化为 DEFAULT_IMAGE_SIZE 后再请求。"""
        sent = {}

        def capture(request):
            sent["body"] = json.loads(request.content.decode())
            return _png_response()

        with respx.mock:
            respx.post(URL).mock(side_effect=capture)
            asyncio.run(client.generate_image("一只猫", size=size))

        assert sent["body"]["payload"]["size"] == DEFAULT_IMAGE_SIZE

    def test_supported_size_passthrough(self, client):
        """合法尺寸应原样传递，不做改写。"""
        sent = {}

        def capture(request):
            sent["body"] = json.loads(request.content.decode())
            return _png_response()

        with respx.mock:
            respx.post(URL).mock(side_effect=capture)
            asyncio.run(client.generate_image("一只猫", size="2048x2048"))

        assert sent["body"]["payload"]["size"] == "2048x2048"

    def test_credit_exhaustion_is_not_reported_as_provider_outage(self, client):
        from szyg.integrations.cloud_inference_client import CloudInferenceError

        with respx.mock:
            respx.post(URL).mock(Response(429, json={"detail": "credits 余额不足，请先充值后再使用"}))
            with pytest.raises(CloudInferenceError) as caught:
                asyncio.run(client.generate_image("一只猫"))

        assert caught.value.status_code == 429
        assert "Credits 余额不足" in str(caught.value)

    def test_expired_session_requires_sign_in(self, client):
        from szyg.integrations.cloud_inference_client import CloudInferenceError

        with respx.mock:
            respx.post(URL).mock(Response(401, json={"detail": "登录状态已失效"}))
            with pytest.raises(CloudInferenceError) as caught:
                asyncio.run(client.generate_image("一只猫"))

        assert caught.value.status_code == 401
        assert str(caught.value) == "登录状态已失效，请重新登录"
