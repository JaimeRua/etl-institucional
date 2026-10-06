from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shared.audit import RunContext, finish_table_run, start_table_run
from shared.config import Settings
from shared.db_postgres import get_pg_connection, get_pg_engine

logger = logging.getLogger(__name__)


PIPELINE_DIR = Path(__file__).resolve().parent
MATRIX_PATH = PIPELINE_DIR / "transformation_matrix.json"
DDL_PATH = PIPELINE_DIR / "sql" / "001_create_stg_matricula_sies.sql"
IDENTIFIER_RE = re.compile(r"^[a-z_][a-z0-9_]*$")
PG_TYPE_RE = re.compile(r"^(?:text|smallint|integer|numeric\([1-9][0-9]*,[0-9]+\))$")
SUPPORTED_RULES = {
    "R00_TIPO_FISICO",
    "R04_ANIO",
    "R08_PORCENTAJE",
    "R10_PROMEDIO_EDAD",
    "R12_DURACION",
    "R14_CONTEO",
    "R16_CODIGO",
    "R18_TEXTO",
    "R19_DOCUMENTO",
}


@dataclass(frozen=True)
class ColumnRule:
    sqlserver: str
    source: str
    target: str
    pg_type: str
    rule: str
    action: str


@dataclass(frozen=True)
class TransformationMatrix:
    version: int
    source_schema: str
    source_table: str
    target_schema: str
    target_table: str
    reject_schema: str
    reject_table: str
    columns: tuple[ColumnRule, ...]


@dataclass(frozen=True)
class StageLoadResult:
    rows_in: int
    rows_out: int
    rows_rejected: int


class StageLoadError(RuntimeError):
    pass


def _qualified_name(value: object, field: str) -> tuple[str, str]:
    parts = str(value).split(".")
    if len(parts) != 2 or not all(IDENTIFIER_RE.fullmatch(part) for part in parts):
        raise ValueError(f"{field} debe tener formato esquema.tabla: {value}")
    return parts[0], parts[1]


def load_matrix(path: Path = MATRIX_PATH) -> TransformationMatrix:
    data = json.loads(path.read_text(encoding="utf-8"))
    source_schema, source_table = _qualified_name(data.get("source"), "source")
    target_schema, target_table = _qualified_name(data.get("target"), "target")
    reject_schema, reject_table = _qualified_name(
        data.get("reject_target"), "reject_target"
    )

    columns: list[ColumnRule] = []
    for item in data.get("columns", []):
        column = ColumnRule(
            sqlserver=str(item["sqlserver"]),
            source=str(item["source"]),
            target=str(item["target"]),
            pg_type=str(item["type"]),
            rule=str(item["rule"]),
            action=str(item["action"]),
        )
        if not IDENTIFIER_RE.fullmatch(column.source):
            raise ValueError(f"Columna raw inválida: {column.source}")
        if not IDENTIFIER_RE.fullmatch(column.target):
            raise ValueError(f"Columna stg inválida: {column.target}")
        if not PG_TYPE_RE.fullmatch(column.pg_type):
            raise ValueError(f"Tipo PostgreSQL no permitido: {column.pg_type}")
        if column.rule not in SUPPORTED_RULES:
            raise ValueError(f"Regla no soportada: {column.rule}")
        if column.action not in {"DIRECTA", "VALIDAR"}:
            raise ValueError(f"Acción no soportada: {column.action}")
        columns.append(column)

    if int(data.get("version", 0)) != 1:
        raise ValueError("Versión de matriz no soportada")
    if len(columns) != 60:
        raise ValueError(
            f"La matriz debe contener 60 columnas; contiene {len(columns)}"
        )
    if len({column.source for column in columns}) != len(columns):
        raise ValueError("La matriz contiene columnas raw duplicadas")
    if len({column.target for column in columns}) != len(columns):
        raise ValueError("La matriz contiene columnas stg duplicadas")

    return TransformationMatrix(
        version=1,
        source_schema=source_schema,
        source_table=source_table,
        target_schema=target_schema,
        target_table=target_table,
        reject_schema=reject_schema,
        reject_table=reject_table,
        columns=tuple(columns),
    )


def quote_identifier(value: str) -> str:
    if not IDENTIFIER_RE.fullmatch(value):
        raise ValueError(f"Identificador PostgreSQL inválido: {value}")
    return f'"{value}"'


def qualified(schema: str, table: str) -> str:
    return f"{quote_identifier(schema)}.{quote_identifier(table)}"


def _raw_alias(column: ColumnRule) -> str:
    return f"_raw_{column.target}"


def _normalized_expression(column: ColumnRule) -> str:
    source = f"r.{quote_identifier(column.source)}::text"
    if column.rule in {"R08_PORCENTAJE", "R10_PROMEDIO_EDAD"}:
        source = f"replace({source}, '%', '')"
    return f"NULLIF(BTRIM({source}), '')"


def _decimal_expression(raw: str) -> str:
    return f"replace({quote_identifier(raw)}, ',', '.')"


def _parsed_expression(column: ColumnRule) -> str:
    raw = _raw_alias(column)
    raw_id = quote_identifier(raw)
    if column.pg_type == "text":
        return raw_id
    if column.rule == "R04_ANIO":
        return (
            f"CASE WHEN {raw_id} ~ '^[0-9]+$' THEN "
            f"CASE WHEN {raw_id}::numeric BETWEEN 1900 AND 2100 "
            f"THEN {raw_id}::smallint END END"
        )
    if column.rule == "R12_DURACION":
        return (
            f"CASE WHEN {raw_id} ~ '^[0-9]+$' THEN "
            f"CASE WHEN {raw_id}::numeric BETWEEN 0 AND 32767 "
            f"THEN {raw_id}::smallint END END"
        )
    if column.rule == "R14_CONTEO":
        return (
            f"CASE WHEN {raw_id} ~ '^[0-9]+$' THEN "
            f"CASE WHEN {raw_id}::numeric BETWEEN 0 AND 2147483647 "
            f"THEN {raw_id}::integer END END"
        )
    decimal = _decimal_expression(raw)
    if column.rule == "R10_PROMEDIO_EDAD":
        return (
            f"CASE WHEN {raw_id} ~ '^[0-9]+([.,][0-9]+)?$' THEN "
            f"CASE WHEN {decimal}::numeric BETWEEN 0 AND 150 "
            f"THEN {decimal}::numeric(6,2) END END"
        )
    if column.rule == "R08_PORCENTAJE":
        return (
            f"CASE WHEN {raw_id} ~ '^[0-9]+([.,][0-9]+)?$' THEN "
            f"CASE WHEN {decimal}::numeric BETWEEN 0 AND 100 "
            f"THEN {decimal}::numeric(9,4) END END"
        )
    raise ValueError(
        f"No hay conversión definida para {column.target}: "
        f"{column.rule}/{column.pg_type}"
    )


def _error_expression(column: ColumnRule) -> str | None:
    if column.action != "VALIDAR":
        return None
    raw = quote_identifier(_raw_alias(column))
    parsed = quote_identifier(column.target)
    descriptions = {
        "R04_ANIO": "año entero entre 1900 y 2100",
        "R08_PORCENTAJE": "porcentaje numérico entre 0 y 100",
        "R10_PROMEDIO_EDAD": "edad numérica entre 0 y 150",
        "R12_DURACION": "duración entera no negativa",
        "R14_CONTEO": "conteo entero no negativo",
    }
    description = descriptions[column.rule]
    message = f"{column.rule}: {column.target} debe ser {description}"
    return f"CASE WHEN {raw} IS NOT NULL AND {parsed} IS NULL THEN '{message}' END"


def build_transform_sql(matrix: TransformationMatrix) -> str:
    source = qualified(matrix.source_schema, matrix.source_table)
    normalized = [
        f"{_normalized_expression(column)} AS {quote_identifier(_raw_alias(column))}"
        for column in matrix.columns
    ]
    parsed = [
        f"{_parsed_expression(column)} AS {quote_identifier(column.target)}"
        for column in matrix.columns
    ]
    errors = [
        expression
        for column in matrix.columns
        if (expression := _error_expression(column)) is not None
    ]
    normalized_sql = ",\n            ".join(normalized)
    parsed_sql = ",\n            ".join(parsed)
    errors_sql = ",\n                ".join(errors)

    return f"""
        CREATE TEMP TABLE _matricula_sies_transform ON COMMIT DROP AS
        WITH normalized AS (
          SELECT
            r._etl_ingestion_id AS _raw_ingestion_id,
            r._etl_batch_id AS _raw_batch_id,
            r._etl_loaded_at AS _raw_loaded_at,
            r._etl_row_hash AS _raw_row_hash,
            to_jsonb(r) AS registro_raw,
            {normalized_sql}
          FROM {source} AS r
        ), parsed AS (
          SELECT
            n.*,
            {parsed_sql}
          FROM normalized AS n
        )
        SELECT
          p.*,
          array_remove(ARRAY[
                {errors_sql}
          ], NULL)::text[] AS errores
        FROM parsed AS p
    """


def _fetch_count(cursor: Any, statement: str, params: tuple[object, ...] = ()) -> int:
    cursor.execute(statement, params)
    row = cursor.fetchone()
    if row is None:
        raise StageLoadError("La consulta de conteo no devolvió resultado")
    return int(row[0])


def _validate_columns(cursor: Any, schema: str, table: str, required: set[str]) -> None:
    cursor.execute(
        """
        SELECT column_name
          FROM information_schema.columns
         WHERE table_schema = %s AND table_name = %s
        """,
        (schema, table),
    )
    actual = {str(row[0]) for row in cursor.fetchall()}
    missing = sorted(required - actual)
    if missing:
        raise StageLoadError(
            f"{schema}.{table} inexistente o incompleta; "
            f"faltan columnas: {', '.join(missing)}"
        )


def ensure_ddl(connection: Any) -> None:
    with connection.cursor() as cursor:
        cursor.execute(DDL_PATH.read_text(encoding="utf-8"))
    connection.commit()


def load_stage(
    connection: Any,
    *,
    matrix: TransformationMatrix,
    run_id: str,
    dry_run: bool,
) -> StageLoadResult:
    source_required = {column.source for column in matrix.columns} | {
        "_etl_ingestion_id",
        "_etl_batch_id",
        "_etl_loaded_at",
        "_etl_row_hash",
    }
    target_required = {column.target for column in matrix.columns} | {
        "_raw_ingestion_id",
        "_raw_batch_id",
        "_raw_loaded_at",
        "_raw_row_hash",
        "_stg_run_id",
        "_stg_loaded_at",
    }
    target = qualified(matrix.target_schema, matrix.target_table)
    reject_target = qualified(matrix.reject_schema, matrix.reject_table)
    target_columns = [quote_identifier(column.target) for column in matrix.columns]
    metadata_columns = [
        "_raw_ingestion_id",
        "_raw_batch_id",
        "_raw_loaded_at",
        "_raw_row_hash",
        "_stg_run_id",
    ]

    with connection.cursor() as cursor:
        _validate_columns(
            cursor, matrix.source_schema, matrix.source_table, source_required
        )
        _validate_columns(
            cursor, matrix.target_schema, matrix.target_table, target_required
        )
        cursor.execute(build_transform_sql(matrix))
        rows_in = _fetch_count(cursor, "SELECT count(*) FROM _matricula_sies_transform")
        rows_rejected = _fetch_count(
            cursor,
            "SELECT count(*) FROM _matricula_sies_transform "
            "WHERE cardinality(errores) > 0",
        )
        rows_out = rows_in - rows_rejected

        if dry_run:
            connection.rollback()
            return StageLoadResult(rows_in, rows_out, rows_rejected)

        cursor.execute(f"TRUNCATE TABLE {target}")
        insert_columns = target_columns + [
            quote_identifier(column) for column in metadata_columns
        ]
        select_columns = target_columns + [
            quote_identifier(column) for column in metadata_columns[:-1]
        ]
        cursor.execute(
            f"""
            INSERT INTO {target} ({", ".join(insert_columns)})
            SELECT {", ".join(select_columns)}, %s
              FROM _matricula_sies_transform
             WHERE cardinality(errores) = 0
            """,
            (run_id,),
        )
        inserted = int(cursor.rowcount)
        cursor.execute(
            f"""
            INSERT INTO {reject_target} (
                _stg_run_id, _raw_ingestion_id, _raw_batch_id,
                _raw_loaded_at, errores, registro_raw
            )
            SELECT %s, _raw_ingestion_id, _raw_batch_id,
                   _raw_loaded_at, errores, registro_raw
              FROM _matricula_sies_transform
             WHERE cardinality(errores) > 0
            """,
            (run_id,),
        )
        rejected = int(cursor.rowcount)
        if inserted != rows_out or rejected != rows_rejected:
            raise StageLoadError(
                "Conteo inconsistente: "
                f"raw={rows_in}, stg={inserted}, rechazos={rejected}"
            )

    connection.commit()
    return StageLoadResult(rows_in, rows_out, rows_rejected)


def _validate_requested_table(ctx: RunContext, matrix: TransformationMatrix) -> None:
    requested = [str(value).lower() for value in ctx.options.get("tables", [])]
    accepted = {
        matrix.source_table,
        f"{matrix.source_schema}.{matrix.source_table}",
        matrix.target_table,
        f"{matrix.target_schema}.{matrix.target_table}",
    }
    invalid = sorted(set(requested) - accepted)
    if invalid:
        raise ValueError(
            "raw_to_stg_matricula solo procesa raw.bi_mat_sies_reporte; "
            f"no reconoce: {', '.join(invalid)}"
        )


def run(ctx: RunContext, settings: Settings) -> tuple[int, int]:
    matrix = load_matrix()
    _validate_requested_table(ctx, matrix)
    dry_run = bool(ctx.options.get("dry_run", False))
    audit_engine = get_pg_engine(settings.postgres)
    connection = get_pg_connection(settings.postgres)
    batch_id = f"{ctx.run_id}:{matrix.target_table}"

    start_table_run(
        audit_engine,
        ctx,
        source_schema=matrix.source_schema,
        source_table=matrix.source_table,
        target_schema=matrix.target_schema,
        target_table=matrix.target_table,
        batch_id=batch_id,
    )
    logger.info(
        "stg_table_load_started",
        extra={
            "event": "stg_table_load_started",
            "run_id": ctx.run_id,
            "pipeline": ctx.pipeline,
            "source_table": f"{matrix.source_schema}.{matrix.source_table}",
            "target_table": f"{matrix.target_schema}.{matrix.target_table}",
            "dry_run": dry_run,
        },
    )
    try:
        ensure_ddl(connection)
        result = load_stage(
            connection, matrix=matrix, run_id=ctx.run_id, dry_run=dry_run
        )
    except Exception as exc:
        connection.rollback()
        finish_table_run(
            audit_engine,
            ctx,
            source_schema=matrix.source_schema,
            source_table=matrix.source_table,
            status="FAILED",
            error=str(exc),
        )
        raise
    finally:
        connection.close()

    if dry_run:
        status = "VALIDATED"
    elif result.rows_rejected:
        status = "SUCCESS_WITH_WARNINGS"
    else:
        status = "SUCCESS"
    finish_table_run(
        audit_engine,
        ctx,
        source_schema=matrix.source_schema,
        source_table=matrix.source_table,
        status=status,
        rows_in=result.rows_in,
        rows_out=result.rows_out,
        error=(
            f"{result.rows_rejected} registro(s) en "
            f"{matrix.reject_schema}.{matrix.reject_table}"
            if result.rows_rejected
            else None
        ),
    )
    logger.info(
        "stg_pipeline_completed",
        extra={
            "event": "stg_pipeline_completed",
            "run_id": ctx.run_id,
            "pipeline": ctx.pipeline,
            "rows_in": result.rows_in,
            "rows_out": result.rows_out,
            "rows_rejected": result.rows_rejected,
            "dry_run": dry_run,
        },
    )
    return result.rows_in, result.rows_out
