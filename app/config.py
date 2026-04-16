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
    sensor_stuck_min_points: int = Field(
        default=int(os.getenv("SENSOR_STUCK_MIN_POINTS", "45"))
    )
    sensor_stuck_min_duration_minutes: int = Field(
        default=int(os.getenv("SENSOR_STUCK_MIN_DURATION_MINUTES", "45"))
    )
    sensor_stuck_relative_range_tolerance: float = Field(
        default=float(os.getenv("SENSOR_STUCK_RELATIVE_RANGE_TOLERANCE", "0.001"))
    )
    sensor_stuck_absolute_range_tolerance: float = Field(
        default=float(os.getenv("SENSOR_STUCK_ABSOLUTE_RANGE_TOLERANCE", "0.01"))
    )
    predictive_alerts_enabled: bool = Field(
        default=os.getenv("PREDICTIVE_ALERTS_ENABLED", "true").lower() == "true"
    )
    predictive_min_confidence: float = Field(
        default=float(os.getenv("PREDICTIVE_MIN_CONFIDENCE", "0.68"))
    )
    predictive_forecast_horizon_minutes: int = Field(
        default=int(os.getenv("PREDICTIVE_FORECAST_HORIZON_MINUTES", "180"))
    )
    predictive_trip_horizon_minutes: int = Field(
        default=int(os.getenv("PREDICTIVE_TRIP_HORIZON_MINUTES", "45"))
    )
    predictive_min_points: int = Field(
        default=int(os.getenv("PREDICTIVE_MIN_POINTS", "18"))
    )
    predictive_min_regression_r2: float = Field(
        default=float(os.getenv("PREDICTIVE_MIN_REGRESSION_R2", "0.55"))
    )
    flow_suction_temperature_c: float = Field(
        default=float(os.getenv("FLOW_SUCTION_TEMPERATURE_C", "28"))
    )
    flow_suction_relative_humidity_pct: float = Field(
        default=float(os.getenv("FLOW_SUCTION_RELATIVE_HUMIDITY_PCT", "90"))
    )
    flow_atmospheric_pressure_kpa: float = Field(
        default=float(os.getenv("FLOW_ATMOSPHERIC_PRESSURE_KPA", "101.325"))
    )
    flow_saturation_vapor_pressure_kpa: float = Field(
        default=float(os.getenv("FLOW_SATURATION_VAPOR_PRESSURE_KPA", "3.7831"))
    )
    flow_current_to_normal_factor: float = Field(
        default=float(os.getenv("FLOW_CURRENT_TO_NORMAL_FACTOR", "0.87658"))
    )
    flow_nominal_nm3h: float = Field(
        default=float(os.getenv("FLOW_NOMINAL_NM3H", "12000"))
    )
    flow_nominal_current_a: float = Field(
        default=float(os.getenv("FLOW_NOMINAL_CURRENT_A", "180"))
    )
    flow_no_load_current_a: float = Field(
        default=float(os.getenv("FLOW_NO_LOAD_CURRENT_A", "0"))
    )
    gemini_enabled: bool = Field(
        default=os.getenv("GEMINI_ENABLED", "false").lower() == "true"
    )
    gemini_api_key: str | None = Field(default=os.getenv("GEMINI_API_KEY"))
    gemini_model: str = Field(default=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))
    gemini_temperature: float = Field(
        default=float(os.getenv("GEMINI_TEMPERATURE", "0.1"))
    )
    gemini_max_output_tokens: int = Field(
        default=int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "1200"))
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
