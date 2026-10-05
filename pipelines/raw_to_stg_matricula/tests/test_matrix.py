import json
from pathlib import Path

import pytest

from pipelines.raw_to_stg_matricula.pipeline import DDL_PATH, load_matrix


def test_matricula_matrix_is_complete() -> None:
    matrix = load_matrix()

    assert matrix.version == 1
    assert (matrix.source_schema, matrix.source_table) == (
        "raw",
        "bi_mat_sies_reporte",
    )
    assert (matrix.target_schema, matrix.target_table) == ("stg", "matricula_sies")
    assert len(matrix.columns) == 60
    assert len({column.source for column in matrix.columns}) == 60
    assert len({column.target for column in matrix.columns}) == 60


def test_sensitive_types_follow_the_approved_matrix() -> None:
    columns = {column.target: column for column in load_matrix().columns}

    assert columns["ano"].pg_type == "smallint"
    assert columns["ano"].rule == "R04_ANIO"
    assert columns["codigo_carrera"].pg_type == "text"
    assert columns["total_matricula"].pg_type == "integer"
    assert columns["promedio_edad_carrera"].pg_type == "numeric(6,2)"
    assert columns["cobertura_tes"].pg_type == "numeric(9,4)"


def test_ddl_contains_every_matrix_column_with_its_type() -> None:
    ddl = DDL_PATH.read_text(encoding="utf-8")

    for column in load_matrix().columns:
        assert f"    {column.target} {column.pg_type}," in ddl
    assert "_raw_ingestion_id bigint NOT NULL" in ddl
    assert "_stg_run_id text NOT NULL" in ddl
    assert "CREATE TABLE IF NOT EXISTS stg.matricula_sies_rechazos" in ddl


def test_invalid_matrix_version_is_rejected(tmp_path: Path) -> None:
    source = json.loads(
        (Path(__file__).resolve().parents[1] / "transformation_matrix.json").read_text(
            encoding="utf-8"
        )
    )
    source["version"] = 2
    path = tmp_path / "matrix.json"
    path.write_text(json.dumps(source), encoding="utf-8")

    with pytest.raises(ValueError, match="Versión"):
        load_matrix(path)
