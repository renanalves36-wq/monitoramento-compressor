"""Testes do motor de analise de influencia da Qn."""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from app.services.analysis_engine import build_analysis_payload


def _base_frame(n: int = 160) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    x = np.linspace(0.0, 1.0, n)
    frame = pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-04-10 00:00:00", periods=n, freq="min"),
            "st_oper": "EM FUNCIONAMENTO",
            "st_carga_oper": "CARREGADO",
            "pv_pos_abert_valv_admissao_pct": 82.0 + 2.0 * np.sin(x * 5.0) + rng.normal(0, 0.08, n),
            "pv_pos_valv_bypass_pct": 9.0 + 1.5 * np.cos(x * 4.0) + rng.normal(0, 0.06, n),
            "pv_pos_alivio_pct": 4.0 + rng.normal(0, 0.05, n),
            "pv_pres_descarga_bar": 7.0 + 0.25 * np.sin(x * 3.0) + rng.normal(0, 0.01, n),
            "pv_pres_sistema_bar": 6.4 + 0.08 * np.cos(x * 3.5) + rng.normal(0, 0.01, n),
            "pv_temp_oleo_lubrificacao_c": 50.0 + rng.normal(0, 0.05, n),
            "pv_pres_oleo_bar": 9.0 + rng.normal(0, 0.02, n),
            "pv_vib_estagio_1_mils": 0.30 + rng.normal(0, 0.01, n),
            "pv_vib_estagio_2_mils": 0.32 + rng.normal(0, 0.01, n),
            "pv_vib_estagio_3_mils": 0.28 + rng.normal(0, 0.01, n),
            "pv_temp_fase_a_do_estator_c": 118.0 + rng.normal(0, 0.2, n),
            "pv_temp_fase_b_do_estator_c": 117.0 + rng.normal(0, 0.2, n),
            "pv_temp_fase_c_do_estator_c": 118.5 + rng.normal(0, 0.2, n),
            "pv_temp_rolamento_dianteiro_motor": 62.0 + rng.normal(0, 0.15, n),
            "pv_temp_ar_estagio_3_c": 42.0 + rng.normal(0, 0.08, n),
            "pv_corr_motor_a": 165.0 + rng.normal(0, 0.3, n),
            "qa_m3h": 12000.0 + rng.normal(0, 5.0, n),
            "mode_key": "EM FUNCIONAMENTO|CARREGADO",
        }
    )
    return frame


class AnalysisEngineTest(unittest.TestCase):
    def test_process_or_control_dominance_when_discharge_and_bypass_drive_qn(self) -> None:
        frame = _base_frame()
        centered_discharge = frame["pv_pres_descarga_bar"] - frame["pv_pres_descarga_bar"].mean()
        centered_bypass = frame["pv_pos_valv_bypass_pct"] - frame["pv_pos_valv_bypass_pct"].mean()
        frame["qn_m3h"] = 10500.0 - 2600.0 * centered_discharge - 55.0 * centered_bypass

        payload = build_analysis_payload(frame, range_value=24, range_unit="hours")

        self.assertIn(
            payload.classificacao_origem.classificacao,
            {"dominancia_processo_rede", "dominancia_controle"},
        )
        self.assertGreater(payload.qualidade_modelo_direto.r2 or 0.0, 0.85)
        self.assertTrue(payload.influencia_direta)

    def test_qn_window_summary_keeps_latest_and_window_statistics_separate(self) -> None:
        frame = _base_frame(60)
        frame["qn_m3h"] = np.linspace(10000.0, 11200.0, len(frame))

        payload = build_analysis_payload(frame, range_value=24, range_unit="hours")

        self.assertEqual(payload.qn_atual, 11200.0)
        self.assertEqual(payload.qn_fim_janela, 11200.0)
        self.assertEqual(payload.qn_inicio_janela, 10000.0)
        self.assertEqual(payload.qn_media_janela, 10600.0)
        self.assertEqual(payload.qn_minima_janela, 10000.0)
        self.assertEqual(payload.qn_maxima_janela, 11200.0)
        self.assertEqual(payload.qn_variacao_janela, 1200.0)
        self.assertEqual(payload.qn_variacao_percentual_janela, 12.0)

    def test_internal_degradation_dominance_when_vibration_and_oil_drive_residual_loss(self) -> None:
        frame = _base_frame()
        trend = np.linspace(0.0, 1.0, len(frame))
        frame["pv_vib_estagio_2_mils"] = 0.35 + 0.65 * trend
        frame["pv_temp_oleo_lubrificacao_c"] = 50.0 + 8.0 * trend
        frame["qn_m3h"] = (
            10800.0
            - 850.0 * frame["pv_vib_estagio_2_mils"]
            - 42.0 * frame["pv_temp_oleo_lubrificacao_c"]
        )

        payload = build_analysis_payload(frame, range_value=24, range_unit="hours")

        self.assertEqual(payload.classificacao_origem.classificacao, "dominancia_degradacao_interna")
        self.assertGreater(payload.qualidade_modelo_desvio.r2 or 0.0, 0.80)
        self.assertIn(
            "pv_vib_estagio_2_mils",
            [item.variavel for item in payload.influencia_indireta[:3]],
        )

    def test_mixed_dominance_when_process_and_degradation_both_explain_qn(self) -> None:
        frame = _base_frame()
        trend = np.linspace(0.0, 1.0, len(frame))
        frame["pv_pres_descarga_bar"] = 7.0 + 0.45 * np.sin(trend * 8.0)
        frame["pv_vib_estagio_2_mils"] = 0.30 + 0.55 * trend
        direct = -900.0 * (frame["pv_pres_descarga_bar"] - frame["pv_pres_descarga_bar"].mean())
        internal = -750.0 * (frame["pv_vib_estagio_2_mils"] - frame["pv_vib_estagio_2_mils"].mean())
        frame["qn_m3h"] = 10000.0 + direct + internal

        payload = build_analysis_payload(frame, range_value=24, range_unit="hours")

        self.assertEqual(payload.classificacao_origem.classificacao, "dominancia_mista")

    def test_low_confidence_when_critical_signals_are_suspicious(self) -> None:
        frame = _base_frame(90)
        frame["pv_temp_ar_estagio_3_c"] = 0.0
        frame["pv_pres_vacuo_cx_engran_inh2o"] = 250.0
        frame["qn_m3h"] = 10000.0 + np.linspace(0.0, 20.0, len(frame))

        payload = build_analysis_payload(frame, range_value=24, range_unit="hours")

        self.assertEqual(payload.classificacao_origem.classificacao, "baixa_confianca")
        quality_codes = {item.code for item in payload.qualidade_dados}
        self.assertIn("persistent_zero_critical_signal", quality_codes)
        self.assertIn("engineering_inconsistent_signal", quality_codes)


if __name__ == "__main__":
    unittest.main()
