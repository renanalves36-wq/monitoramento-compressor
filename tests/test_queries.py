"""Testes de sanidade das queries SQL."""

from __future__ import annotations

import unittest

from app.db.queries import build_incremental_query


class QueryTests(unittest.TestCase):
    def test_incremental_query_uses_explicit_select(self) -> None:
        query = build_incremental_query()
        self.assertNotIn("SELECT *", query.upper())
        self.assertIn("[012CPA0008_PV_POSIÇÃO_ALIVIO%] AS pv_pos_alivio_pct", query)
        self.assertIn("WHERE [TimeStamp] > ?", query)


if __name__ == "__main__":
    unittest.main()
