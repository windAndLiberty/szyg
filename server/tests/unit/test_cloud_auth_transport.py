import httpx


def test_cloud_requests_use_connection_only_retries(monkeypatch, tmp_path):
    import szyg.cloud_auth as cloud_auth_module

    monkeypatch.setenv("SZYG_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SZYG_CLOUD_ENABLED", "true")
    monkeypatch.setenv("SZYG_CONTROL_URL", "https://control.example.test")

    seen: dict[str, object] = {}

    class FakeTransport:
        def __init__(self, *, retries):
            seen["retries"] = retries

    class FakeResponse:
        status_code = 200
        content = b'{"status":"ok"}'

        @staticmethod
        def json():
            return {"status": "ok"}

    class FakeClient:
        def __init__(self, *, timeout, trust_env, transport):
            seen.update(timeout=timeout, trust_env=trust_env, transport=transport)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def request(self, method, url, *, json, headers):
            seen.update(method=method, url=url, json=json, headers=headers)
            return FakeResponse()

    monkeypatch.setattr(cloud_auth_module.httpx, "HTTPTransport", FakeTransport)
    monkeypatch.setattr(cloud_auth_module.httpx, "Client", FakeClient)

    manager = cloud_auth_module.CloudAuthManager()
    result = manager._request("GET", "/health")

    assert result == {"status": "ok"}
    assert seen["retries"] == 2
    assert seen["trust_env"] is False
    assert seen["url"] == "https://control.example.test/health"


def test_cloud_transport_errors_remain_user_safe_and_are_logged(monkeypatch, tmp_path, caplog):
    import szyg.cloud_auth as cloud_auth_module

    monkeypatch.setenv("SZYG_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SZYG_CLOUD_ENABLED", "true")
    monkeypatch.setenv("SZYG_CONTROL_URL", "https://control.example.test")

    class FakeTransport:
        def __init__(self, *, retries):
            self.retries = retries

    class FailingClient:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def request(self, method, url, **_kwargs):
            request = httpx.Request(method, url)
            raise httpx.ConnectError("connection refused", request=request)

    monkeypatch.setattr(cloud_auth_module.httpx, "HTTPTransport", FakeTransport)
    monkeypatch.setattr(cloud_auth_module.httpx, "Client", FailingClient)

    manager = cloud_auth_module.CloudAuthManager()
    with caplog.at_level("WARNING", logger=cloud_auth_module.__name__):
        try:
            manager._request("POST", "/api/v1/auth/login", json_body={"email": "hidden@example.test"})
        except cloud_auth_module.CloudAuthError as exc:
            assert str(exc) == "云账户服务暂时不可用"
        else:
            raise AssertionError("CloudAuthError was not raised")

    assert "method=POST" in caplog.text
    assert "path=/api/v1/auth/login" in caplog.text
    assert "hidden@example.test" not in caplog.text
