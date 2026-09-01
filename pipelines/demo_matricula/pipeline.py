from __future__ import annotations

import pandas as pd
from sqlalchemy import text

from shared.audit import RunContext
from shared.config import Settings
from shared.db_postgres import get_pg_engine


def extract_mock() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"anio": 2025, "carrera": "Ingeniería", "matriculados": 120},
            {"anio": 2025, "carrera": "Derecho ", "matriculados": 80},
        ]
    )


def transform(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["anio"] = out["anio"].astype(int)
    out["carrera"] = out["carrera"].astype(str).str.strip().str.upper()
    out["matriculados"] = out["matriculados"].astype(int)
    return out


def validate(df: pd.DataFrame) -> None:
    required = {"anio", "carrera", "matriculados"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Faltan columnas requeridas: {sorted(missing)}")

    if df["anio"].isna().any():
        raise ValueError("Hay valores nulos en anio")

    if (df["anio"] < 1900).any() or (df["anio"] > 2100).any():
        raise ValueError("anio fuera de rango razonable")

    if df["carrera"].isna().any() or (df["carrera"].astype(str).str.len() == 0).any():
        raise ValueError("carrera vacía o nula")

    if (df["matriculados"] < 0).any():
        raise ValueError("matriculados no puede ser negativo")

    # Clave natural: (anio, carrera) debe ser única
    if df.duplicated(subset=["anio", "carrera"]).any():
        dups = df[df.duplicated(subset=["anio", "carrera"], keep=False)]
        raise ValueError(f"Duplicados en clave (anio,carrera):\n{dups}")


def ensure_table(engine) -> None:
    with engine.begin() as cxn:
        cxn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS gold.gold_matricula (
                    anio INT NOT NULL,
                    carrera TEXT NOT NULL,
                    matriculados INT NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (anio, carrera)
                );
                """
            )
        )


def upsert(engine, df: pd.DataFrame) -> int:
    records = df.to_dict(orient="records")
    with engine.begin() as cxn:
        for row in records:
            cxn.execute(
                text(
                    """
                    INSERT INTO gold.gold_matricula (anio, carrera, matriculados)
                    VALUES (:anio, :carrera, :matriculados)
                    ON CONFLICT (anio, carrera)
                    DO UPDATE SET
                      matriculados = EXCLUDED.matriculados,
                      updated_at = NOW();
                    """
                ),
                row,
            )
    return len(records)


def run(ctx: RunContext, settings: Settings) -> tuple[int, int]:
    df_raw = extract_mock()
    rows_in = len(df_raw)

    df = transform(df_raw)
    validate(df)

    engine = get_pg_engine(settings.postgres)
    ensure_table(engine)
    rows_out = upsert(engine, df)

    print(f"[demo_matricula] run_id={ctx.run_id} env={ctx.env} rows_in={rows_in} rows_out={rows_out}")
    return rows_in, rows_out
