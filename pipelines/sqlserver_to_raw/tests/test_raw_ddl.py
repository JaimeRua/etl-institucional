import re
from pathlib import Path

from pipelines.sqlserver_to_raw.manifest import load_manifest

DDL_PATH = Path(__file__).resolve().parents[1] / "sql" / "001_create_raw_tables.sql"
TABLE_RE = re.compile(
    r'CREATE TABLE IF NOT EXISTS raw\."([^"]+)" \(\n(.*?)\n\);', re.DOTALL
)
COLUMN_RE = re.compile(r'^    "([^"]+)" ', re.MULTILINE)
METADATA_COLUMNS = [
    "_etl_ingestion_id",
    "_etl_batch_id",
    "_etl_loaded_at",
    "_etl_source_database",
    "_etl_source_schema",
    "_etl_source_table",
    "_etl_row_hash",
]


def test_raw_ddl_covers_the_complete_manifest() -> None:
    manifest = load_manifest()
    ddl = DDL_PATH.read_text(encoding="utf-8")
    blocks = {name: body for name, body in TABLE_RE.findall(ddl)}

    assert len(blocks) == 138
    assert set(blocks) == {table.target_table for table in manifest.tables}

    for table in manifest.tables:
        actual_columns = COLUMN_RE.findall(blocks[table.target_table])
        expected_columns = [column.target for column in table.columns]
        assert actual_columns == expected_columns + METADATA_COLUMNS


def test_raw_ddl_contains_approved_type_mappings_and_lineage() -> None:
    ddl = DDL_PATH.read_text(encoding="utf-8")

    assert '"codigo_asignatura" character varying(255)' in ddl
    assert '"ptje_ponderado" numeric(10,2)' in ddl
    assert '"latitud" double precision' in ddl
    assert '"definition" bytea' in ddl
    assert '"_etl_ingestion_id" bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY' in ddl
    assert '"_etl_loaded_at" timestamp with time zone' in ddl
