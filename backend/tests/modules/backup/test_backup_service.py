from datetime import date, datetime
from io import StringIO
from pathlib import Path
from uuid import UUID, uuid4

from english7.cli import build_parser
from english7.modules.backup.service import (
    format_sql_literal,
    format_sql_string,
)


def test_format_sql_string_escaping() -> None:
    assert format_sql_string("Hello World") == "N'Hello World'"
    assert format_sql_string("It's fine") == "N'It''s fine'"
    assert format_sql_string("Line 1\nLine 2") == "N'Line 1' + CHAR(10) + N'Line 2'"
    assert format_sql_string("CR\r\nLF") == "N'CR' + CHAR(13) + CHAR(10) + N'LF'"
    assert format_sql_string("CR\rLF") == "N'CR' + CHAR(13) + N'LF'"
    assert format_sql_string("null\0byte") == "N'nullbyte'"


def test_format_sql_literal_types() -> None:
    assert format_sql_literal(None, "VARCHAR") == "NULL"
    assert format_sql_literal(True, "BIT") == "1"
    assert format_sql_literal(False, "BIT") == "0"
    assert format_sql_literal(123, "INT") == "123"
    assert format_sql_literal(45.67, "FLOAT") == "45.67"
    assert format_sql_literal(float("nan"), "FLOAT") == "NULL"
    assert format_sql_literal(float("inf"), "FLOAT") == "NULL"

    u = uuid4()
    assert format_sql_literal(u, "UNIQUEIDENTIFIER") == f"'{u}'"

    d = date(2026, 10, 16)
    assert format_sql_literal(d, "DATE") == "'2026-10-16'"

    dt = datetime(2026, 10, 16, 12, 0, 0)
    assert format_sql_literal(dt, "DATETIMEOFFSET") == "'2026-10-16T12:00:00'"

    payload = {"key": "value"}
    assert format_sql_literal(payload, "NVARCHAR") == "N'{\"key\": \"value\"}'"


def test_cli_parser_dump_sql() -> None:
    parser = build_parser()
    args = parser.parse_args(["dump-sql", "--database", "custom_db", "--output", "out.sql"])

    assert args.database == "custom_db"
    assert args.output == Path("out.sql")
