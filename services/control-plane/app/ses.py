from __future__ import annotations

import json

from tencentcloud.common import credential
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.ses.v20201002 import models, ses_client

from .config import Settings


class SesDeliveryError(RuntimeError):
    pass


class TencentSesSender:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def send_registration_code(self, destination: str, code: str) -> str:
        if not self.settings.ses_enabled:
            raise SesDeliveryError("邮件验证码服务尚未配置")
        try:
            cred = credential.Credential(
                self.settings.ses_secret_id_value,
                self.settings.ses_secret_key_value,
            )
            http_profile = HttpProfile()
            http_profile.endpoint = "ses.tencentcloudapi.com"
            client_profile = ClientProfile(httpProfile=http_profile)
            client = ses_client.SesClient(cred, self.settings.ses_region, client_profile)
            request = models.SendEmailRequest()
            request.FromEmailAddress = f"小妤数字员工 <{self.settings.ses_from_email}>"
            request.Destination = [destination]
            request.Subject = "小妤数字员工注册验证码"
            template = models.Template()
            template.TemplateID = int(self.settings.ses_template_id)
            # The approved Tencent SES template uses {{xxx}} as its single
            # variable. TemplateData keys must match the placeholder exactly.
            template.TemplateData = json.dumps({"xxx": code}, ensure_ascii=False)
            request.Template = template
            response = client.SendEmail(request)
            return str(response.MessageId or "")
        except TencentCloudSDKException as exc:
            raise SesDeliveryError(f"验证码邮件发送失败：{exc.code}") from exc
        except Exception as exc:
            raise SesDeliveryError("验证码邮件发送失败") from exc
