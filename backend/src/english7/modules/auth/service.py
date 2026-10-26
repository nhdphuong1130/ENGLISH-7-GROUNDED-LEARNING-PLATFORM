import secrets
from uuid import UUID

from english7.api.errors import ApplicationError
from english7.core.security import PasswordHasher, TokenService
from english7.modules.auth.domain import AuthUser, ProfileGender
from english7.modules.auth.repository import AuthRepository

PROFILE_TEXT_LIMITS = {
    "full_name": 255,
    "school_name": 255,
    "class_name": 100,
}
PROFILE_FIELDS = {*PROFILE_TEXT_LIMITS, "date_of_birth", "gender"}


class AuthService:
    def __init__(
        self,
        repository: AuthRepository,
        password_hasher: PasswordHasher,
        token_service: TokenService,
    ) -> None:
        self.repository = repository
        self.password_hasher = password_hasher
        self.token_service = token_service

    def register(self, email: str, password: str) -> AuthUser:
        normalized_email = email.strip().lower()
        if self.repository.get_by_email(normalized_email) is not None:
            raise ApplicationError(
                code="email_already_registered",
                message="Email is already registered",
                status_code=409,
            )
        user = AuthUser.new(
            email=normalized_email,
            password_hash=self.password_hasher.hash(password),
        )
        return self.repository.create(user)

    def verify_credentials(self, email: str, password: str) -> AuthUser:
        clean = email.strip().lower()
        user = self.repository.get_by_email(clean)
        if user is None:
            digits = "".join(c for c in clean if c.isdigit())
            if digits:
                if digits.startswith("0"):
                    digits = f"84{digits[1:]}"
                elif not digits.startswith("84"):
                    digits = f"84{digits}"
                phone_email = f"phone_{digits}@english7.edu.vn"
                user = self.repository.get_by_email(phone_email)

        if (
            user is None
            or not user.is_active
            or not self.password_hasher.verify(password, user.password_hash)
        ):
            raise ApplicationError(
                code="invalid_credentials",
                message="Email or password is incorrect",
                status_code=401,
            )
        return user

    def login(self, email: str, password: str) -> str:
        return self.token_service.issue(self.verify_credentials(email, password))

    def issue_token(self, user: AuthUser) -> str:
        return self.token_service.issue(user)

    @staticmethod
    def phone_to_email(phone: str) -> str:
        clean = "".join(c for c in phone if c.isdigit())
        if clean.startswith("0"):
            clean = f"84{clean[1:]}"
        elif not clean.startswith("84"):
            clean = f"84{clean}"
        return f"phone_{clean}@english7.edu.vn"

    def find_phone_user(self, phone_or_email: str) -> AuthUser | None:
        clean = phone_or_email.strip().lower()
        user = self.repository.get_by_email(clean)
        if user is not None:
            return user
        return self.repository.get_by_email(self.phone_to_email(clean))

    def register_phone(self, phone: str, password: str) -> str:
        phone_email = self.phone_to_email(phone)
        if self.repository.get_by_email(phone_email) is not None:
            raise ApplicationError(
                code="phone_already_registered",
                message="Số điện thoại này đã được đăng ký tài khoản. Vui lòng đăng nhập lại hoặc sử dụng 'Quên mật khẩu'.",
                status_code=409,
            )
        user = AuthUser.new(
            email=phone_email,
            password_hash=self.password_hasher.hash(password),
            role="student",
        )
        user = self.repository.create(user)
        return self.token_service.issue(user)

    def reset_password_by_phone(self, phone_or_email: str, new_password: str) -> None:
        user = self.find_phone_user(phone_or_email)
        if user is None:
            raise ApplicationError(
                code="phone_not_found",
                message="Không tìm thấy tài khoản với số điện thoại hoặc email này",
                status_code=404,
            )
        self.repository.update_password_hash(
            user.id,
            self.password_hasher.hash(new_password),
        )

    def login_or_register_phone(self, phone: str) -> str:
        phone_email = self.phone_to_email(phone)
        user = self.repository.get_by_email(phone_email)
        if user is None:
            user = AuthUser.new(
                email=phone_email,
                password_hash=self.password_hasher.hash(secrets.token_urlsafe(16)),
                role="student",
            )
            user = self.repository.create(user)
        return self.token_service.issue(user)

    def authenticate_token(self, encoded: str) -> AuthUser:
        claims = self.token_service.decode(encoded)
        user = self.repository.get_by_id(claims.subject)
        if user is None or not user.is_active:
            raise ApplicationError(
                code="invalid_token",
                message="Access token is invalid",
                status_code=401,
            )
        return user

    def update_profile(
        self,
        user_id: UUID,
        changes: dict[str, object],
    ) -> AuthUser:
        invalid_fields = set(changes) - PROFILE_FIELDS
        if invalid_fields:
            raise ApplicationError(
                code="profile_fields_invalid",
                message="Profile contains unsupported fields",
                status_code=422,
                details={"fields": sorted(invalid_fields)},
            )

        normalized = dict(changes)
        for field, limit in PROFILE_TEXT_LIMITS.items():
            if field not in normalized:
                continue
            value = normalized[field]
            if value is None:
                normalized[field] = None
            elif isinstance(value, str):
                normalized[field] = value.strip() or None
            else:
                raise ApplicationError(
                    code="profile_field_invalid",
                    message=f"{field} must be text or null",
                    status_code=422,
                )
            if normalized[field] is not None and len(normalized[field]) > limit:  # type: ignore[arg-type]
                raise ApplicationError(
                    code="profile_field_too_long",
                    message=f"{field} is too long",
                    status_code=422,
                )

        if "gender" in normalized and normalized["gender"] is not None:
            try:
                normalized["gender"] = ProfileGender(
                    str(normalized["gender"])
                ).value
            except ValueError as error:
                raise ApplicationError(
                    code="profile_gender_invalid",
                    message="Gender is invalid",
                    status_code=422,
                ) from error

        updated = self.repository.update_profile(user_id, normalized)
        if updated is None:
            raise ApplicationError(
                code="user_not_found",
                message="User was not found",
                status_code=404,
            )
        return updated

    def change_password(
        self,
        user_id: UUID,
        *,
        current_password: str,
        new_password: str,
        confirm_password: str,
    ) -> None:
        if new_password != confirm_password:
            raise ApplicationError(
                code="password_confirmation_mismatch",
                message="Password confirmation does not match",
                status_code=422,
            )

        user = self.repository.get_by_id(user_id)
        if user is None:
            raise ApplicationError(
                code="user_not_found",
                message="User was not found",
                status_code=404,
            )
        is_phone_user = user.email.startswith("phone_")
        if not (is_phone_user and not current_password):
            if not self.password_hasher.verify(current_password, user.password_hash):
                raise ApplicationError(
                    code="current_password_invalid",
                    message="Current password is incorrect",
                    status_code=400,
                )
        if self.password_hasher.verify(new_password, user.password_hash):
            raise ApplicationError(
                code="password_unchanged",
                message="New password must be different",
                status_code=422,
            )

        changed = self.repository.update_password_hash(
            user_id,
            self.password_hasher.hash(new_password),
        )
        if not changed:
            raise ApplicationError(
                code="user_not_found",
                message="User was not found",
                status_code=404,
            )

    @staticmethod
    def authorize(user: AuthUser, allowed_roles: set[str]) -> AuthUser:
        if user.role not in allowed_roles:
            raise ApplicationError(
                code="forbidden",
                message="You do not have permission to perform this action",
                status_code=403,
            )
        return user
