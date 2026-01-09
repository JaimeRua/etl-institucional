import os
import urllib.parse
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


def get_mssql_engine() -> Engine:
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
