import urllib.parse
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from shared.config import PostgresCfg

def get_pg_engine(cfg: PostgresCfg) -> Engine:
    password_enc = urllib.parse.quote_plus(cfg.password)
    url = f"postgresql+psycopg://{cfg.user}:{password_enc}@{cfg.host}:{cfg.port}/{cfg.db}"
    return create_engine(url, pool_pre_ping=True)
