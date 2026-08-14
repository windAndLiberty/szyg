from __future__ import annotations

import json
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

import httpx
from volcengine.Credentials import Credentials
from volcengine.auth.SignerV4 import SignerV4
from volcengine.base.Request import Request

from .config import get_settings


ARK_MARKERS = ("ark", "方舟", "豆包", "大模型", "seed")


class ProviderBillingClient:
    host = "open.volcengineapi.com"

    def __init__(self) -> None:
        self.settings = get_settings()

    def _signed_request(self, body: dict) -> dict:
        request = Request()
        request.host = self.host
        request.method = "POST"
        request.path = "/"
        request.query = {"Action": "ListBillDetail", "Version": "2022-01-01"}
        request.headers = {"Host": self.host, "Content-Type": "application/json"}
        request.body = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
        credentials = Credentials(
            self.settings.provider_billing_access_key,
            self.settings.provider_billing_secret_key,
            "billing",
            self.settings.provider_billing_region,
        )
        SignerV4.sign(request, credentials)
        response = httpx.post(
            f"https://{self.host}/",
            params=request.query,
            headers=request.headers,
            content=request.body,
            timeout=60,
        )
        response.raise_for_status()
        return response.json()

    def _is_ark_line(self, item: dict) -> bool:
        text = " ".join(str(item.get(key) or "") for key in (
            "Product", "ProductZh", "ConfigurationName", "SolutionZh", "SubjectName"
        )).lower()
        if not any(marker in text for marker in ARK_MARKERS):
            return False
        expected_project = self.settings.provider_billing_project.strip().lower()
        if not expected_project:
            return True
        project_text = " ".join(str(item.get(key) or "") for key in (
            "Project", "ProjectId", "ProjectName", "ProjectDisplayName"
        )).lower()
        return expected_project in project_text

    def fetch_daily_cost(self, billing_date: date) -> tuple[int, int, str]:
        offset = 0
        total = None
        amount = Decimal("0")
        matched_lines = 0
        request_id = ""
        while total is None or offset < total:
            payload = {
                "BillPeriod": billing_date.strftime("%Y-%m"),
                "ExpenseDate": billing_date.isoformat(),
                "GroupTerm": 0,
                "GroupPeriod": 2,
                "Limit": 300,
                "Offset": offset,
                "NeedRecordNum": 1,
                "IgnoreZero": 1,
            }
            data = self._signed_request(payload)
            metadata = data.get("ResponseMetadata") or data.get("Metadata") or {}
            request_id = str(metadata.get("RequestId") or request_id)
            result = data.get("Result") or data
            rows = result.get("List") or []
            for item in rows:
                if self._is_ark_line(item):
                    amount += Decimal(str(item.get("PayableAmount") or item.get("PaidAmount") or "0"))
                    matched_lines += 1
            total = int(result.get("Total") or len(rows))
            offset += len(rows)
            if not rows:
                break
        micros = int((amount * Decimal("1000000")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        return micros, matched_lines, request_id
