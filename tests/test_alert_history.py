"""Testes da avaliacao historica de alertas."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta

import pandas as pd

from app.config import get_settings
from app.services.alert_service import AlertService


class AlertHistoryTests(unittest.TestCase):
    def test_zero_abnormal_is_detected_in_history(self) -> None:
        service = AlertService(get_settings().alert_rules_path)
        start = datetime(2026, 4, 9, 7, 0, 0)
        rows = []
        for index in range(6):
            rows.append(
                {
                    "timestamp": start + timedelta(minutes=index),
                    "mode_key": "EM FUNCIONAMENTO|CARREGADO",
                    "st_oper": "EM FUNCIONAMENTO",
                    "st_carga_oper": "CARREGADO",
                    "pv_temp_ar_estagio_3_c": 0.0,
                }
            )

        frame = pd.DataFrame(rows)
        active_alerts, event_history, _scores = service.evaluate_history(frame, quality_issues=[])

        self.assertTrue(any(alert.rule_id == "temperatura_estagio_3_zerada" for alert in active_alerts))
        self.assertTrue(any(alert.rule_id == "temperatura_estagio_3_zerada" for alert in event_history))


if __name__ == "__main__":
    unittest.main()
