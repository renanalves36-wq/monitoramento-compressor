"""Testes do motor prescritivo do TA6000."""

from __future__ import annotations

import unittest

from app.services.prescriptive_service import PrescriptiveService


class PrescriptiveServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = PrescriptiveService()

    def _base_payload(self) -> dict[str, object]:
        return {
            "st_oper": "EM FUNCIONAMENTO",
            "st_carga_oper": "CARREGADO",
            "mode_key": "EM FUNCIONAMENTO|CARREGADO",
            "pv_corr_motor_a": 170.0,
            "pv_corr_motor_a__ma_1h": 168.0,
            "pv_temp_oleo_lubrificacao_c": 45.0,
            "pv_temp_oleo_lubrificacao_c__ma_1h": 44.5,
            "pv_vib_estagio_1_mils": 0.8,
            "pv_vib_estagio_1_mils__ma_1h": 0.79,
            "pv_vib_estagio_2_mils": 0.9,
            "pv_vib_estagio_2_mils__ma_1h": 0.88,
            "pv_vib_estagio_3_mils": 0.85,
            "pv_vib_estagio_3_mils__ma_1h": 0.84,
            "pv_vib_max_mils": 0.9,
            "pv_vib_max_mils__ma_1h": 0.88,
            "pv_pres_descarga_bar": 7.3,
            "pv_pres_sistema_bar": 7.0,
            "sp_pres_sistema_bar": 6.8,
            "sp_pres_setpoint_descarga_bar": 7.0,
            "pv_pos_valv_bypass_pct": 5.0,
            "pv_pos_abert_valv_admissao_pct": 60.0,
            "pv_pos_alivio_pct": 0.0,
            "pv_temp_fase_a_do_estator_c": 115.0,
            "pv_temp_fase_b_do_estator_c": 116.0,
            "pv_temp_fase_c_do_estator_c": 114.0,
            "pv_temp_rolamento_dianteiro_motor": 62.0,
            "pv_pres_oleo_bar": 8.5,
            "pv_pres_oleo_antes_filtro_bar": 9.2,
            "delta_filtro_oleo_bar": 0.7,
            "pv_niv_interruptor_oleo_bar": 1,
            "pv_pres_vacuo_cx_engran_inh2o": 10.0,
            "pv_temp_ar_estagio_3_c": 45.0,
            "pv_temp_ar_estagio_3_c__ma_1h": 44.0,
            "pv_temp_ar_estagio_3_c__std_1h": 0.5,
            "pv_temp_ar_estagio_3_c__max_1h": 46.0,
            "pv_pres_sistema_bar__std_15m": 0.05,
            "pv_pres_sistema_bar__min_15m": 6.9,
            "pv_pres_sistema_bar__max_15m": 7.2,
        }

    def test_oil_temperature_high_with_stable_current_and_vibration_favors_peripheral(self) -> None:
        payload = self._base_payload()
        payload["pv_temp_oleo_lubrificacao_c"] = 60.0
        payload["pv_temp_oleo_lubrificacao_c__ma_1h"] = 56.0

        diagnosis = self.service.generate_prescriptive_diagnosis(
            "pv_temp_oleo_lubrificacao_c",
            snapshot=payload,
            features=payload,
        )

        self.assertGreater(diagnosis.score_periferico, diagnosis.score_interno)
        self.assertIn("pv_corr_motor_a_estavel", diagnosis.flags_ativas)
        self.assertIn("vibracao_estavel", diagnosis.flags_ativas)

    def test_stage_2_vibration_with_high_current_and_oil_favors_internal(self) -> None:
        payload = self._base_payload()
        payload["pv_vib_estagio_2_mils"] = 1.9
        payload["pv_vib_estagio_2_mils__ma_1h"] = 1.4
        payload["pv_vib_max_mils"] = 1.9
        payload["pv_vib_max_mils__ma_1h"] = 1.4
        payload["pv_corr_motor_a"] = 195.0
        payload["pv_corr_motor_a__ma_1h"] = 186.0
        payload["pv_temp_oleo_lubrificacao_c"] = 58.0
        payload["pv_temp_oleo_lubrificacao_c__ma_1h"] = 55.0

        diagnosis = self.service.generate_prescriptive_diagnosis(
            "pv_vib_estagio_2_mils",
            snapshot=payload,
            features=payload,
        )

        self.assertGreater(diagnosis.score_interno, diagnosis.score_periferico)
        self.assertEqual(diagnosis.hipoteses[0].tipo, "interno")

    def test_discharge_pressure_with_large_delta_favors_peripheral(self) -> None:
        payload = self._base_payload()
        payload["pv_pres_descarga_bar"] = 8.6
        payload["sp_pres_setpoint_descarga_bar"] = 7.0
        payload["pv_pres_sistema_bar"] = 7.1

        diagnosis = self.service.generate_prescriptive_diagnosis(
            "pv_pres_descarga_bar",
            snapshot=payload,
            features=payload,
        )

        self.assertGreater(diagnosis.score_periferico, diagnosis.score_interno)
        self.assertIn("delta_descarga_sistema_alto", diagnosis.flags_ativas)

    def test_phase_a_temperature_detects_stator_asymmetry(self) -> None:
        payload = self._base_payload()
        payload["pv_temp_fase_a_do_estator_c"] = 160.0
        payload["pv_temp_fase_b_do_estator_c"] = 120.0
        payload["pv_temp_fase_c_do_estator_c"] = 118.0

        flags = self.service.build_context_flags(payload, payload)
        diagnosis = self.service.generate_prescriptive_diagnosis(
            "pv_temp_fase_a_do_estator_c",
            snapshot=payload,
            features=payload,
        )

        self.assertTrue(flags["assimetria_estator"])
        self.assertTrue(flags["fase_a_assimetrica"])
        self.assertIn("assimetria", " ".join(diagnosis.observacoes))

    def test_vacuum_incoherent_value_points_to_instrumentation(self) -> None:
        payload = self._base_payload()
        payload["pv_pres_vacuo_cx_engran_inh2o"] = 60.0

        diagnosis = self.service.generate_prescriptive_diagnosis(
            "pv_pres_vacuo_cx_engran_inh2o",
            snapshot=payload,
            features=payload,
        )

        self.assertIn("vacuo_cx_engran_inconsistente", diagnosis.flags_ativas)
        self.assertEqual(diagnosis.hipoteses[0].causa, "erro_de_escala_ou_sensor")

    def test_stage_3_air_temperature_zero_adds_instrumentation_suspicion(self) -> None:
        payload = self._base_payload()
        payload["pv_temp_ar_estagio_3_c"] = 0.0
        payload["pv_temp_ar_estagio_3_c__ma_1h"] = 0.0
        payload["pv_temp_ar_estagio_3_c__std_1h"] = 0.0
        payload["pv_temp_ar_estagio_3_c__max_1h"] = 0.0

        diagnosis = self.service.generate_prescriptive_diagnosis(
            "pv_temp_ar_estagio_3_c",
            snapshot=payload,
            features=payload,
        )

        self.assertIn("temp_ar_estagio_3_zerada", diagnosis.flags_ativas)
        self.assertTrue(any("instrumentacao" in item for item in diagnosis.observacoes))
        self.assertIn("validar sensor da temperatura", diagnosis.acoes_recomendadas)


if __name__ == "__main__":
    unittest.main()
