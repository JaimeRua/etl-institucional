from pathlib import Path

import pytest

from shared.clients.ucampus import UcampusClient
from shared.config import UcampusCfg, load_settings


def _write_config(root: Path) -> None:
    config = root / "config"
    config.mkdir()
    (config / "test.yml").write_text(
        """
app:
  env: test
  log_level: INFO
  log_format: json
postgres:
  host: yaml-postgres
  port: 5432
  db: yaml-db
  user: yaml-user
sqlserver:
  host: yaml-sqlserver
  port: 1433
  db: yaml-source
  user: yaml-reader
  driver: ODBC Driver 18 for SQL Server
ucampus:
  base_url: https://yaml.example/api/
  timeout_s: 30
""".strip(),
        encoding="utf-8",
    )


def test_environment_overrides_non_secret_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_config(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PG_PASSWORD", "pg-secret")
    monkeypatch.setenv("MSSQL_PASSWORD", "ms-secret")
    monkeypatch.setenv("PG_HOST", "env-postgres")
    monkeypatch.setenv("MSSQL_DB", "env-source")
    monkeypatch.setenv("APP_LOG_FORMAT", "text")

    settings = load_settings("test")

    assert settings.postgres.host == "env-postgres"
    assert settings.sqlserver.db == "env-source"
    assert settings.app.log_format == "text"
    assert settings.postgres.password == "pg-secret"


def test_ucampus_client_uses_the_typed_configuration() -> None:
    client = UcampusClient(
        UcampusCfg(
            base_url="https://ucampus.example/api/",
            token="secret",
            timeout_s=45,
        )
    )

    assert client.base_url == "https://ucampus.example/api/"
    assert client.token == "secret"
    assert client.timeout == 45


def test_ucampus_client_requires_a_token() -> None:
    with pytest.raises(RuntimeError, match="token"):
        UcampusClient(
            UcampusCfg(
                base_url="https://ucampus.example/api/",
                token="",
                timeout_s=30,
            )
        )
