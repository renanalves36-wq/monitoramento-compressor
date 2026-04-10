"""Leitura incremental, limpeza e validacao dos dados do compressor."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pandas as pd

from app.config import Settings
from app.db.connection import open_connection
from app.db.queries import build_incremental_query, build_recent_window_query
from app.domain.mappings import (
    CALIBRATION_HINTS,
    DERIVED_SIGNALS,
    NUMERIC_SIGNALS,
    PLAUSIBLE_RANGES,
    STUCK_SENSOR_SIGNALS,
    ZERO_ABNORMAL_SIGNALS,
)
from app.domain.schemas import DataQualityIssue
from app.utils.logger import get_logger


@dataclass(slots=True)
class IngestionBatch:
    frame: pd.DataFrame
    quality_issues: list[DataQualityIssue]
    source: str = "unknown"


class IngestionService:
    """Responsavel por buscar e sanear os dados vindos do SQL Server."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.logger = get_logger(__name__)

    def fetch_recent_window(
        self, since: datetime, limit: int | None = None
    ) -> IngestionBatch:
        query = build_recent_window_query(since=since, limit=limit)
        return self._fetch(query=query, parameter=since, incremental=False, limit=limit)

    def fetch_incremental(
        self, since_timestamp: datetime, limit: int | None = None
    ) -> IngestionBatch:
        query = build_incremental_query(limit=limit)
        return self._fetch(
            query=query,
            parameter=since_timestamp,
            incremental=True,
            limit=limit,
        )

    def _fetch(
        self,
        query: str,
        parameter: datetime,
        incremental: bool,
        limit: int | None,
    ) -> IngestionBatch:
        mode = self.settings.data_source_mode
        if mode == "demo_csv":
            return self._fetch_demo_batch(
                parameter=parameter,
                incremental=incremental,
                limit=limit,
            )

        if mode == "sql":
            return self._fetch_sql_batch(query=query, parameter=parameter)

        try:
            return self._fetch_sql_batch(query=query, parameter=parameter)
        except Exception as exc:
            self.logger.warning(
                "sql_unavailable_falling_back_to_demo",
                extra={
                    "error": str(exc),
                    "demo_csv_path": str(self.settings.demo_csv_path),
                },
            )
            return self._fetch_demo_batch(
                parameter=parameter,
                incremental=incremental,
                limit=limit,
            )

    def _fetch_sql_batch(self, query: str, parameter: datetime) -> IngestionBatch:
        with open_connection(self.settings) as connection:
            cursor = connection.cursor()
            cursor.execute(query, (parameter,))
            rows = cursor.fetchall()
            columns = [column[0] for column in cursor.description]
            cursor.close()

        records = [self._row_to_dict(row=row, columns=columns) for row in rows]
        raw_frame = pd.DataFrame(records)
        clean_frame, issues = self._clean_and_validate(raw_frame)

        self.logger.info(
            "sql_batch_loaded",
            extra={
                "rows_read": len(raw_frame),
                "rows_clean": len(clean_frame),
                "issues_found": len(issues),
            },
        )
        return IngestionBatch(frame=clean_frame, quality_issues=issues, source="sql")

    def _fetch_demo_batch(
        self,
        parameter: datetime,
        incremental: bool,
        limit: int | None,
    ) -> IngestionBatch:
        demo_path = self.settings.demo_csv_path
        if not demo_path.exists():
            raise FileNotFoundError(f"Demo CSV not found: {demo_path}")

        filtered = self._read_demo_csv_window(
            demo_path=demo_path,
            parameter=parameter,
            incremental=incremental,
            limit=limit,
        )

        clean_frame, issues = self._clean_and_validate(filtered.reset_index(drop=True))
        self.logger.info(
            "demo_csv_batch_loaded",
            extra={
                "demo_csv_path": str(demo_path),
                "rows_read": int(len(filtered)),
                "rows_clean": int(len(clean_frame)),
                "issues_found": int(len(issues)),
            },
        )
        return IngestionBatch(frame=clean_frame, quality_issues=issues, source="demo_csv")

    def _read_demo_csv_window(
        self,
        demo_path: Any,
        parameter: datetime,
        incremental: bool,
        limit: int | None,
    ) -> pd.DataFrame:
        parameter_ts = pd.to_datetime(parameter)
        row_budget = limit or self.settings.demo_csv_bootstrap_rows
        fallback_budget = max(row_budget, self.settings.demo_csv_bootstrap_rows)

        filtered_buffer = pd.DataFrame()
        fallback_buffer = pd.DataFrame()
        matched_any = False

        reader = pd.read_csv(
            demo_path,
            decimal=",",
            chunksize=self.settings.demo_csv_chunk_size,
        )

        for chunk in reader:
            if "timestamp" not in chunk.columns:
                raise ValueError("Demo CSV must contain a 'timestamp' column.")

            chunk["timestamp"] = pd.to_datetime(chunk["timestamp"], errors="coerce")
            chunk = chunk.dropna(subset=["timestamp"])
            if chunk.empty:
                continue

            fallback_buffer = (
                pd.concat([fallback_buffer, chunk], ignore_index=True)
                .tail(fallback_budget)
                .reset_index(drop=True)
            )

            if incremental:
                window_chunk = chunk[chunk["timestamp"] > parameter_ts]
            else:
                window_chunk = chunk[chunk["timestamp"] >= parameter_ts]

            if window_chunk.empty:
                continue

            matched_any = True
            filtered_buffer = (
                pd.concat([filtered_buffer, window_chunk], ignore_index=True)
                .tail(row_budget)
                .reset_index(drop=True)
            )

        if matched_any:
            return filtered_buffer.sort_values("timestamp").reset_index(drop=True)

        if incremental:
            return pd.DataFrame()

        return fallback_buffer.sort_values("timestamp").tail(row_budget).reset_index(drop=True)

    @staticmethod
    def _row_to_dict(row: Any, columns: list[str]) -> dict[str, Any]:
        if isinstance(row, dict):
            return row
        if hasattr(row, "keys"):
            return {key: row[key] for key in row.keys()}
        return dict(zip(columns, row, strict=False))

    def _clean_and_validate(
        self, frame: pd.DataFrame
    ) -> tuple[pd.DataFrame, list[DataQualityIssue]]:
        if frame.empty:
            return frame, []

        issues: list[DataQualityIssue] = []
        clean = frame.copy()

        clean["timestamp"] = pd.to_datetime(clean["timestamp"], errors="coerce")
        invalid_ts = clean["timestamp"].isna().sum()
        if invalid_ts:
            issues.append(
                DataQualityIssue(
                    issue_type="invalid_timestamp",
                    message="Linhas com timestamp invalido foram descartadas.",
                    details={"count": int(invalid_ts)},
                )
            )
        clean = clean.dropna(subset=["timestamp"]).sort_values("timestamp")

        duplicated = clean[clean.duplicated(subset=["timestamp"], keep="last")]
        if not duplicated.empty:
            issues.append(
                DataQualityIssue(
                    issue_type="duplicate_timestamp",
                    message="Timestamps duplicados foram consolidados mantendo a ultima leitura.",
                    details={"count": int(len(duplicated))},
                )
            )
            clean = clean.drop_duplicates(subset=["timestamp"], keep="last")

        for column in NUMERIC_SIGNALS:
            if column in clean.columns:
                clean[column] = pd.to_numeric(clean[column], errors="coerce")

        if "status" in clean.columns:
            clean["status"] = pd.to_numeric(clean["status"], errors="coerce").astype("Int64")
        if "st_plc" in clean.columns:
            clean["st_plc"] = clean["st_plc"].astype("boolean")

        for column in ("hora", "data", "ds_turno", "st_oper", "st_carga_oper", "ds_erro"):
            if column in clean.columns:
                clean[column] = clean[column].astype("string")
        if "st_ponto_de_controle" in clean.columns:
            clean["st_ponto_de_controle"] = clean["st_ponto_de_controle"].astype("string")

        clean = self._add_derived_columns(clean)
        clean["mode_key"] = (
            clean["st_oper"].fillna("DESCONHECIDO")
            + "|"
            + clean["st_carga_oper"].fillna("DESCONHECIDO")
        )
        clean["is_normal_operation"] = clean["mode_key"].eq("EM FUNCIONAMENTO|CARREGADO")

        issues.extend(self._collect_null_issues(clean))
        issues.extend(self._collect_zero_issues(clean))
        issues.extend(self._collect_stuck_sensor_issues(clean))
        issues.extend(self._collect_plausibility_issues(clean))

        clean = clean.reset_index(drop=True)
        return clean, issues

    def _add_derived_columns(self, frame: pd.DataFrame) -> pd.DataFrame:
        for signal in DERIVED_SIGNALS:
            if signal not in frame.columns:
                frame[signal] = pd.NA

        if {
            "pv_pres_oleo_antes_filtro_bar",
            "pv_pres_oleo_bar",
        }.issubset(frame.columns):
            frame["delta_filtro_oleo_bar"] = (
                frame["pv_pres_oleo_antes_filtro_bar"] - frame["pv_pres_oleo_bar"]
            )

        vibration_columns = [
            column
            for column in (
                "pv_vib_estagio_1_mils",
                "pv_vib_estagio_2_mils",
                "pv_vib_estagio_3_mils",
            )
            if column in frame.columns
        ]
        if vibration_columns:
            frame["pv_vib_max_mils"] = frame[vibration_columns].max(axis=1)

        stator_columns = [
            column
            for column in (
                "pv_temp_fase_a_do_estator_c",
                "pv_temp_fase_b_do_estator_c",
                "pv_temp_fase_c_do_estator_c",
            )
            if column in frame.columns
        ]
        if stator_columns:
            frame["pv_temp_estator_max_c"] = frame[stator_columns].max(axis=1)

        return frame

    def _collect_null_issues(self, frame: pd.DataFrame) -> list[DataQualityIssue]:
        issues: list[DataQualityIssue] = []
        for column in frame.columns:
            null_count = int(frame[column].isna().sum())
            if null_count:
                issues.append(
                    DataQualityIssue(
                        issue_type="nulls",
                        signal=column,
                        message="Foram encontrados valores nulos na coluna.",
                        details={"count": null_count},
                    )
                )
        return issues

    def _collect_zero_issues(self, frame: pd.DataFrame) -> list[DataQualityIssue]:
        issues: list[DataQualityIssue] = []
        latest_ts = frame["timestamp"].max()
        for signal in ZERO_ABNORMAL_SIGNALS:
            if signal not in frame.columns:
                continue
            tail = frame[signal].dropna().tail(5)
            if len(tail) >= 3 and bool((tail == 0).all()):
                issues.append(
                    DataQualityIssue(
                        issue_type="zero_abnormal",
                        signal=signal,
                        timestamp=latest_ts,
                        message="Valor zerado recorrente detectado para uma variavel sensivel.",
                        details={"window_points": int(len(tail))},
                    )
                )
        return issues

    def _collect_stuck_sensor_issues(self, frame: pd.DataFrame) -> list[DataQualityIssue]:
        issues: list[DataQualityIssue] = []
        latest_ts = frame["timestamp"].max()
        for signal in STUCK_SENSOR_SIGNALS:
            if signal not in frame.columns:
                continue
            tail = frame[signal].dropna().tail(10)
            if len(tail) >= 5 and tail.nunique(dropna=True) == 1:
                issues.append(
                    DataQualityIssue(
                        issue_type="sensor_stuck",
                        signal=signal,
                        timestamp=latest_ts,
                        message="Possivel sensor travado por repeticao persistente do mesmo valor.",
                        details={"repeated_value": float(tail.iloc[-1]), "window_points": int(len(tail))},
                    )
                )
        return issues

    def _collect_plausibility_issues(self, frame: pd.DataFrame) -> list[DataQualityIssue]:
        issues: list[DataQualityIssue] = []
        for signal, limits in PLAUSIBLE_RANGES.items():
            if signal not in frame.columns:
                continue
            violations = frame[
                (frame[signal].notna())
                & (
                    (frame[signal] < limits["min"])
                    | (frame[signal] > limits["max"])
                )
            ]
            if violations.empty:
                continue

            latest_violation = violations.iloc[-1]
            details = {
                "min": limits["min"],
                "max": limits["max"],
                "last_value": float(latest_violation[signal]),
            }
            if signal in CALIBRATION_HINTS:
                details["engineering_hint"] = CALIBRATION_HINTS[signal]

            issues.append(
                DataQualityIssue(
                    issue_type="plausibility",
                    signal=signal,
                    timestamp=latest_violation["timestamp"],
                    message="Valor fora da faixa plausivel basica.",
                    details=details,
                )
            )
        return issues
