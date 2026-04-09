"""Testes basicos do modo demonstracao em CSV."""

from __future__ import annotations

import unittest
from datetime import datetime

from app.config import Settings
from app.services.ingestion_service import IngestionService


class DemoIngestionTests(unittest.TestCase):
    def test_demo_csv_returns_rows(self) -> None:
        settings = Settings(data_source_mode="demo_csv")
        service = IngestionService(settings)

        batch = service.fetch_recent_window(datetime(2030, 1, 1, 0, 0, 0))

        self.assertEqual(batch.source, "demo_csv")
        self.assertGreater(len(batch.frame), 0)
        self.assertIn("timestamp", batch.frame.columns)
        self.assertIn("st_oper", batch.frame.columns)


if __name__ == "__main__":
    unittest.main()
