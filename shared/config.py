from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
    log_format: str


@dataclass(frozen=True)
class Settings:
    app: AppCfg
    postgres: PostgresCfg
    sqlserver: SqlServerCfg
    ucampus: UcampusCfg


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"No existe archivo de config: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Config YAML inválida: {path}")
    return data


def _value(
    section: dict[str, Any],
    key: str,
    env_name: str,
    *,
    required: bool = True,
    default: str | int | None = None,
) -> str:
    raw = os.getenv(env_name)
    if raw is None:
        raw = section.get(key, default)
    if raw is None or str(raw).strip() == "":
        if required:
            raise RuntimeError(
                f"Falta {env_name} o config.{key} para el ambiente seleccionado"
            )
        return ""
    return str(raw)


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
    log_format = _value(app, "log_format", "APP_LOG_FORMAT", default="json").lower()
    if log_format not in {"json", "text"}:
        raise RuntimeError("APP_LOG_FORMAT debe ser json o text")

    return Settings(
        app=AppCfg(
            env=_value(app, "env", "APP_ENV"),
            log_level=_value(app, "log_level", "APP_LOG_LEVEL", default="INFO"),
            log_format=log_format,
        ),
        postgres=PostgresCfg(
            host=_value(pg, "host", "PG_HOST"),
            port=int(_value(pg, "port", "PG_PORT", default=5432)),
            db=_value(pg, "db", "PG_DB"),
            user=_value(pg, "user", "PG_USER"),
            password=pg_password,
        ),
        sqlserver=SqlServerCfg(
            host=_value(ms, "host", "MSSQL_HOST"),
            port=int(_value(ms, "port", "MSSQL_PORT", default=1433)),
            db=_value(ms, "db", "MSSQL_DB"),
            user=_value(ms, "user", "MSSQL_USER"),
            password=ms_password,
            driver=_value(
                ms,
                "driver",
                "MSSQL_DRIVER",
                default="ODBC Driver 18 for SQL Server",
            ),
        ),
        ucampus=UcampusCfg(
            base_url=_value(uc, "base_url", "UCAMPUS_BASE_URL"),
            token=uc_token or "",
            timeout_s=int(_value(uc, "timeout_s", "UCAMPUS_TIMEOUT_S", default=30)),
        ),
    )
