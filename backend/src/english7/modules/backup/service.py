from __future__ import annotations

import json
import math
from datetime import date, datetime
from typing import TextIO
from uuid import UUID

from sqlalchemy import MetaData, text
from sqlalchemy.engine import Engine


def format_sql_string(s: str) -> str:
    s = s.replace("\0", "").replace("'", "''")
    if "\r" not in s and "\n" not in s:
        return f"N'{s}'"
    s = s.replace("\r\n", "' + CHAR(13) + CHAR(10) + N'")
    s = s.replace("\n", "' + CHAR(10) + N'")
    s = s.replace("\r", "' + CHAR(13) + N'")
    return f"N'{s}'"


def format_sql_literal(val: object, col_type_str: str) -> str:
    if val is None:
        return "NULL"
    if isinstance(val, bool):
        return "1" if val else "0"
    if isinstance(val, (int, float)):
        if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
            return "NULL"
        return str(val)
    if isinstance(val, (datetime, date)):
        return f"'{val.isoformat()}'"
    if isinstance(val, UUID):
        return f"'{str(val)}'"
    if isinstance(val, (dict, list)):
        return format_sql_string(json.dumps(val, ensure_ascii=False))
    return format_sql_string(str(val))


class SqlDatabaseDumper:
    def __init__(self, engine: Engine, database_name: str = "english7") -> None:
        self.engine = engine
        self.database_name = database_name

    def dump(self, out: TextIO) -> None:
        meta = MetaData()
        meta.reflect(bind=self.engine)
        sorted_tables = meta.sorted_tables

        out.write("/*\n")
        out.write("========================================================================\n")
        out.write("English 7 Grounded Learning Platform - Database Backup\n")
        out.write(f"Database: {self.database_name}\n")
        out.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        out.write("========================================================================\n")
        out.write("*/\n")
        out.write("SET NOCOUNT ON;\n")
        out.write("SET QUOTED_IDENTIFIER ON;\n")
        out.write("SET ANSI_NULLS ON;\n")
        out.write("GO\n\n")
        out.write(f"USE [{self.database_name}];\n")
        out.write("GO\n\n")

        # 1. Drop existing foreign keys
        out.write("-- 1. Drop existing foreign keys\n")
        out.write("DECLARE @drop_fks NVARCHAR(MAX) = N'';\n")
        out.write(
            "SELECT @drop_fks += N'ALTER TABLE [' + OBJECT_SCHEMA_NAME(parent_object_id) + "
            "N'].[' + OBJECT_NAME(parent_object_id) + N'] DROP CONSTRAINT [' + name + N'];' + "
            "CHAR(13) + CHAR(10)\n"
            "FROM sys.foreign_keys;\n"
        )
        out.write("IF LEN(@drop_fks) > 0 EXEC sp_executesql @drop_fks;\n")
        out.write("GO\n\n")

        # 2. Drop existing tables
        out.write("-- 2. Drop existing tables\n")
        out.write("DECLARE @drop_tables NVARCHAR(MAX) = N'';\n")
        out.write(
            "SELECT @drop_tables += N'DROP TABLE [' + SCHEMA_NAME(schema_id) + "
            "N'].[' + name + N'];' + CHAR(13) + CHAR(10)\n"
            "FROM sys.tables;\n"
        )
        out.write("IF LEN(@drop_tables) > 0 EXEC sp_executesql @drop_tables;\n")
        out.write("GO\n\n")

        # 3. Create tables (with column definitions and primary keys)
        out.write("-- 3. Create tables\n")
        for table in sorted_tables:
            col_defs: list[str] = []
            for col in table.columns:
                type_str = col.type.compile(self.engine.dialect)
                nullable_str = "NULL" if col.nullable else "NOT NULL"
                col_defs.append(f"    [{col.name}] {type_str} {nullable_str}")
            pk_cols = [f"[{c.name}]" for c in table.primary_key.columns]
            if pk_cols:
                pk_name = table.primary_key.name or f"PK_{table.name}"
                col_defs.append(f"    CONSTRAINT [{pk_name}] PRIMARY KEY CLUSTERED ({', '.join(pk_cols)})")
            out.write(f"CREATE TABLE [dbo].[{table.name}] (\n" + ",\n".join(col_defs) + "\n);\nGO\n\n")

        # 4. Disable foreign key checks during insert
        out.write("-- 4. Disable foreign key constraints during bulk insert\n")
        out.write('EXEC sp_MSforeachtable "ALTER TABLE ? NOCHECK CONSTRAINT ALL";\n')
        out.write("GO\n\n")

        # 5. Insert data
        out.write("-- 5. Insert data\n")
        with self.engine.connect() as conn:
            for table in sorted_tables:
                rows = conn.execute(table.select()).fetchall()
                if not rows:
                    continue
                col_names = [f"[{col.name}]" for col in table.columns]
                cols_str = ", ".join(col_names)
                col_type_strs = [str(col.type) for col in table.columns]

                out.write(f"-- Data for [dbo].[{table.name}] ({len(rows)} rows)\n")
                batch_size = 100
                for i in range(0, len(rows), batch_size):
                    batch = rows[i : i + batch_size]
                    values_clauses = []
                    for row in batch:
                        row_vals = [
                            format_sql_literal(val, t_str)
                            for val, t_str in zip(row, col_type_strs)
                        ]
                        values_clauses.append(f"({', '.join(row_vals)})")
                    out.write(
                        f"INSERT INTO [dbo].[{table.name}] ({cols_str}) VALUES\n"
                        + ",\n".join(values_clauses)
                        + ";\n"
                    )
                out.write("GO\n\n")

        # 6. Unique Constraints and Indexes
        out.write("-- 6. Unique Constraints and Indexes\n")
        with self.engine.connect() as conn:
            indexes = conn.execute(text("""
                SELECT
                    t.name AS table_name,
                    i.name AS index_name,
                    i.is_unique,
                    i.is_unique_constraint,
                    STRING_AGG(QUOTENAME(c.name), ', ') WITHIN GROUP (ORDER BY ic.key_ordinal) AS columns
                FROM sys.indexes i
                JOIN sys.tables t ON i.object_id = t.object_id
                JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
                JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
                WHERE i.is_primary_key = 0 AND i.name IS NOT NULL
                GROUP BY t.name, i.name, i.is_unique, i.is_unique_constraint
                ORDER BY t.name, i.name;
            """)).fetchall()

            for row in indexes:
                table_name, index_name, is_unique, is_unique_constraint, columns = row
                if is_unique_constraint:
                    out.write(f"ALTER TABLE [dbo].[{table_name}] ADD CONSTRAINT [{index_name}] UNIQUE ({columns});\n")
                elif is_unique:
                    out.write(f"CREATE UNIQUE NONCLUSTERED INDEX [{index_name}] ON [dbo].[{table_name}] ({columns});\n")
                else:
                    out.write(f"CREATE NONCLUSTERED INDEX [{index_name}] ON [dbo].[{table_name}] ({columns});\n")
            out.write("GO\n\n")

        # 7. Foreign Key Constraints
        out.write("-- 7. Foreign Key Constraints\n")
        with self.engine.connect() as conn:
            fks = conn.execute(text("""
                SELECT
                    fk.name AS fk_name,
                    tp.name AS parent_table,
                    STRING_AGG(QUOTENAME(cp.name), ', ') WITHIN GROUP (ORDER BY fkc.constraint_column_id) AS parent_columns,
                    tr.name AS ref_table,
                    STRING_AGG(QUOTENAME(cr.name), ', ') WITHIN GROUP (ORDER BY fkc.constraint_column_id) AS ref_columns
                FROM sys.foreign_keys fk
                JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
                JOIN sys.tables tp ON fkc.parent_object_id = tp.object_id
                JOIN sys.columns cp ON fkc.parent_object_id = cp.object_id AND fkc.parent_column_id = cp.column_id
                JOIN sys.tables tr ON fkc.referenced_object_id = tr.object_id
                JOIN sys.columns cr ON fkc.referenced_object_id = cr.object_id AND fkc.referenced_column_id = cr.column_id
                GROUP BY fk.name, tp.name, tr.name
                ORDER BY tp.name, fk.name;
            """)).fetchall()

            for row in fks:
                fk_name, parent_table, parent_columns, ref_table, ref_columns = row
                out.write(
                    f"ALTER TABLE [dbo].[{parent_table}] ADD CONSTRAINT [{fk_name}] "
                    f"FOREIGN KEY ({parent_columns}) REFERENCES [dbo].[{ref_table}] ({ref_columns});\n"
                )
            out.write("GO\n\n")

        # 8. Check Constraints
        out.write("-- 8. Check Constraints\n")
        with self.engine.connect() as conn:
            cks = conn.execute(text("""
                SELECT
                    t.name AS table_name,
                    cc.name AS constraint_name,
                    cc.definition
                FROM sys.check_constraints cc
                JOIN sys.tables t ON cc.parent_object_id = t.object_id
                ORDER BY t.name, cc.name;
            """)).fetchall()

            for row in cks:
                table_name, constraint_name, definition = row
                out.write(f"ALTER TABLE [dbo].[{table_name}] ADD CONSTRAINT [{constraint_name}] CHECK {definition};\n")
            out.write("GO\n\n")

        # 9. Re-enable foreign key constraints with verification
        out.write("-- 9. Re-enable foreign key constraints with validation\n")
        out.write('EXEC sp_MSforeachtable "ALTER TABLE ? WITH CHECK CHECK CONSTRAINT ALL";\n')
        out.write("GO\n\n")
        out.write(f"PRINT 'Backup restore completed successfully for {self.database_name}.';\n")
        out.write("GO\n")
