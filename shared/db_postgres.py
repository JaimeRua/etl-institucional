import os
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

def get_pg_engine() -> Engine:
    host = os.getenv("PG_HOST")
    port = os.getenv("PG_PORT", "5432")
    db = os.getenv("PG_DB")
    user = os.getenv("PG_USER")
    pwd = os.getenv("PG_PASSWORD")

    if not all([host, db, user, pwd]):
        raise RuntimeError("Faltan variables PG_* en .env")

    url = f"postgresql+psycopg://{user}:{pwd}@{host}:{port}/{db}"
    return create_engine(url, pool_pre_ping=True)
