from pathlib import Path

import pytest

from pipelines.sqlserver_to_raw.manifest import load_manifest, select_tables


def test_inventory_manifest_is_complete() -> None:
    manifest = load_manifest()

    assert manifest.version == 1
    assert manifest.source_database == "analisis_pro"
    assert manifest.target_schema == "raw"
    assert len(manifest.tables) == 138
    assert sum(len(table.columns) for table in manifest.tables) == 6_289
    assert len(select_tables(manifest, [])) == 137


def test_sysdiagrams_is_present_but_disabled() -> None:
    manifest = load_manifest()
    sysdiagrams = next(
        table for table in manifest.tables if table.source_table == "sysdiagrams"
    )

    assert sysdiagrams.enabled is False
    with pytest.raises(ValueError, match="deshabilitadas"):
        select_tables(manifest, ["sysdiagrams"])


def test_table_can_be_selected_by_any_supported_name() -> None:
    manifest = load_manifest()
    expected = next(
        table
        for table in manifest.tables
        if table.source_table == "ACAD_CURSO_PREGRADO"
    )

    for requested in (
        "dbo.ACAD_CURSO_PREGRADO",
        "ACAD_CURSO_PREGRADO",
        "acad_curso_pregrado",
    ):
        assert select_tables(manifest, [requested]) == (expected,)


def test_invalid_manifest_version_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "tables.json"
    path.write_text(
        '{"version": 2, "source_database": "db", "target_schema": "raw", "tables": []}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Versión"):
        load_manifest(path)
