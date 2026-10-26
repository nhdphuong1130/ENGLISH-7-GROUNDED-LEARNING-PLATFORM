from datetime import date, timedelta
from functools import lru_cache
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from english7.api.errors import ApplicationError
from english7.core.security import PasswordHasher, TokenService
from english7.core.settings import get_settings
from english7.db.session import get_session_factory
from english7.modules.auth.domain import AuthUser, ProfileGender
from english7.modules.auth.repository import SQLAlchemyAuthRepository
from english7.modules.auth.service import AuthService
from english7.modules.auth.admin_device_service import AdminDeviceService
from english7.modules.auth.sms_service import SmsOtpService, get_sms_service

router = APIRouter(prefix="/auth", tags=["auth"])
bearer = HTTPBearer(auto_error=False)


class CredentialsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    device_id: str | None = Field(default=None, min_length=16, max_length=512)


class UserResponse(BaseModel):
    id: str
    email: str
    role: str
    full_name: str | None
    date_of_birth: date | None
    gender: ProfileGender | None
    school_name: str | None
    class_name: str | None

    @classmethod
    def from_user(cls, user: AuthUser) -> "UserResponse":
        return cls(
            id=str(user.id),
            email=user.email,
            role=user.role,
            full_name=user.full_name,
            date_of_birth=user.date_of_birth,
            gender=user.gender,
            school_name=user.school_name,
            class_name=user.class_name,
        )


class ProfileUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None, max_length=255)
    date_of_birth: date | None = None
    gender: ProfileGender | None = None
    school_name: str | None = Field(default=None, max_length=255)
    class_name: str | None = Field(default=None, max_length=100)


class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(default="", max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)


class TokenResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_token: str
    token_type: str = "bearer"


class AdminLoginChallengeResponse(BaseModel):
    challenge_id: UUID
    masked_phone: str
    expires_in_seconds: int = 300


class AdminLoginVerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    challenge_id: UUID
    device_id: str = Field(min_length=16, max_length=512)
    otp: str = Field(min_length=4, max_length=10)


class SendOtpRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phone: str = Field(min_length=9, max_length=20)
    channel: str = Field(default="sms", pattern="^(sms|voice)$")
    purpose: str = Field(default="any", pattern="^(login|register|reset_password|any)$")


class SendOtpResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = "success"
    message: str


class VerifyOtpRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phone: str = Field(min_length=9, max_length=20)
    otp: str = Field(min_length=4, max_length=10)


class RegisterPhoneRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phone: str = Field(min_length=9, max_length=20)
    otp: str = Field(min_length=4, max_length=10)
    password: str = Field(min_length=8, max_length=128)


class ResetPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phone: str = Field(min_length=9, max_length=20)
    otp: str = Field(min_length=4, max_length=10)
    new_password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)


class SimpleMessageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = "success"
    message: str


@lru_cache
def get_auth_service() -> AuthService:
    settings = get_settings()
    secret = settings.jwt_secret.get_secret_value() if settings.jwt_secret else None
    lifetime = (
        timedelta(minutes=settings.access_token_minutes)
        if settings.access_token_minutes is not None
        else None
    )
    return AuthService(
        SQLAlchemyAuthRepository(lambda: get_session_factory()()),
        PasswordHasher(),
        TokenService(
            secret=secret,
            algorithm=settings.jwt_algorithm,
            lifetime=lifetime,
        ),
    )


def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer),
    ],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthUser:
    if credentials is None:
        raise ApplicationError(
            code="unauthorized",
            message="Authentication is required",
            status_code=401,
        )
    return service.authenticate_token(credentials.credentials)


def get_admin_device_service() -> AdminDeviceService:
    return AdminDeviceService(lambda: get_session_factory()())


def get_admin_otp_phone() -> str | None:
    return get_settings().admin_otp_phone


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: CredentialsRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> UserResponse:
    user = service.register(payload.email, payload.password)
    return UserResponse.from_user(user)


@router.post("/login", response_model=TokenResponse | AdminLoginChallengeResponse)
def login(
    payload: CredentialsRequest,
    response: Response,
    service: Annotated[AuthService, Depends(get_auth_service)],
    device_service: Annotated[AdminDeviceService, Depends(get_admin_device_service)],
    sms_service: Annotated[SmsOtpService, Depends(get_sms_service)],
    admin_phone: Annotated[str | None, Depends(get_admin_otp_phone)],
) -> TokenResponse | AdminLoginChallengeResponse:
    user = service.verify_credentials(payload.email, payload.password)
    if user.role != "admin":
        return TokenResponse(access_token=service.issue_token(user))
    if payload.device_id is None:
        raise ApplicationError("admin_device_required", "Admin login requires a device identifier", 422)
    if device_service.is_trusted(user.id, payload.device_id):
        return TokenResponse(access_token=service.issue_token(user))
    if not admin_phone or not admin_phone.strip():
        raise ApplicationError("admin_otp_not_configured", "Admin OTP phone is not configured", 503)
    sms_service.send_otp(admin_phone)
    challenge = device_service.create_challenge(user.id, payload.device_id, admin_phone)
    digits = "".join(character for character in admin_phone if character.isdigit())
    masked = f"***{digits[-3:]}" if digits else "***"
    response.status_code = status.HTTP_202_ACCEPTED
    return AdminLoginChallengeResponse(challenge_id=challenge.id, masked_phone=masked)


@router.post("/admin-login/verify", response_model=TokenResponse)
def verify_admin_login(
    payload: AdminLoginVerifyRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
    device_service: Annotated[AdminDeviceService, Depends(get_admin_device_service)],
    sms_service: Annotated[SmsOtpService, Depends(get_sms_service)],
) -> TokenResponse:
    admin_id = device_service.verify_challenge(
        payload.challenge_id,
        payload.device_id,
        payload.otp,
        sms_service,
    )
    user = service.repository.get_by_id(admin_id)
    if user is None or user.role != "admin" or not user.is_active:
        raise ApplicationError("admin_not_found", "Admin account is unavailable", 401)
    return TokenResponse(access_token=service.issue_token(user))


@router.post("/otp/send", response_model=SendOtpResponse)
def send_otp(
    payload: SendOtpRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    sms_service: Annotated[SmsOtpService, Depends(get_sms_service)],
) -> SendOtpResponse:
    target_phone = payload.phone.strip()
    if payload.purpose == "register":
        existing = auth_service.find_phone_user(payload.phone)
        if existing is not None:
            raise ApplicationError(
                code="phone_already_registered",
                message="Số điện thoại này đã được đăng ký tài khoản. Vui lòng đăng nhập lại hoặc chọn Quên mật khẩu.",
                status_code=409,
            )
    elif payload.purpose == "reset_password":
        existing = auth_service.find_phone_user(payload.phone)
        if existing is None:
            raise ApplicationError(
                code="phone_not_found",
                message="Số điện thoại hoặc email này chưa được đăng ký trong hệ thống.",
                status_code=404,
            )
        if existing.email.startswith("phone_"):
            digits = "".join(c for c in existing.email.split("@")[0] if c.isdigit())
            target_phone = f"+{digits}"

    message = sms_service.send_otp(target_phone, channel=payload.channel)
    return SendOtpResponse(status="success", message=message)


@router.post("/otp/verify", response_model=TokenResponse)
def verify_otp(
    payload: VerifyOtpRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
    sms_service: Annotated[SmsOtpService, Depends(get_sms_service)],
) -> TokenResponse:
    if not sms_service.verify_otp(payload.phone, payload.otp):
        raise ApplicationError(
            code="invalid_otp",
            message="Mã OTP không chính xác hoặc đã hết hạn",
            status_code=400,
        )
    token = service.login_or_register_phone(payload.phone)
    return TokenResponse(access_token=token)


@router.post("/otp/validate", response_model=SimpleMessageResponse)
def validate_otp(
    payload: VerifyOtpRequest,
    sms_service: Annotated[SmsOtpService, Depends(get_sms_service)],
) -> SimpleMessageResponse:
    target_phone = payload.phone.strip()
    if not sms_service.check_otp(target_phone, payload.otp):
        raise ApplicationError(
            code="invalid_otp",
            message="Mã OTP không chính xác hoặc đã hết hạn",
            status_code=400,
        )
    return SimpleMessageResponse(status="success", message="Mã OTP chính xác")


@router.post("/register-phone", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register_phone(
    payload: RegisterPhoneRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
    sms_service: Annotated[SmsOtpService, Depends(get_sms_service)],
) -> TokenResponse:
    if not sms_service.verify_otp(payload.phone, payload.otp):
        raise ApplicationError(
            code="invalid_otp",
            message="Mã OTP không chính xác hoặc đã hết hạn",
            status_code=400,
        )
    existing = service.find_phone_user(payload.phone)
    if existing is not None:
        raise ApplicationError(
            code="phone_already_registered",
            message="Số điện thoại này đã được đăng ký tài khoản. Vui lòng đăng nhập lại hoặc chọn Quên mật khẩu.",
            status_code=409,
        )
    token = service.register_phone(payload.phone, payload.password)
    return TokenResponse(access_token=token)


@router.post("/reset-password", response_model=SimpleMessageResponse)
def reset_password(
    payload: ResetPasswordRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
    sms_service: Annotated[SmsOtpService, Depends(get_sms_service)],
) -> SimpleMessageResponse:
    if payload.new_password != payload.confirm_password:
        raise ApplicationError(
            code="password_confirmation_mismatch",
            message="Mật khẩu xác nhận không khớp",
            status_code=422,
        )
    target_phone = payload.phone.strip()
    existing = service.find_phone_user(payload.phone)
    if existing is not None and existing.email.startswith("phone_"):
        digits = "".join(c for c in existing.email.split("@")[0] if c.isdigit())
        target_phone = f"+{digits}"

    if not sms_service.verify_otp(target_phone, payload.otp):
        raise ApplicationError(
            code="invalid_otp",
            message="Mã OTP không chính xác hoặc đã hết hạn",
            status_code=400,
        )
    service.reset_password_by_phone(payload.phone, payload.new_password)
    return SimpleMessageResponse(
        status="success",
        message="Đặt lại mật khẩu thành công. Vui lòng đăng nhập bằng mật khẩu mới.",
    )


@router.get("/me", response_model=UserResponse)
def me(user: Annotated[AuthUser, Depends(get_current_user)]) -> UserResponse:
    return UserResponse.from_user(user)


@router.patch("/me", response_model=UserResponse)
def update_me(
    payload: ProfileUpdateRequest,
    user: Annotated[AuthUser, Depends(get_current_user)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> UserResponse:
    updated = service.update_profile(
        user.id,
        payload.model_dump(exclude_unset=True),
    )
    return UserResponse.from_user(updated)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: ChangePasswordRequest,
    user: Annotated[AuthUser, Depends(get_current_user)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> Response:
    service.change_password(
        user.id,
        current_password=payload.current_password,
        new_password=payload.new_password,
        confirm_password=payload.confirm_password,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
