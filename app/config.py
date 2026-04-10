"""Configuracao central da aplicacao."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field, computed_field


load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseModel):
    """Configuracoes carregadas do ambiente."""

    app_name: str = Field(default=os.getenv("APP_NAME", "ta6000-monitor"))
    environment: str = Field(default=os.getenv("ENVIRONMENT", "local"))
    log_level: str = Field(default=os.getenv("LOG_LEVEL", "INFO").upper())
    data_source_mode: str = Field(default=os.getenv("DATA_SOURCE_MODE", "auto").lower())

    sql_server: str = Field(default=os.getenv("SQL_SERVER", "srv01win185"))
    sql_port: int = Field(default=int(os.getenv("SQL_PORT", "1433")))
    sql_database: str = Field(default=os.getenv("SQL_DATABASE", "INDUSOFT"))
    sql_username: str | None = Field(default=os.getenv("SQL_USERNAME"))
    sql_password: str | None = Field(default=os.getenv("SQL_PASSWORD"))
    sql_encrypt: str = Field(default=os.getenv("SQL_ENCRYPT", "Optional"))
    sql_trust_server_certificate: str = Field(
        default=os.getenv("SQL_TRUST_SERVER_CERTIFICATE", "yes")
    )
    sql_connection_string_override: str | None = Field(
        default=os.getenv("SQL_CONNECTION_STRING")
    )

    initial_lookback_hours: int = Field(
        default=int(os.getenv("INITIAL_LOOKBACK_HOURS", "24"))
    )
    cache_ttl_seconds: int = Field(default=int(os.getenv("CACHE_TTL_SECONDS", "60")))
    api_readings_limit: int = Field(default=int(os.getenv("API_READINGS_LIMIT", "50")))
    demo_csv_chunk_size: int = Field(
        default=int(os.getenv("DEMO_CSV_CHUNK_SIZE", "20000"))
    )
    demo_csv_bootstrap_rows: int = Field(
        default=int(os.getenv("DEMO_CSV_BOOTSTRAP_ROWS", "5000"))
    )
    demo_csv_full_bootstrap: bool = Field(
        default=os.getenv("DEMO_CSV_FULL_BOOTSTRAP", "true").lower() == "true"
    )
    alert_rules_path: Path = Field(
        default=BASE_DIR / os.getenv("ALERT_RULES_PATH", "config/alert_rules.json")
    )
    demo_csv_path: Path = Field(
        default=BASE_DIR / os.getenv("DEMO_CSV_PATH", "data/demo_ta6000.csv")
    )
    sqlite_path: Path = Field(
        default=BASE_DIR / os.getenv("SQLITE_PATH", "data/alerts.db")
    )

    @computed_field  # type: ignore[misc]
    @property
    def sql_connection_string(self) -> str:
        if self.sql_connection_string_override:
            return self.sql_connection_string_override

        parts = [
            f"Server={self.sql_server},{self.sql_port}",
            f"Database={self.sql_database}",
            f"Encrypt={self.sql_encrypt}",
            f"TrustServerCertificate={self.sql_trust_server_certificate}",
        ]

        if self.sql_username and self.sql_password:
            parts.extend(
                [
                    f"User Id={self.sql_username}",
                    f"Password={self.sql_password}",
                ]
            )

        return ";".join(parts)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retorna uma instancia cacheada das configuracoes."""

    return Settings()
