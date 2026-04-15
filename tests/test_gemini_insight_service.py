"""Testes da camada de parsing dos insights do Gemini."""

from __future__ import annotations

import unittest

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
        self.assertTrue(payload.recommended_actions)
        self.assertIn("fora do formato JSON", payload.observations[0])


if __name__ == "__main__":
    unittest.main()
