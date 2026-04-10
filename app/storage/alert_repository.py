"""Repositorio SQLite para alertas ativos e historico simples."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from app.domain.schemas import AlertRecord, PrescriptiveDiagnosis


class AlertRepository:
    """Gerencia a persistencia local dos alertas."""

    def __init__(self, sqlite_path: Path) -> None:
        self.sqlite_path = sqlite_path

    def initialize(self) -> None:
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.sqlite_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS alerts (
                    alert_id TEXT PRIMARY KEY,
                    rule_id TEXT NOT NULL,
                    layer TEXT NOT NULL,
                    subsystem TEXT NOT NULL,
                    signal TEXT,
                    severity TEXT NOT NULL,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    triggered_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    current_value TEXT,
                    threshold TEXT,
                    mode_key TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );
                """
            )
            connection.commit()

    def replace_active_alerts(self, alerts: list[AlertRecord]) -> None:
        with sqlite3.connect(self.sqlite_path) as connection:
            connection.execute("UPDATE alerts SET is_active = 0")

            for alert in alerts:
                metadata_payload = dict(alert.metadata)
                if alert.prescriptive_diagnosis is not None:
                    metadata_payload["prescriptive_diagnosis"] = (
                        alert.prescriptive_diagnosis.model_dump()
                    )
                connection.execute(
                    """
                    INSERT INTO alerts (
                        alert_id,
                        rule_id,
                        layer,
                        subsystem,
                        signal,
                        severity,
                        title,
                        message,
                        triggered_at,
                        last_seen_at,
                        current_value,
                        threshold,
                        mode_key,
                        is_active,
                        metadata_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                    ON CONFLICT(alert_id) DO UPDATE SET
                        severity = excluded.severity,
                        title = excluded.title,
                        message = excluded.message,
                        last_seen_at = excluded.last_seen_at,
                        current_value = excluded.current_value,
                        threshold = excluded.threshold,
                        mode_key = excluded.mode_key,
                        is_active = 1,
                        metadata_json = excluded.metadata_json;
                    """,
                    (
                        alert.alert_id,
                        alert.rule_id,
                        alert.layer,
                        alert.subsystem,
                        alert.signal,
                        alert.severity,
                        alert.title,
                        alert.message,
                        alert.triggered_at.isoformat(),
                        alert.last_seen_at.isoformat(),
                        None if alert.current_value is None else str(alert.current_value),
                        alert.threshold,
                        alert.mode_key,
                        json.dumps(metadata_payload, ensure_ascii=True),
                    ),
                )

            connection.commit()

    def list_alerts(self, active_only: bool = True) -> list[AlertRecord]:
        query = """
            SELECT
                alert_id,
                rule_id,
                layer,
                subsystem,
                signal,
                severity,
                title,
                message,
                triggered_at,
                last_seen_at,
                current_value,
                threshold,
                mode_key,
                is_active,
                metadata_json
            FROM alerts
        """
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY last_seen_at DESC;"

        with sqlite3.connect(self.sqlite_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(query).fetchall()

        alerts: list[AlertRecord] = []
        for row in rows:
            metadata_payload = json.loads(row["metadata_json"] or "{}")
            diagnosis_payload = metadata_payload.pop("prescriptive_diagnosis", None)
            alerts.append(
                AlertRecord(
                    alert_id=row["alert_id"],
                    rule_id=row["rule_id"],
                    layer=row["layer"],
                    subsystem=row["subsystem"],
                    signal=row["signal"],
                    severity=row["severity"],
                    title=row["title"],
                    message=row["message"],
                    triggered_at=row["triggered_at"],
                    last_seen_at=row["last_seen_at"],
                    current_value=row["current_value"],
                    threshold=row["threshold"],
                    mode_key=row["mode_key"],
                    is_active=bool(row["is_active"]),
                    metadata=metadata_payload,
                    prescriptive_diagnosis=(
                        None
                        if diagnosis_payload is None
                        else PrescriptiveDiagnosis.model_validate(diagnosis_payload)
                    ),
                )
            )
        return alerts
