from pathlib import Path

from sqlalchemy.dialects import mssql

from english7.modules.admin.dashboard_service import AdminDashboardService


class _CapturingSession:
    def __init__(self) -> None:
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def scalar(self, statement):
        self.statements.append(statement)
        return 0


def test_admin_dashboard_boolean_filters_compile_for_sql_server() -> None:
    session = _CapturingSession()
    AdminDashboardService(lambda: session).summary()

    sql = "\n".join(
        str(statement.compile(dialect=mssql.dialect()))
        for statement in session.statements
    )

    assert " IS 1" not in sql
    assert " IS 0" not in sql
    assert "is_active = 1" in sql
    assert "is_active = 0" in sql


def test_backend_does_not_use_is_for_boolean_values() -> None:
    source_root = Path(__file__).parents[2] / "src" / "english7"
    offenders = []
    for path in source_root.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        for token in (".is_(True)", ".is_(False)"):
            if token in source:
                offenders.append(f"{path.relative_to(source_root)}: {token}")

    assert offenders == []
