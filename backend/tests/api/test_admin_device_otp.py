from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from english7.core.security import PasswordHasher, TokenService
from english7.db.base import Base
from english7.db.models import Role, User
from english7.main import app
from english7.modules.auth.admin_device_service import AdminDeviceService
from english7.modules.auth.repository import SQLAlchemyAuthRepository
from english7.modules.auth.router import (
    get_admin_device_service,
    get_admin_otp_phone,
    get_auth_service,
    get_sms_service,
)
from english7.modules.auth.service import AuthService


class SmsStub:
    def __init__(self) -> None:
        self.sent: list[str] = []

    def send_otp(self, phone: str, channel: str = "sms") -> str:
        self.sent.append(phone)
        return "sent"

    def verify_otp(self, phone: str, otp: str) -> bool:
        return phone == "+84374423251" and otp == "123456"


def _dependencies():
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    hasher = PasswordHasher()
    with factory() as session:
        student_role = Role(name="student")
        admin_role = Role(name="admin")
        session.add_all([student_role, admin_role]); session.flush()
        session.add_all([
            User(email="student@example.com", password_hash=hasher.hash("student-password"), role_id=student_role.id),
            User(email="admin@example.com", password_hash=hasher.hash("admin-password"), role_id=admin_role.id),
        ])
        session.commit()
    auth = AuthService(SQLAlchemyAuthRepository(factory), hasher, TokenService(secret="test-secret-with-sufficient-length", algorithm="HS256", lifetime=timedelta(minutes=30), clock=lambda: datetime(2026, 10, 26, tzinfo=timezone.utc)))
    devices = AdminDeviceService(factory, clock=lambda: datetime(2026, 10, 26, tzinfo=timezone.utc))
    sms = SmsStub()
    return auth, devices, sms


def test_student_login_is_unchanged(client) -> None:
    auth, devices, sms = _dependencies()
    app.dependency_overrides[get_auth_service] = lambda: auth
    app.dependency_overrides[get_admin_device_service] = lambda: devices
    app.dependency_overrides[get_sms_service] = lambda: sms
    app.dependency_overrides[get_admin_otp_phone] = lambda: "+84374423251"
    try:
        response = client.post("/api/v1/auth/login", json={"email": "student@example.com", "password": "student-password", "device_id": "device-identifier-a"})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["access_token"]
    assert sms.sent == []


def test_new_admin_device_requires_otp_then_becomes_trusted(client) -> None:
    auth, devices, sms = _dependencies()
    app.dependency_overrides[get_auth_service] = lambda: auth
    app.dependency_overrides[get_admin_device_service] = lambda: devices
    app.dependency_overrides[get_sms_service] = lambda: sms
    app.dependency_overrides[get_admin_otp_phone] = lambda: "+84374423251"
    try:
        challenge = client.post("/api/v1/auth/login", json={"email": "admin@example.com", "password": "admin-password", "device_id": "device-identifier-a"})
        verified = client.post("/api/v1/auth/admin-login/verify", json={"challenge_id": challenge.json()["challenge_id"], "device_id": "device-identifier-a", "otp": "123456"})
        trusted = client.post("/api/v1/auth/login", json={"email": "admin@example.com", "password": "admin-password", "device_id": "device-identifier-a"})
    finally:
        app.dependency_overrides.clear()

    assert challenge.status_code == 202
    assert challenge.json()["masked_phone"].endswith("251")
    assert verified.status_code == 200
    assert verified.json()["access_token"]
    assert trusted.status_code == 200
    assert len(sms.sent) == 1


def test_admin_can_revoke_all_trusted_devices(client) -> None:
    auth, devices, sms = _dependencies()
    app.dependency_overrides[get_auth_service] = lambda: auth
    app.dependency_overrides[get_admin_device_service] = lambda: devices
    app.dependency_overrides[get_sms_service] = lambda: sms
    app.dependency_overrides[get_admin_otp_phone] = lambda: "+84374423251"
    try:
        first = client.post("/api/v1/auth/login", json={"email": "admin@example.com", "password": "admin-password", "device_id": "device-identifier-a"})
        verified = client.post("/api/v1/auth/admin-login/verify", json={"challenge_id": first.json()["challenge_id"], "device_id": "device-identifier-a", "otp": "123456"})
        token = verified.json()["access_token"]
        revoked = client.post("/api/v1/admin/trusted-devices/revoke-all", headers={"Authorization": f"Bearer {token}"})
        challenged_again = client.post("/api/v1/auth/login", json={"email": "admin@example.com", "password": "admin-password", "device_id": "device-identifier-a"})
    finally:
        app.dependency_overrides.clear()
    assert revoked.status_code == 204
    assert challenged_again.status_code == 202
