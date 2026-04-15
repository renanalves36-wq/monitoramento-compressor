"""Testes da camada de parsing dos insights do Gemini."""

from __future__ import annotations

import unittest

from app.config import Settings
from app.domain.schemas import LlmInsight
from app.services.gemini_insight_service import _GeminiInsightPayload
from app.services.gemini_insight_service import GeminiInsightService


class GeminiInsightParsingTest(unittest.TestCase):
    def test_parse_json_inside_markdown_fence(self) -> None:
        payload = GeminiInsightService._parse_payload_from_text(
            """```json
{
  "summary": "Vibracao subindo de forma sustentada.",
  "insights": ["A tendencia merece acompanhamento."],
  "observations": ["Nao confirmar causa sem inspecao."],
  "false_positive_risk": "medium",
  "confidence": 0.62,
  "hypotheses": [
    {"causa": "inicio_de_desbalanceamento", "confianca": 0.55, "racional": "slope positivo"}
  ],
  "recommended_actions": ["Comparar vibracao entre estagios."]
}
```"""
        )

        self.assertEqual(payload.summary, "Vibracao subindo de forma sustentada.")
        self.assertEqual(payload.hypotheses[0].causa, "inicio_de_desbalanceamento")
        self.assertEqual(payload.recommended_actions[0], "Comparar vibracao entre estagios.")

    def test_malformed_response_becomes_safe_fallback_payload(self) -> None:
        payload = GeminiInsightService._parse_payload_from_text(
            '{"summary": "Analise iniciada",\n "insights": ["texto sem fechar'
        )

        self.assertIn("Analise iniciada", payload.summary)
        self.assertEqual(payload.false_positive_risk, "medium")
        self.assertLess(payload.confidence, 0.5)
        self.assertIn("parcialmente fora do formato", payload.observations[0])

    def test_partial_json_response_recovers_summary_without_raw_json(self) -> None:
        payload = GeminiInsightService._parse_payload_from_text(
            '{"summary": "Corrente do motor acima do normal, mas sem confirmacao de causa",\n'
            '"insights": ["Comparar corrente com pressao de descarga"],\n'
            '"confidence": 0.61'
        )

        self.assertEqual(
            payload.summary,
            "Corrente do motor acima do normal, mas sem confirmacao de causa.",
        )
        self.assertEqual(payload.insights, ["Comparar corrente com pressao de descarga"])
        self.assertEqual(payload.confidence, 0.61)
        self.assertNotIn("{", payload.summary)

    def test_cache_key_reuses_existing_insight_without_new_attempt(self) -> None:
        class FakeGeminiInsightService(GeminiInsightService):
            def _call_gemini(self, **_kwargs) -> _GeminiInsightPayload:  # type: ignore[override]
                return _GeminiInsightPayload(
                    summary="Leitura cacheavel.",
                    confidence=0.7,
                    recommended_actions=["Acompanhar tendencia."],
                )

        service = FakeGeminiInsightService(
            Settings(gemini_enabled=True, gemini_api_key="fake-key")
        )

        first = service.generate_alert_insight(
            layer="fixed_rule",
            signal="pv_corr_motor_a",
            alert_title="Corrente alta",
            alert_message="Corrente acima do limite.",
            snapshot={},
            evidence={},
            cache_key="same-alert",
        )
        second = service.generate_alert_insight(
            layer="fixed_rule",
            signal="pv_corr_motor_a",
            alert_title="Corrente alta",
            alert_message="Corrente acima do limite.",
            snapshot={},
            evidence={},
            cache_key="same-alert",
        )

        self.assertIsInstance(first, LlmInsight)
        self.assertIsInstance(second, LlmInsight)
        self.assertEqual(service.attempts, 1)
        self.assertEqual(service.successes, 1)
        self.assertEqual(service.cache_hits, 1)
        self.assertEqual(first.summary, second.summary)


if __name__ == "__main__":
    unittest.main()
