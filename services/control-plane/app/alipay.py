from __future__ import annotations

from pathlib import Path

from alipay.aop.api.AlipayClientConfig import AlipayClientConfig
from alipay.aop.api.DefaultAlipayClient import DefaultAlipayClient
from alipay.aop.api.domain.AlipayTradePagePayModel import AlipayTradePagePayModel
from alipay.aop.api.request.AlipayTradePagePayRequest import AlipayTradePagePayRequest
from alipay.aop.api.util.SignatureUtils import get_sign_content, verify_with_rsa
from cryptography.hazmat.primitives import serialization

from .config import get_settings


def _pem(raw: bytes, label: str) -> bytes:
    if raw.lstrip().startswith(b"-----BEGIN"):
        return raw
    stripped = b"".join(raw.split())
    body = b"\n".join(stripped[i:i + 64] for i in range(0, len(stripped), 64))
    return b"-----BEGIN " + label.encode() + b"-----\n" + body + b"\n-----END " + label.encode() + b"-----\n"


def _key_body(pem: bytes) -> str:
    return "".join(
        line.strip() for line in pem.decode("ascii").splitlines()
        if line and not line.startswith("-----")
    )


def _canonical(params: dict[str, str]) -> str:
    signed_params = {
        key: value for key, value in params.items()
        if key not in {"sign", "sign_type"} and value not in {None, ""}
    }
    return get_sign_content(signed_params)


class AlipayGateway:
    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def enabled(self) -> bool:
        return self.settings.alipay_enabled

    def _private_key_body(self) -> str:
        raw = Path(self.settings.alipay_merchant_private_key_file).read_bytes()
        try:
            key = serialization.load_pem_private_key(_pem(raw, "PRIVATE KEY"), password=None)
        except ValueError:
            key = serialization.load_pem_private_key(_pem(raw, "RSA PRIVATE KEY"), password=None)
        traditional_pem = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
        return _key_body(traditional_pem)

    def _public_key_body(self) -> str:
        raw = Path(self.settings.alipay_public_key_file).read_bytes()
        public_key = serialization.load_pem_public_key(_pem(raw, "PUBLIC KEY"))
        normalized_pem = public_key.public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return _key_body(normalized_pem)

    def _client(self) -> DefaultAlipayClient:
        config = AlipayClientConfig()
        config.server_url = self.settings.alipay_gateway_url
        config.app_id = self.settings.alipay_app_id
        config.app_private_key = self._private_key_body()
        config.alipay_public_key = self._public_key_body()
        config.charset = "utf-8"
        config.format = "json"
        config.sign_type = "RSA2"
        return DefaultAlipayClient(alipay_client_config=config)

    def verify(self, params: dict[str, str]) -> bool:
        signature = params.get("sign", "")
        try:
            content = _canonical(params).encode("utf-8")
            return verify_with_rsa(self._public_key_body(), content, signature)
        except Exception:
            return False

    def page_pay_url(self, *, merchant_order_no: str, amount: str, subject: str) -> str:
        notify_url = self.settings.alipay_notify_url or (
            self.settings.public_base_url.rstrip("/") + "/api/v1/payments/alipay/notify"
        )
        return_url = self.settings.alipay_return_url or (
            self.settings.public_base_url.rstrip("/") + "/api/v1/payments/alipay/return"
        )

        model = AlipayTradePagePayModel()
        model.out_trade_no = merchant_order_no
        model.total_amount = amount
        model.subject = subject
        model.product_code = "FAST_INSTANT_TRADE_PAY"
        model.timeout_express = "30m"

        request = AlipayTradePagePayRequest(biz_model=model)
        request.notify_url = notify_url
        request.return_url = return_url
        return self._client().page_execute(request, http_method="GET")
