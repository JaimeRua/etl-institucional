import os
import urllib.parse
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from shared.config import SqlServerCfg


def _odbc_connection_string(cfg: SqlServerCfg) -> str:
    def value(raw: str) -> str:
        return "{" + raw.replace("}", "}}") + "}"

    return (
        f"DRIVER={value(cfg.driver)};"
        f"SERVER={cfg.host},{cfg.port};"
        f"DATABASE={value(cfg.db)};"
        f"UID={value(cfg.user)};PWD={value(cfg.password)};"
        "Encrypt=yes;TrustServerCertificate=yes;"
    )


def get_mssql_connection(cfg: SqlServerCfg) -> Any:
    """Abre una conexión DB-API para extracciones por streaming."""
    import pyodbc

    return pyodbc.connect(_odbc_connection_string(cfg), autocommit=True)


def get_mssql_engine(cfg: SqlServerCfg | None = None) -> Engine:
    if cfg is not None:
        params = urllib.parse.quote_plus(_odbc_connection_string(cfg))
        return create_engine(
            f"mssql+pyodbc:///?odbc_connect={params}", pool_pre_ping=True
        )

    host = os.getenv("MSSQL_HOST")
    port = os.getenv("MSSQL_PORT", "1433")
    db = os.getenv("MSSQL_DB")
    user = os.getenv("MSSQL_USER")
    pwd = os.getenv("MSSQL_PASSWORD")
    driver = os.getenv("MSSQL_DRIVER", "ODBC Driver 18 for SQL Server")

    if not all([host, db, user, pwd]):
        raise RuntimeError("Faltan variables MSSQL_* en .env")

    odbc_str = (
        f"DRIVER={{{driver}}};"
        f"SERVER={host},{port};"
        f"DATABASE={db};"
        f"UID={user};PWD={pwd};"
        f"Encrypt=yes;TrustServerCertificate=yes;"
    )
    params = urllib.parse.quote_plus(odbc_str)
    url = f"mssql+pyodbc:///?odbc_connect={params}"
    return create_engine(url, pool_pre_ping=True)
