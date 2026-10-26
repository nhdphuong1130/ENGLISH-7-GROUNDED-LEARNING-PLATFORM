import base64
import json
import logging
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from english7.api.errors import ApplicationError
from english7.core.settings import get_settings

logger = logging.getLogger(__name__)


@dataclass
class SmsOtpService:
    account_sid: str
    auth_token: str | None
    from_phone: str
    gateway_url: str | None = None
    gateway_username: str | None = None
    gateway_password: str | None = None
    clicksend_username: str | None = None
    clicksend_api_key: str | None = None
    ttl_seconds: int = 300
    _store: dict[str, tuple[str, float]] = field(default_factory=dict)

    @staticmethod
    def normalize_phone(phone: str) -> str:
        cleaned = "".join(c for c in phone if c.isdigit() or c == "+").strip()
        if cleaned.startswith("+"):
            return cleaned
        if cleaned.startswith("0"):
            return f"+84{cleaned[1:]}"
        if cleaned.startswith("84"):
            return f"+{cleaned}"
        return f"+84{cleaned}"

    def send_otp(self, phone: str, channel: str = "sms") -> str:
        target_phone = self.normalize_phone(phone)
        local_phone = f"0{target_phone[3:]}" if target_phone.startswith("+84") else target_phone
        code = f"{secrets.randbelow(900000) + 100000}"
        expire_at = time.time() + self.ttl_seconds
        self._store[target_phone] = (code, expire_at)

        logger.info(
            "Generated an OTP for a masked phone via channel '%s' "
            "(expires in %ss)",
            channel,
            self.ttl_seconds,
        )

        # 1. Voice Call Channel (ClickSend Voice API)
        if channel == "voice":
            if not self.clicksend_username or not self.clicksend_api_key:
                raise ApplicationError(
                    code="clicksend_not_configured",
                    message="Dịch vụ cuộc gọi ClickSend chưa được cấu hình. Vui lòng thêm ENGLISH7_CLICKSEND_USERNAME và ENGLISH7_CLICKSEND_API_KEY vào file .env",
                    status_code=503,
                )
            voice_url = "https://rest.clicksend.com/v3/voice/send"
            spoken_code = " . ".join(list(code))
            voice_body = json.dumps({
                "messages": [
                    {
                        "to": target_phone,
                        "body": f"Ma xac thuc English 7 cua ban la {spoken_code}. Xin nhac lai, {spoken_code}.",
                        "voice": "female",
                        "lang": "vi-vn",
                    }
                ]
            }).encode("utf-8")
            credentials = f"{self.clicksend_username}:{self.clicksend_api_key}"
            encoded_auth = base64.b64encode(credentials.encode("utf-8")).decode("ascii")

            req = urllib.request.Request(voice_url, data=voice_body, method="POST")
            req.add_header("Authorization", f"Basic {encoded_auth}")
            req.add_header("Content-Type", "application/json")

            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    logger.info(f"ClickSend Voice Call dispatched to {target_phone}: {resp_data}")
                    messages = resp_data.get("data", {}).get("messages", [])
                    if messages:
                        status = messages[0].get("status")
                        if status == "INSUFFICIENT_CREDIT":
                            raise ApplicationError(
                                code="insufficient_credit",
                                message="Tài khoản ClickSend không đủ số dư để gửi cuộc gọi (vui lòng nạp thêm tiền hoặc chọn 'Gửi mã OTP qua SMS' miễn phí).",
                                status_code=402,
                            )
                        if status not in ("SUCCESS", "Sent", "QUEUED", None):
                            raise ApplicationError(
                                code="voice_send_failed",
                                message=f"ClickSend trả về trạng thái lỗi: {status}",
                                status_code=502,
                            )
                    return "Mã OTP đang được gửi qua cuộc gọi thoại tới số điện thoại của bạn"
            except ApplicationError:
                raise
            except urllib.error.HTTPError as e:
                error_body = e.read().decode("utf-8", errors="ignore")
                logger.error(f"ClickSend Voice API error ({e.code}): {error_body}")
                raise ApplicationError(
                    code="voice_send_failed",
                    message=f"Gửi cuộc gọi qua ClickSend thất bại: {error_body}",
                    status_code=502,
                ) from e
            except Exception as e:
                logger.error(f"Unexpected error when calling ClickSend Voice: {e}")
                raise ApplicationError(
                    code="voice_service_unavailable",
                    message=f"Không thể kết nối đến dịch vụ cuộc gọi: {e}",
                    status_code=503,
                ) from e

        # 2. SMS Channel (Primary: Android Local SIM SMS Gateway if configured)
        if self.gateway_url and self.gateway_username and self.gateway_password:
            candidate_urls = [self.gateway_url.rstrip("/")]
            if "127.0.0.1" in self.gateway_url or "localhost" in self.gateway_url:
                candidate_urls.extend([
                    "http://host.docker.internal:8088",
                    "http://host.docker.internal:8080",
                    "http://192.168.1.219:8080",
                ])
            for base_url in candidate_urls:
                try:
                    gw_url = f"{base_url}/message"
                    gw_body = json.dumps({
                        "message": f"Ma OTP English 7 cua ban la: {code}. Ma co hieu luc trong 5 phut.",
                        "phoneNumbers": [local_phone],
                    }).encode("utf-8")
                    credentials = f"{self.gateway_username}:{self.gateway_password}"
                    encoded_auth = base64.b64encode(credentials.encode("utf-8")).decode("ascii")

                    req = urllib.request.Request(gw_url, data=gw_body, method="POST")
                    req.add_header("Authorization", f"Basic {encoded_auth}")
                    req.add_header("Content-Type", "application/json")

                    with urllib.request.urlopen(req, timeout=5) as resp:
                        resp_data = json.loads(resp.read().decode("utf-8"))
                        logger.info(f"Android SIM Gateway dispatched SMS to {local_phone}, id: {resp_data.get('id')}")
                        return "Mã OTP đã được gửi thành công qua tin nhắn SMS"
                except Exception as e:
                    logger.debug(f"Android Gateway candidate {base_url} failed: {e}")

            if not self.auth_token:
                self._store.pop(target_phone, None)
                raise ApplicationError(
                    code="sms_gateway_unavailable",
                    message=(
                        "Không thể kết nối tới điện thoại gửi SMS. "
                        "Hãy kiểm tra SMS Gateway và tunnel HTTPS."
                    ),
                    status_code=503,
                )

        # 3. Secondary SMS: Twilio REST API
        if self.auth_token:
            url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"
            form_data = urllib.parse.urlencode({
                "To": target_phone,
                "From": self.from_phone,
                "Body": f"Ma OTP English 7 cua ban la: {code}. Ma co hieu luc trong 5 phut.",
            }).encode("utf-8")

            credentials = f"{self.account_sid}:{self.auth_token}"
            encoded_auth = base64.b64encode(credentials.encode("utf-8")).decode("ascii")

            req = urllib.request.Request(url, data=form_data, method="POST")
            req.add_header("Authorization", f"Basic {encoded_auth}")
            req.add_header("Content-Type", "application/x-www-form-urlencoded")

            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    logger.info(f"Twilio SMS dispatched to {target_phone}, sid: {resp_data.get('sid')}")
                    return "Mã OTP đã được gửi thành công qua tin nhắn SMS"
            except urllib.error.HTTPError as e:
                error_body = e.read().decode("utf-8", errors="ignore")
                logger.error(f"Twilio API error ({e.code}): {error_body}")
                raise ApplicationError(
                    code="sms_send_failed",
                    message=f"Gửi SMS qua Twilio thất bại: {error_body}",
                    status_code=502,
                ) from e
            except Exception as e:
                logger.error(f"Unexpected error when sending SMS: {e}")
                raise ApplicationError(
                    code="sms_service_unavailable",
                    message=f"Không thể kết nối đến cổng SMS: {e}",
                    status_code=503,
                ) from e

        # 4. Fallback: Dev Mode
        logger.warning("[DEV MODE] SMS provider is not configured")
        return f"Mã OTP đã được tạo (Dev mode): {code}"

    def check_otp(self, phone: str, otp: str) -> bool:
        target_phone = self.normalize_phone(phone)
        entry = self._store.get(target_phone)
        if not entry:
            return False

        saved_code, expire_at = entry
        if time.time() > expire_at:
            self._store.pop(target_phone, None)
            return False

        return saved_code == otp.strip()

    def verify_otp(self, phone: str, otp: str) -> bool:
        target_phone = self.normalize_phone(phone)
        entry = self._store.get(target_phone)
        if not entry:
            return False

        saved_code, expire_at = entry
        if time.time() > expire_at:
            self._store.pop(target_phone, None)
            return False

        if saved_code == otp.strip():
            self._store.pop(target_phone, None)
            return True

        return False


_sms_service_instance: SmsOtpService | None = None


def get_sms_service() -> SmsOtpService:
    global _sms_service_instance
    if _sms_service_instance is None:
        settings = get_settings()
        auth_token = settings.twilio_auth_token.get_secret_value() if settings.twilio_auth_token else None
        gw_password = settings.sms_gateway_password.get_secret_value() if settings.sms_gateway_password else None
        clicksend_key = settings.clicksend_api_key.get_secret_value() if settings.clicksend_api_key else None
        _sms_service_instance = SmsOtpService(
            account_sid=settings.twilio_account_sid,
            auth_token=auth_token,
            from_phone=settings.twilio_from_phone,
            gateway_url=settings.sms_gateway_url,
            gateway_username=settings.sms_gateway_username,
            gateway_password=gw_password,
            clicksend_username=settings.clicksend_username,
            clicksend_api_key=clicksend_key,
        )
    return _sms_service_instance
