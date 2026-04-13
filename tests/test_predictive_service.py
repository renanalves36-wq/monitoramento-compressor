"""Testes da camada preditiva estatistica."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta

import pandas as pd

from app.config import Settings
from app.services.feature_service import FeatureService
from app.services.predictive_service import PredictiveService


class PredictiveServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = Settings(
            gemini_enabled=False,
            predictive_alerts_enabled=True,
            predictive_min_confidence=0.6,
            predictive_min_points=18,
            predictive_min_regression_r2=0.5,
        )
        self.service = PredictiveService(self.settings)
        self.feature_service = FeatureService()

    def _build_frame(self, values: list[float], signal: str, *, mode_key: str = "EM FUNCIONAMENTO|CARREGADO") -> pd.DataFrame:
        start = datetime(2026, 4, 13, 8, 0, 0)
        rows = []
        for index, value in enumerate(values):
            rows.append(
                {
                    "timestamp": start + timedelta(minutes=index),
                    "mode_key": mode_key,
                    "st_oper": "EM FUNCIONAMENTO" if mode_key == "EM FUNCIONAMENTO|CARREGADO" else "PARTINDO",
                    "st_carga_oper": "CARREGADO",
                    signal: value,
                    "pv_temp_oleo_lubrificacao_c": 48.0,
                    "pv_corr_motor_a": 172.0,
                    "pv_vib_estagio_1_mils": value if signal == "pv_vib_estagio_1_mils" else 0.55,
                    "pv_vib_estagio_2_mils": value if signal == "pv_vib_estagio_2_mils" else 0.62,
                    "pv_vib_estagio_3_mils": value if signal == "pv_vib_estagio_3_mils" else 0.58,
                    "pv_pres_descarga_bar": value if signal == "pv_pres_descarga_bar" else 7.05,
                    "pv_pres_sistema_bar": 6.65,
                    "pv_temp_fase_a_do_estator_c": 118.0,
                    "pv_temp_fase_b_do_estator_c": 117.0,
                    "pv_temp_fase_c_do_estator_c": 116.0,
                    "pv_temp_rolamento_dianteiro_motor": 63.0,
                    "pv_pos_valv_bypass_pct": 5.0,
                    "pv_pos_abert_valv_admissao_pct": 65.0,
                    "pv_pos_alivio_pct": 0.0,
                }
            )
        raw = pd.DataFrame(rows)
        return self.feature_service.compute(raw)

    def test_rising_stage_2_vibration_generates_predictive_alert(self) -> None:
        values = [0.45 + (0.025 * idx) for idx in range(24)]
        frame = self._build_frame(values, "pv_vib_estagio_2_mils")

        alerts = self.service.evaluate_current(frame, active_alerts=[])

        target = next(alert for alert in alerts if alert.signal == "pv_vib_estagio_2_mils")
        self.assertEqual(target.layer, "predictive_statistics")
        self.assertIsNotNone(target.predictive_diagnosis)
        self.assertGreater(target.predictive_diagnosis.confidence, 0.6)
        self.assertIn(target.predictive_diagnosis.predicted_event, {"critical_alarm", "possible_trip"})

    def test_flat_signal_does_not_generate_predictive_alert(self) -> None:
        values = [0.55 for _ in range(24)]
        frame = self._build_frame(values, "pv_vib_estagio_2_mils")

        alerts = self.service.evaluate_current(frame, active_alerts=[])

        self.assertFalse(any(alert.signal == "pv_vib_estagio_2_mils" for alert in alerts))

    def test_transition_mode_suppresses_predictive_alert(self) -> None:
        values = [0.45 + (0.03 * idx) for idx in range(24)]
        frame = self._build_frame(values, "pv_vib_estagio_2_mils", mode_key="PARTINDO|CARREGADO")

        alerts = self.service.evaluate_current(frame, active_alerts=[])

        self.assertEqual(alerts, [])


if __name__ == "__main__":
    unittest.main()
