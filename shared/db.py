"""Conector de compatibilidad para integraciones basadas en ``DB_URL``.

Los pipelines institucionales nuevos deben usar ``shared.db_postgres`` o
``shared.db_sqlserver`` con la configuración tipada de ``shared.config``.
"""

import os
import warnings

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


def get_engine() -> Engine:
    warnings.warn(
        "shared.db.get_engine está deprecado; use shared.db_postgres",
        DeprecationWarning,
        stacklevel=2,
    )
    db_url = os.getenv("DB_URL")
    if not db_url:
        raise RuntimeError("DB_URL no está configurada (revisa .env).")
    return create_engine(db_url, pool_pre_ping=True)
