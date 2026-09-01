import psycopg
from sqlalchemy import URL, create_engine
from sqlalchemy.engine import Engine

from shared.config import PostgresCfg


def get_pg_connection(cfg: PostgresCfg) -> psycopg.Connection:
    """Abre una conexión psycopg nativa, requerida por COPY FROM STDIN."""
    return psycopg.connect(
        host=cfg.host,
        port=cfg.port,
        dbname=cfg.db,
        user=cfg.user,
        password=cfg.password,
    )


def get_pg_engine(cfg: PostgresCfg) -> Engine:
    url = URL.create(
        "postgresql+psycopg",
        username=cfg.user,
        password=cfg.password,
        host=cfg.host,
        port=cfg.port,
        database=cfg.db,
    )
    return create_engine(url, pool_pre_ping=True)
