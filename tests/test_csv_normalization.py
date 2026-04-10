"""Testes de normalizacao do CSV demo/exportado."""

from __future__ import annotations

import unittest

import pandas as pd

from app.config import Settings
from app.services.ingestion_service import IngestionService


class CsvNormalizationTests(unittest.TestCase):
    def test_standardize_demo_chunk_accepts_export_columns(self) -> None:
        _ = IngestionService(Settings())
        raw_chunk = pd.DataFrame(
            {
                "TimeStamp": ["09/04/2026 16:30:51"],
                "dsTurno": ["B"],
                "Status": ["0"],
                "st_plc": ["True"],
                "pv_pres_sistema_bar": ["7,15"],
            }
        )

        normalized = IngestionService._standardize_demo_chunk(raw_chunk)

        self.assertIn("timestamp", normalized.columns)
        self.assertIn("ds_turno", normalized.columns)
        self.assertIn("status", normalized.columns)
        self.assertTrue(pd.notna(normalized.loc[0, "timestamp"]))

    def test_parse_demo_timestamps_accepts_multiple_formats(self) -> None:
        values = pd.Series(
            [
                "09/04/2026 16:30:51",
                "2026-04-09 16:30:51",
                "04/09/2026 16:30:51",
            ]
        )

        parsed = IngestionService._parse_demo_timestamps(values)

        self.assertTrue(parsed.notna().all())


if __name__ == "__main__":
    unittest.main()
