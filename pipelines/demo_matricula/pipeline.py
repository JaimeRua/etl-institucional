from __future__ import annotations

import pandas as pd


def run(env: str) -> None:
    df = pd.DataFrame(
        [
            {"anio": 2025, "carrera": "INGENIERIA", "matriculados": 120},
            {"anio": 2025, "carrera": "DERECHO", "matriculados": 80},
        ]
    )
    print(f"[demo_matricula] ENV={env} filas={len(df)}")
    print(df)
