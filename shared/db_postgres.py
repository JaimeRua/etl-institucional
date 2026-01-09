import os
import urllib.parse
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


def get_pg_engine() -> Engine:
    host = os.getenv("PG_HOST")
    port = os.getenv("PG_PORT", "5432")
    db = os.getenv("PG_DB")
    user = os.getenv("PG_USER")
    password = os.getenv("PG_PASSWORD")

    if not host or not db or not user or not password:
        raise RuntimeError(
            "Faltan variables PG_* (PG_HOST, PG_DB, PG_USER, PG_PASSWORD)."
        )

    password_enc = urllib.parse.quote_plus(password)  # password ya es str
    url = f"postgresql+psycopg://{user}:{password_enc}@{host}:{port}/{db}"
    return create_engine(url, pool_pre_ping=True)
