from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import os
import yaml
from dotenv import load_dotenv


@dataclass(frozen=True)
class PostgresCfg:
    host: str
    port: int
    db: str
    user: str
    password: str  # viene desde .env


@dataclass(frozen=True)
class SqlServerCfg:
    host: str
    port: int
    db: str
    user: str
    password: str  # viene desde .env
    driver: str


@dataclass(frozen=True)
class UcampusCfg:
    base_url: str
    token: str  # viene desde .env
    timeout_s: int


@dataclass(frozen=True)
class AppCfg:
    env: str
    log_level: str


@dataclass(frozen=True)
class Settings:
    app: AppCfg
    postgres: PostgresCfg
    sqlserver: SqlServerCfg
    ucampus: UcampusCfg


def _read_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"No existe archivo de config: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Config YAML inválida: {path}")
    return data


def load_settings(env: str) -> Settings:
    # Carga secretos desde .env (si existe)
    load_dotenv()

    cfg = _read_yaml(Path("config") / f"{env}.yml")

    app = cfg["app"]
    pg = cfg["postgres"]
    ms = cfg["sqlserver"]
    uc = cfg["ucampus"]

    # Secretos desde env
    pg_password = os.getenv("PG_PASSWORD")
    ms_password = os.getenv("MSSQL_PASSWORD")
    uc_token = os.getenv("UCAMPUS_TOKEN")

    if not pg_password:
        raise RuntimeError("Falta PG_PASSWORD en .env")
    if not ms_password:
        raise RuntimeError("Falta MSSQL_PASSWORD en .env")
    if not uc_token:
        raise RuntimeError("Falta UCAMPUS_TOKEN en .env")

    return Settings(
        app=AppCfg(env=str(app["env"]), log_level=str(app["log_level"])),
        postgres=PostgresCfg(
            host=str(pg["host"]),
            port=int(pg["port"]),
            db=str(pg["db"]),
            user=str(pg["user"]),
            password=pg_password,
        ),
        sqlserver=SqlServerCfg(
            host=str(ms["host"]),
            port=int(ms["port"]),
            db=str(ms["db"]),
            user=str(ms["user"]),
            password=ms_password,
            driver=str(ms["driver"]),
        ),
        ucampus=UcampusCfg(
            base_url=str(uc["base_url"]),
            token=uc_token,
            timeout_s=int(uc["timeout_s"]),
        ),
    )
