from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ColumnMapping:
    source: str
    target: str


@dataclass(frozen=True)
class TableMapping:
    source_schema: str
    source_table: str
    target_table: str
    enabled: bool
    columns: tuple[ColumnMapping, ...]

    @property
    def source_key(self) -> str:
        return f"{self.source_schema}.{self.source_table}"


@dataclass(frozen=True)
class RawManifest:
    version: int
    source_database: str
    target_schema: str
    tables: tuple[TableMapping, ...]


DEFAULT_MANIFEST = Path(__file__).with_name("tables.json")


def load_manifest(path: Path = DEFAULT_MANIFEST) -> RawManifest:
    payload = json.loads(path.read_text(encoding="utf-8"))
    tables = tuple(
        TableMapping(
            source_schema=str(item["source_schema"]),
            source_table=str(item["source_table"]),
            target_table=str(item["target_table"]),
            enabled=bool(item.get("enabled", True)),
            columns=tuple(
                ColumnMapping(source=str(col["source"]), target=str(col["target"]))
                for col in item["columns"]
            ),
        )
        for item in payload["tables"]
    )
    manifest = RawManifest(
        version=int(payload["version"]),
        source_database=str(payload["source_database"]),
        target_schema=str(payload["target_schema"]),
        tables=tables,
    )
    _validate_manifest(manifest)
    return manifest


def select_tables(
    manifest: RawManifest, requested: list[str]
) -> tuple[TableMapping, ...]:
    enabled = tuple(table for table in manifest.tables if table.enabled)
    if not requested:
        return enabled

    selected: list[TableMapping] = []
    unknown: list[str] = []
    for value in requested:
        key = value.casefold()
        matches = [
            table
            for table in enabled
            if key
            in {
                table.source_key.casefold(),
                table.source_table.casefold(),
                table.target_table.casefold(),
            }
        ]
        if not matches:
            unknown.append(value)
            continue
        for match in matches:
            if match not in selected:
                selected.append(match)
    if unknown:
        raise ValueError(
            f"Tablas no encontradas o deshabilitadas: {', '.join(unknown)}"
        )
    return tuple(selected)


def _validate_manifest(manifest: RawManifest) -> None:
    if manifest.version != 1:
        raise ValueError(f"Versión de manifiesto no soportada: {manifest.version}")
    source_keys = [table.source_key.casefold() for table in manifest.tables]
    target_keys = [table.target_table.casefold() for table in manifest.tables]
    if len(source_keys) != len(set(source_keys)):
        raise ValueError("El manifiesto contiene tablas de origen duplicadas")
    if len(target_keys) != len(set(target_keys)):
        raise ValueError("El manifiesto contiene tablas raw duplicadas")
    for table in manifest.tables:
        if not table.columns:
            raise ValueError(f"La tabla {table.source_key} no tiene columnas")
        targets = [column.target.casefold() for column in table.columns]
        if len(targets) != len(set(targets)):
            raise ValueError(
                f"La tabla {table.source_key} tiene columnas destino duplicadas"
            )
