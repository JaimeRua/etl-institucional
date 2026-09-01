from pipelines.sqlserver_to_raw.manifest import ColumnMapping, TableMapping
from pipelines.sqlserver_to_raw.pipeline import build_source_select, quote_mssql


def test_mssql_identifier_escaping() -> None:
    assert quote_mssql("columna]rara") == "[columna]]rara]"


def test_source_select_preserves_original_names() -> None:
    table = TableMapping(
        source_schema="dbo",
        source_table="MATRÍCULA 2025",
        target_table="matricula_2025",
        enabled=True,
        columns=(
            ColumnMapping(source="AÑO", target="ano"),
            ColumnMapping(source="CÓDIGO CARRERA", target="codigo_carrera"),
        ),
    )

    assert build_source_select(table) == (
        "SELECT [AÑO], [CÓDIGO CARRERA] FROM [dbo].[MATRÍCULA 2025]"
    )
    assert build_source_select(table, empty=True).startswith("SELECT TOP (0) ")
