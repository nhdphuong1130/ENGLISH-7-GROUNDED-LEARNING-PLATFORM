from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
import hashlib
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from english7.api.errors import ApplicationError
from english7.db.models import AdminLoginChallenge, AdminTrustedDevice


def _utc(value: datetime) -> datetime:
    return (
        value.replace(tzinfo=timezone.utc)
        if value.tzinfo is None
        else value.astimezone(timezone.utc)
    )


class AdminDeviceService:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        clock: Callable[[], datetime] | None = None,
        trust_days: int = 30,
        challenge_minutes: int = 5,
    ) -> None:
        self._session_factory = session_factory
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._trust_days = trust_days
        self._challenge_minutes = challenge_minutes

    @staticmethod
    def hash_device(device_id: str) -> str:
        clean = device_id.strip()
        if len(clean) < 16 or len(clean) > 512:
            raise ApplicationError("admin_device_invalid", "Device identifier is invalid", 422)
        return hashlib.sha256(clean.encode("utf-8")).hexdigest()

    def is_trusted(self, admin_id: UUID, device_id: str) -> bool:
        device_hash = self.hash_device(device_id)
        now = _utc(self._clock())
        with self._session_factory() as session:
            row = session.scalar(
                select(AdminTrustedDevice).where(
                    AdminTrustedDevice.admin_id == admin_id,
                    AdminTrustedDevice.device_hash == device_hash,
                )
            )
            if row is None or row.revoked_at is not None or _utc(row.trusted_until) <= now:
                return False
            row.last_used_at = now
            session.commit()
            return True

    def create_challenge(
        self,
        admin_id: UUID,
        device_id: str,
        target_phone: str,
    ) -> AdminLoginChallenge:
        now = _utc(self._clock())
        row = AdminLoginChallenge(
            admin_id=admin_id,
            device_hash=self.hash_device(device_id),
            target_phone=target_phone,
            expires_at=now + timedelta(minutes=self._challenge_minutes),
            failed_attempts=0,
        )
        with self._session_factory() as session:
            session.add(row)
            session.commit()
            session.refresh(row)
            session.expunge(row)
        return row

    def verify_challenge(
        self,
        challenge_id: UUID,
        device_id: str,
        otp: str,
        sms_service,
    ) -> UUID:
        now = _utc(self._clock())
        device_hash = self.hash_device(device_id)
        with self._session_factory() as session:
            challenge = session.get(AdminLoginChallenge, challenge_id)
            if challenge is None or challenge.completed_at is not None:
                raise ApplicationError("admin_challenge_invalid", "Admin login challenge is invalid", 400)
            if _utc(challenge.expires_at) <= now:
                raise ApplicationError("admin_challenge_expired", "Admin login challenge has expired", 400)
            if challenge.device_hash != device_hash:
                raise ApplicationError("admin_device_mismatch", "Admin login challenge belongs to another device", 400)
            if challenge.failed_attempts >= 5:
                raise ApplicationError("admin_challenge_locked", "Too many invalid OTP attempts", 429)
            if not sms_service.verify_otp(challenge.target_phone, otp):
                challenge.failed_attempts += 1
                session.commit()
                raise ApplicationError("invalid_otp", "Mã OTP không chính xác hoặc đã hết hạn", 400)
            challenge.completed_at = now
            trusted = session.scalar(
                select(AdminTrustedDevice).where(
                    AdminTrustedDevice.admin_id == challenge.admin_id,
                    AdminTrustedDevice.device_hash == device_hash,
                )
            )
            if trusted is None:
                trusted = AdminTrustedDevice(
                    admin_id=challenge.admin_id,
                    device_hash=device_hash,
                    trusted_until=now + timedelta(days=self._trust_days),
                    last_used_at=now,
                )
                session.add(trusted)
            else:
                trusted.trusted_until = now + timedelta(days=self._trust_days)
                trusted.last_used_at = now
                trusted.revoked_at = None
            admin_id = challenge.admin_id
            session.commit()
            return admin_id

    def revoke_all(self, admin_id: UUID) -> None:
        now = _utc(self._clock())
        with self._session_factory() as session:
            session.execute(
                update(AdminTrustedDevice)
                .where(
                    AdminTrustedDevice.admin_id == admin_id,
                    AdminTrustedDevice.revoked_at.is_(None),
                )
                .values(revoked_at=now)
            )
            session.commit()
