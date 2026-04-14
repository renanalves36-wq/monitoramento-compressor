"""Testes de sanidade do motor de alertas."""

from __future__ import annotations

import unittest
from datetime import datetime
from pathlib import Path

import pandas as pd

from app.config import Settings
from app.domain.schemas import DataQualityIssue, LlmInsight
from app.services.alert_service import AlertService


class AlertServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = AlertService(Path("config/alert_rules.json"))

    def test_fixed_and_anomaly_rules_generate_alerts(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "timestamp": datetime(2026, 4, 9, 8, 0, 0),
                    "mode_key": "EM FUNCIONAMENTO|CARREGADO",
                    "pv_pres_sistema_bar": 8.2,
                    "pv_pres_descarga_bar": 6.0,
                    "pv_temp_oleo_lubrificacao_c": 40.0,
                    "pv_vib_max_mils": 1.0,
                    "pv_vib_estagio_1_mils": 0.9,
                    "pv_vib_estagio_2_mils": 0.9,
                    "pv_vib_estagio_3_mils": 0.9,
                    "pv_pres_oleo_bar": 8.0,
                    "delta_filtro_oleo_bar": 0.5,
                    "pv_pres_vacuo_cx_engran_inh2o": 25.0,
                    "pv_corr_motor_a": 120.0,
                    "pv_temp_fase_a_do_estator_c": 80.0,
                    "pv_temp_fase_b_do_estator_c": 80.0,
                    "pv_temp_fase_c_do_estator_c": 80.0,
                    "pv_temp_rolamento_dianteiro_motor": 50.0,
                    "pv_temp_ar_estagio_3_c": 0.0,
                    "pv_temp_oleo_lubrificacao_c__slope_15m": 0.0,
                    "pv_vib_max_mils__zscore_1h": 0.0,
                    "pv_corr_motor_a__slope_1h": 0.0,
                    "pv_pres_descarga_bar__ewma_gap_abs": 0.0,
                }
            ]
        )
        quality_issues = [
            DataQualityIssue(
                issue_type="zero_abnormal",
                signal="pv_temp_ar_estagio_3_c",
                timestamp=datetime(2026, 4, 9, 8, 0, 0),
                message="Valor zerado recorrente.",
            )
        ]

        alerts, scores = self.service.evaluate(frame, quality_issues)

        self.assertGreaterEqual(len(alerts), 2)
        self.assertTrue(any(alert.rule_id == "pressao_sistema_fora_faixa" for alert in alerts))
        self.assertTrue(any(alert.rule_id == "temperatura_estagio_3_zerada" for alert in alerts))
        self.assertTrue(
            any(
                alert.signal == "pv_pres_sistema_bar"
                and alert.prescriptive_diagnosis is not None
                for alert in alerts
            )
        )
        self.assertTrue(any(score.subsystem == "ar_processo" and score.score > 0 for score in scores))

    def test_sensor_stuck_requires_longer_window_and_lower_severity(self) -> None:
        rows = []
        for minute in range(20):
            rows.append(
                {
                    "timestamp": datetime(2026, 4, 9, 8, minute, 0),
                    "mode_key": "EM FUNCIONAMENTO|CARREGADO",
                    "st_oper": "EM FUNCIONAMENTO",
                    "st_carga_oper": "CARREGADO",
                    "pv_corr_motor_a": 181.0,
                }
            )

        short_frame = pd.DataFrame(rows)
        short_alerts, _ = self.service.evaluate(short_frame, [])
        self.assertFalse(any(alert.rule_id == "sensor_stuck::pv_corr_motor_a" for alert in short_alerts))

        for minute in range(20, 50):
            rows.append(
                {
                    "timestamp": datetime(2026, 4, 9, 8, minute, 0),
                    "mode_key": "EM FUNCIONAMENTO|CARREGADO",
                    "st_oper": "EM FUNCIONAMENTO",
                    "st_carga_oper": "CARREGADO",
                    "pv_corr_motor_a": 181.0,
                }
            )

        long_frame = pd.DataFrame(rows)
        long_alerts, _ = self.service.evaluate(long_frame, [])
        stuck_alert = next(
            alert for alert in long_alerts if alert.rule_id == "sensor_stuck::pv_corr_motor_a"
        )
        self.assertEqual(stuck_alert.severity, "low")
        self.assertGreaterEqual(float(stuck_alert.metadata["window_minutes"]), 45.0)

    def test_statistical_anomaly_requires_real_deviation(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "timestamp": datetime(2026, 4, 11, 8, 0, 0),
                    "mode_key": "EM FUNCIONAMENTO|CARREGADO",
                    "pv_vib_max_mils": 0.302,
                    "pv_vib_max_mils__zscore_1h": 4.2,
                    "pv_vib_max_mils__ma_1h": 0.300,
                    "pv_vib_max_mils__std_1h": 0.001,
                }
            ]
        )

        alerts, _ = self.service.evaluate(frame, [])

        self.assertFalse(any(alert.rule_id == "vibracao_max_em_alta" for alert in alerts))

    def test_statistical_alert_can_receive_llm_enrichment(self) -> None:
        settings = Settings(gemini_enabled=True, gemini_api_key="test-key")
        service = AlertService(Path("config/alert_rules.json"), settings=settings)
        service.gemini_service.generate_alert_insight = lambda **_: LlmInsight(
            provider="gemini",
            model="gemini-2.5-flash",
            confidence=0.72,
            summary="Leitura sintetica da IA.",
            insights=["A vibracao saiu do comportamento recente."],
        )
        frame = pd.DataFrame(
            [
                {
                    "timestamp": datetime(2026, 4, 11, 9, 0, 0),
                    "mode_key": "EM FUNCIONAMENTO|CARREGADO",
                    "pv_vib_max_mils": 0.38,
                    "pv_vib_max_mils__zscore_1h": 4.2,
                    "pv_vib_max_mils__ma_1h": 0.24,
                    "pv_vib_max_mils__std_1h": 0.03,
                }
            ]
        )

        alerts, _ = service.evaluate(frame, [])
        service.enrich_alerts_with_llm(alerts, frame)

        target = next(alert for alert in alerts if alert.rule_id == "vibracao_max_em_alta")
        self.assertIsNotNone(target.llm_insight)
        self.assertEqual(target.llm_insight.summary, "Leitura sintetica da IA.")


if __name__ == "__main__":
    unittest.main()
