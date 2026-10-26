import json
from unittest.mock import MagicMock, patch
import pytest

from english7.api.errors import ApplicationError
from english7.modules.auth.sms_service import SmsOtpService


def test_normalize_phone() -> None:
    assert SmsOtpService.normalize_phone("0365218732") == "+84365218732"
    assert SmsOtpService.normalize_phone("+84365218732") == "+84365218732"
    assert SmsOtpService.normalize_phone("84365218732") == "+84365218732"
    assert SmsOtpService.normalize_phone("0912 345 678") == "+84912345678"


def test_send_and_verify_otp_dev_mode() -> None:
    service = SmsOtpService(
        account_sid="test_sid",
        auth_token=None,
        from_phone="+17372508034",
        ttl_seconds=300,
    )
    result = service.send_otp("0365218732")
    assert "Mã OTP đã được tạo" in result

    target = "+84365218732"
    assert target in service._store
    code, _ = service._store[target]
    assert len(code) == 6

    # Wrong OTP fails
    assert not service.verify_otp("0365218732", "000000")

    # Correct OTP succeeds and clears entry
    assert service.verify_otp("0365218732", code)
    assert not service.verify_otp("0365218732", code)


def test_verify_otp_expired() -> None:
    service = SmsOtpService(
        account_sid="test_sid",
        auth_token=None,
        from_phone="+17372508034",
        ttl_seconds=-1,
    )
    service.send_otp("0365218732")
    target = "+84365218732"
    code, _ = service._store[target]
    assert not service.verify_otp("0365218732", code)


@patch("urllib.request.urlopen")
def test_send_otp_twilio_success(mock_urlopen: MagicMock) -> None:
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({"sid": "SM12345", "status": "queued"}).encode("utf-8")
    mock_urlopen.return_value.__enter__.return_value = mock_response

    service = SmsOtpService(
        account_sid="AC_TEST_DUMMY_SID_FOR_UNITTEST",
        auth_token="dummy_token",
        from_phone="+10000000000",
    )
    msg = service.send_otp("+84365218732")
    assert "thành công qua tin nhắn SMS" in msg
    assert mock_urlopen.called


@patch("urllib.request.urlopen")
def test_send_otp_android_gateway_success(mock_urlopen: MagicMock) -> None:
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({"id": "msg-123", "state": "Pending"}).encode("utf-8")
    mock_urlopen.return_value.__enter__.return_value = mock_response

    service = SmsOtpService(
        account_sid="test_sid",
        auth_token=None,
        from_phone="+17372508034",
        gateway_url="http://127.0.0.1:8080",
        gateway_username="sms",
        gateway_password="pwd",
    )
    msg = service.send_otp("+84365218732")
    assert "thành công qua tin nhắn SMS" in msg
    assert mock_urlopen.called


@patch("urllib.request.urlopen", side_effect=OSError("tunnel offline"))
def test_configured_android_gateway_failure_does_not_fake_success(
    mock_urlopen: MagicMock,
) -> None:
    service = SmsOtpService(
        account_sid="",
        auth_token=None,
        from_phone="",
        gateway_url="https://sms-gateway.example.com",
        gateway_username="sms",
        gateway_password="pwd",
    )

    with pytest.raises(ApplicationError) as exc_info:
        service.send_otp("+84365218732")

    assert exc_info.value.code == "sms_gateway_unavailable"
    assert exc_info.value.status_code == 503


def test_send_otp_voice_not_configured_raises() -> None:
    service = SmsOtpService(
        account_sid="test_sid",
        auth_token=None,
        from_phone="+17372508034",
    )
    with pytest.raises(ApplicationError) as exc_info:
        service.send_otp("+84365218732", channel="voice")
    assert exc_info.value.code == "clicksend_not_configured"


@patch("urllib.request.urlopen")
def test_send_otp_voice_clicksend_success(mock_urlopen: MagicMock) -> None:
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({"http_code": 200, "response_code": "SUCCESS"}).encode("utf-8")
    mock_urlopen.return_value.__enter__.return_value = mock_response

    service = SmsOtpService(
        account_sid="test_sid",
        auth_token=None,
        from_phone="+17372508034",
        clicksend_username="user123",
        clicksend_api_key="key123",
    )
    msg = service.send_otp("+84365218732", channel="voice")
    assert "cuộc gọi thoại" in msg
    assert mock_urlopen.called


@patch("urllib.request.urlopen")
def test_send_otp_voice_clicksend_insufficient_credit(mock_urlopen: MagicMock) -> None:
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({
        "http_code": 200,
        "response_code": "SUCCESS",
        "data": {
            "messages": [{"status": "INSUFFICIENT_CREDIT"}]
        }
    }).encode("utf-8")
    mock_urlopen.return_value.__enter__.return_value = mock_response

    service = SmsOtpService(
        account_sid="test_sid",
        auth_token=None,
        from_phone="+17372508034",
        clicksend_username="user123",
        clicksend_api_key="key123",
    )
    with pytest.raises(ApplicationError) as exc_info:
        service.send_otp("+84365218732", channel="voice")
    assert exc_info.value.code == "insufficient_credit"


def test_otp_is_randomly_generated_and_not_hardcoded() -> None:
    service = SmsOtpService(
        account_sid="test_sid",
        auth_token=None,
        from_phone="+17372508034",
    )
    generated_codes = set()
    for _ in range(50):
        service.send_otp("0365218732")
        code, _ = service._store["+84365218732"]
        assert len(code) == 6
        assert code.isdigit()
        generated_codes.add(code)
    # 50 random 6-digit numbers should produce at least 45 unique codes
    assert len(generated_codes) >= 45


