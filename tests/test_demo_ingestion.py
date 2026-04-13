"""Testes basicos do modo demonstracao em CSV."""

from __future__ import annotations

import unittest
from datetime import datetime

import pandas as pd

from app.config import Settings
from app.services.ingestion_service import IngestionService


class DemoIngestionTests(unittest.TestCase):
    def test_demo_csv_returns_rows(self) -> None:
        settings = Settings(
            data_source_mode="demo_csv",
            demo_csv_chunk_size=10,
            demo_csv_bootstrap_rows=25,
            demo_csv_full_bootstrap=True,
        )
        service = IngestionService(settings)

        batch = service.fetch_recent_window(datetime(2030, 1, 1, 0, 0, 0))

        self.assertEqual(batch.source, "demo_csv")
        self.assertGreater(len(batch.frame), 0)
        self.assertGreater(len(batch.frame), settings.demo_csv_bootstrap_rows)
        self.assertIn("timestamp", batch.frame.columns)
        self.assertIn("st_oper", batch.frame.columns)

    def test_stuck_sensor_quality_issue_requires_longer_time_window(self) -> None:
        settings = Settings(
            data_source_mode="demo_csv",
            sensor_stuck_min_points=45,
            sensor_stuck_min_duration_minutes=45,
        )
        service = IngestionService(settings)
        frame = pd.DataFrame(
            {
                "timestamp": pd.date_range("2026-04-09 08:00:00", periods=20, freq="min"),
                "pv_corr_motor_a": [181.0] * 20,
            }
        )

        short_issues = service._collect_stuck_sensor_issues(frame)
        self.assertFalse(any(issue.signal == "pv_corr_motor_a" for issue in short_issues))

        long_frame = pd.DataFrame(
            {
                "timestamp": pd.date_range("2026-04-09 08:00:00", periods=50, freq="min"),
                "pv_corr_motor_a": [181.0] * 50,
            }
        )
        long_issues = service._collect_stuck_sensor_issues(long_frame)
        issue = next(issue for issue in long_issues if issue.signal == "pv_corr_motor_a")
        self.assertGreaterEqual(float(issue.details["window_minutes"]), 45.0)


if __name__ == "__main__":
    unittest.main()
