"""Testes para limites e referencias do grafico de tendencia."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from app.api.routes_status import get_multi_signal_trend
from app.config import Settings
from app.services.health_service import HealthService
from app.storage.alert_repository import AlertRepository
from app.utils.datetime_utils import utc_now


class TrendLimitsTests(unittest.TestCase):
    def setUp(self) -> None:
        settings = Settings(sqlite_path=Path("data/test_trend_limits.db"))
        repository = AlertRepository(settings.sqlite_path)
        repository.initialize()
        self.service = HealthService(settings=settings, repository=repository)

    def test_between_rule_is_preserved_as_operational_range(self) -> None:
        lower_limit, upper_limit, target_value, rules = self.service._get_signal_limits_and_rules(
            "pv_pres_sistema_bar"
        )

        self.assertEqual(lower_limit, 5.0)
        self.assertEqual(upper_limit, 7.8)
        self.assertIsNone(target_value)
        self.assertTrue(any(rule.rule_id == "rede_pressao_alta" for rule in rules))
        self.assertTrue(any(rule.rule_id == "pressao_sistema_fora_faixa" for rule in rules))

    def test_target_current_uses_real_setpoint_signal(self) -> None:
        start = datetime(2026, 4, 9, 7, 0, 0)
        self.service._feature_frame = pd.DataFrame(
            [
                {
                    "timestamp": start,
                    "mode_key": "EM FUNCIONAMENTO|CARREGADO",
                    "pv_pres_sistema_bar": 6.8,
                    "sp_pres_sistema_bar": 6.6,
                },
                {
                    "timestamp": start + timedelta(minutes=1),
                    "mode_key": "EM FUNCIONAMENTO|CARREGADO",
                    "pv_pres_sistema_bar": 7.0,
                    "sp_pres_sistema_bar": 6.7,
                },
            ]
        )
        self.service._history_frame = self.service._feature_frame.copy()
        self.service._last_refresh_at = utc_now()

        response = self.service.get_signal_trend_window(
            signal="pv_pres_sistema_bar",
            range_value=2,
            range_unit="points",
            bucket="raw",
        )

        self.assertEqual(response.summary.target_current, 6.7)
        self.assertEqual(response.target_signal, "sp_pres_sistema_bar")
        self.assertEqual(response.lower_limit, 5.0)
        self.assertEqual(response.upper_limit, 7.8)

    def test_catalog_keeps_setpoint_signals_visible(self) -> None:
        start = datetime(2026, 4, 9, 7, 0, 0)
        self.service._feature_frame = pd.DataFrame(
            [
                {
                    "timestamp": start,
                    "mode_key": "EM FUNCIONAMENTO|CARREGADO",
                    "pv_pres_sistema_bar": 6.8,
                    "sp_pres_sistema_bar": 6.6,
                }
            ]
        )
        self.service._history_frame = self.service._feature_frame.copy()
        self.service._last_refresh_at = utc_now()

        response = self.service.get_signal_catalog()
        signal_map = {item.signal: item for item in response.signals}

        self.assertIn("sp_pres_sistema_bar", signal_map)
        self.assertTrue(signal_map["sp_pres_sistema_bar"].is_setpoint)
        self.assertIn("pv_pres_sistema_bar", signal_map)

    def test_multi_signal_trend_returns_all_selected_series(self) -> None:
        start = datetime(2026, 4, 9, 7, 0, 0)
        self.service._feature_frame = pd.DataFrame(
            [
                {
                    "timestamp": start,
                    "mode_key": "EM FUNCIONAMENTO|CARREGADO",
                    "pv_pres_sistema_bar": 6.8,
                    "sp_pres_sistema_bar": 6.6,
                    "pv_temp_oleo_lubrificacao_c": 48.0,
                },
                {
                    "timestamp": start + timedelta(minutes=1),
                    "mode_key": "EM FUNCIONAMENTO|CARREGADO",
                    "pv_pres_sistema_bar": 7.0,
                    "sp_pres_sistema_bar": 6.7,
                    "pv_temp_oleo_lubrificacao_c": 49.2,
                },
            ]
        )
        self.service._history_frame = self.service._feature_frame.copy()
        self.service._last_refresh_at = utc_now()

        response = self.service.get_multi_signal_trend_window(
            signals=["pv_pres_sistema_bar", "pv_temp_oleo_lubrificacao_c"],
            range_value=2,
            range_unit="points",
            bucket="raw",
            max_points=200,
        )

        self.assertEqual(response.signals, ["pv_pres_sistema_bar", "pv_temp_oleo_lubrificacao_c"])
        self.assertEqual(response.correlation_mode, "normalized")
        self.assertEqual(len(response.series), 2)
        self.assertEqual(response.series[0].signal, "pv_pres_sistema_bar")
        self.assertEqual(response.series[1].signal, "pv_temp_oleo_lubrificacao_c")

    def test_status_trends_route_accepts_single_signal(self) -> None:
        start = datetime(2026, 4, 9, 7, 0, 0)
        self.service._feature_frame = pd.DataFrame(
            [
                {
                    "timestamp": start,
                    "mode_key": "EM FUNCIONAMENTO|CARREGADO",
                    "pv_pres_sistema_bar": 6.8,
                    "sp_pres_sistema_bar": 6.6,
                },
                {
                    "timestamp": start + timedelta(minutes=1),
                    "mode_key": "EM FUNCIONAMENTO|CARREGADO",
                    "pv_pres_sistema_bar": 7.0,
                    "sp_pres_sistema_bar": 6.7,
                },
            ]
        )
        self.service._history_frame = self.service._feature_frame.copy()
        self.service._last_refresh_at = utc_now()

        response = get_multi_signal_trend(
            signals=["pv_pres_sistema_bar"],
            range_value=2,
            range_unit="points",
            bucket="raw",
            max_points=200,
            service=self.service,
        )

        self.assertEqual(response.signals, ["pv_pres_sistema_bar"])
        self.assertEqual(len(response.series), 1)
        self.assertEqual(response.series[0].signal, "pv_pres_sistema_bar")

    def test_trend_requests_reuse_cached_feature_frame_without_refresh(self) -> None:
        start = datetime(2026, 4, 9, 7, 0, 0)
        self.service._feature_frame = pd.DataFrame(
            [
                {
                    "timestamp": start,
                    "mode_key": "EM FUNCIONAMENTO|CARREGADO",
                    "pv_pres_sistema_bar": 6.8,
                },
                {
                    "timestamp": start + timedelta(minutes=1),
                    "mode_key": "EM FUNCIONAMENTO|CARREGADO",
                    "pv_pres_sistema_bar": 7.0,
                },
            ]
        )
        self.service._history_frame = self.service._feature_frame.copy()
        self.service.refresh = lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("refresh nao deveria ser chamado")
        )

        response = self.service.get_multi_signal_trend_window(
            signals=["pv_pres_sistema_bar"],
            range_value=2,
            range_unit="points",
            bucket="raw",
            max_points=200,
        )

        self.assertEqual(len(response.series), 1)
        self.assertEqual(response.series[0].count, 2)


if __name__ == "__main__":
    unittest.main()
