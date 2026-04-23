"""Testes dos calculos de vazao do TA6000."""

from __future__ import annotations

import unittest

from app.services.flow_service import (
    calculate_current_to_normal_factor,
    calculate_dry_air_partial_pressure_kpa,
    calculate_flow_loss_m3h,
    calculate_flow_utilization_pct,
    calculate_qa_m3h,
    calculate_qn_m3h,
    calculate_vapor_partial_pressure_kpa,
)


class FlowServiceTest(unittest.TestCase):
    def test_ambient_conversion_factor_matches_defined_basis(self) -> None:
        vapor_pressure = calculate_vapor_partial_pressure_kpa(
            relative_humidity_pct=90,
            saturation_vapor_pressure_kpa=3.7831,
        )
        dry_air_pressure = calculate_dry_air_partial_pressure_kpa(
            atmospheric_pressure_kpa=101.325,
            vapor_partial_pressure_kpa=vapor_pressure,
        )
        factor = calculate_current_to_normal_factor(
            dry_air_partial_pressure_kpa=dry_air_pressure,
            atmospheric_pressure_kpa=101.325,
            suction_temperature_c=28,
        )

        self.assertAlmostEqual(vapor_pressure, 3.40479, places=5)
        self.assertAlmostEqual(dry_air_pressure, 97.92021, places=5)
        self.assertAlmostEqual(factor, 0.87654, places=5)

    def test_qn_is_limited_to_nominal_and_qa_is_suction_equivalent(self) -> None:
        qn_m3h = calculate_qn_m3h(
            current_a=180,
            no_load_current_a=0,
            nominal_current_a=180,
            nominal_flow_nm3h=12000,
        )
        qa_m3h = calculate_qa_m3h(
            qn_m3h=qn_m3h,
            current_to_normal_factor=0.87658,
        )

        self.assertAlmostEqual(qn_m3h or 0, 12000, places=5)
        self.assertAlmostEqual(qa_m3h or 0, 13689.57, places=2)

        overloaded_qn = calculate_qn_m3h(
            current_a=195,
            no_load_current_a=0,
            nominal_current_a=180,
            nominal_flow_nm3h=12000,
        )
        self.assertEqual(overloaded_qn, 12000)

    def test_qn_is_clamped_to_zero_below_no_load_current(self) -> None:
        qn_m3h = calculate_qn_m3h(
            current_a=20,
            no_load_current_a=30,
            nominal_current_a=180,
            nominal_flow_nm3h=12000,
        )

        self.assertEqual(qn_m3h, 0.0)

    def test_flow_loss_and_utilization_use_nominal_capacity(self) -> None:
        loss = calculate_flow_loss_m3h(qn_m3h=9600, nominal_flow_nm3h=12000)
        utilization = calculate_flow_utilization_pct(qn_m3h=9600, nominal_flow_nm3h=12000)
        overloaded_loss = calculate_flow_loss_m3h(qn_m3h=13000, nominal_flow_nm3h=12000)
        overloaded_utilization = calculate_flow_utilization_pct(
            qn_m3h=13000,
            nominal_flow_nm3h=12000,
        )

        self.assertEqual(loss, 2400)
        self.assertEqual(utilization, 80)
        self.assertEqual(overloaded_loss, 0)
        self.assertEqual(overloaded_utilization, 100)


if __name__ == "__main__":
    unittest.main()
