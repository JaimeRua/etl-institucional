from pipelines.raw_to_stg_matricula.pipeline import (
    _parsed_expression,
    build_transform_sql,
    load_matrix,
)


def test_transform_sql_is_set_based_and_keeps_lineage() -> None:
    sql = build_transform_sql(load_matrix())

    assert "CREATE TEMP TABLE _matricula_sies_transform" in sql
    assert 'FROM "raw"."bi_mat_sies_reporte" AS r' in sql
    assert "to_jsonb(r) AS registro_raw" in sql
    assert "array_remove(ARRAY[" in sql
    assert "R14_CONTEO: total_matricula" in sql
    assert "R08_PORCENTAJE: cobertura_tes" in sql


def test_numeric_parsers_are_guarded_before_casting() -> None:
    columns = {column.target: column for column in load_matrix().columns}

    count_sql = _parsed_expression(columns["total_matricula"])
    year_sql = _parsed_expression(columns["ano"])
    coverage_sql = _parsed_expression(columns["cobertura_tes"])

    assert "~ '^[0-9]+$'" in count_sql
    assert "BETWEEN 0 AND 2147483647" in count_sql
    assert "BETWEEN 1900 AND 2100" in year_sql
    assert "replace(\"_raw_cobertura_tes\", ',', '.')" in coverage_sql
    assert "BETWEEN 0 AND 100" in coverage_sql
