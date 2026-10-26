import runpy
from pathlib import Path

from sqlalchemy.dialects import mssql
from sqlalchemy.schema import CreateTable

from english7.db.base import Base


def test_frozen_learning_schema_matches_current_models():
    migration = runpy.run_path(str(Path(__file__).parents[3] / 'alembic/versions/0007_learning.py'))
    metadata = migration['schema']()
    for name in migration['TABLES']:
        frozen, model = metadata.tables[name], Base.metadata.tables[name]
        # Later additive migrations may add columns, but must never rewrite or
        # invalidate the schema frozen in this historical revision.
        assert set(frozen.c.keys()) <= set(model.c.keys())
        for column in frozen.c:
            actual = model.c[column.name]
            assert column.nullable == actual.nullable
            assert column.primary_key == actual.primary_key
            assert str(column.type.compile(dialect=mssql.dialect())) == str(actual.type.compile(dialect=mssql.dialect()))
            assert {f.target_fullname for f in column.foreign_keys} == {f.target_fullname for f in actual.foreign_keys}
        assert str(CreateTable(frozen).compile(dialect=mssql.dialect()))
