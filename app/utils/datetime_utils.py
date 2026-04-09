"""Helpers de data e hora."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd


def utc_now() -> datetime:
    """Retorna timestamp atual em UTC."""

    return datetime.now(timezone.utc)


def ensure_datetime(value: Any) -> datetime | None:
    """Converte um valor para datetime quando possivel."""

    if value is None or value == "":
        return None
    converted = pd.to_datetime(value, errors="coerce")
    if pd.isna(converted):
        return None
    if isinstance(converted, pd.Timestamp):
        return converted.to_pydatetime()
    return converted


def lookback_datetime(hours: int) -> datetime:
    """Calcula o inicio da janela de lookback."""

    return datetime.now() - timedelta(hours=hours)


def to_iso(value: Any) -> str | None:
    """Serializa datas para string ISO."""

    dt_value = ensure_datetime(value)
    return dt_value.isoformat() if dt_value else None
