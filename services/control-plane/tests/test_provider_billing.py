from types import SimpleNamespace

from app.provider_billing import ProviderBillingClient


def billing_client(project: str) -> ProviderBillingClient:
    client = ProviderBillingClient.__new__(ProviderBillingClient)
    client.settings = SimpleNamespace(provider_billing_project=project)
    return client


def test_billing_filter_accepts_ark_lines_for_configured_project():
    item = {
        "ProductZh": "火山方舟大模型服务平台",
        "ProjectName": "szyg-production",
    }
    assert billing_client("szyg-production")._is_ark_line(item)


def test_billing_filter_rejects_other_projects():
    item = {
        "ProductZh": "火山方舟大模型服务平台",
        "ProjectName": "personal-sandbox",
    }
    assert not billing_client("szyg-production")._is_ark_line(item)
