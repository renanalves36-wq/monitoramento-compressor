"""Camada opcional de enriquecimento com Gemini para insights operacionais."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from app.config import Settings
from app.domain.schemas import LlmInsight, LlmInsightHypothesis
from app.utils.logger import get_logger


class _GeminiInsightPayload(BaseModel):
    summary: str
    insights: list[str] = Field(default_factory=list)
    observations: list[str] = Field(default_factory=list)
    false_positive_risk: str = "medium"
    confidence: float = 0.0
    hypotheses: list[dict[str, Any]] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)


class GeminiInsightService:
    """Gera leitura profissional sobre alertas, quando habilitado."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.logger = get_logger(__name__)

    def enabled(self) -> bool:
        return bool(self.settings.gemini_enabled and self.settings.gemini_api_key)

    def generate_predictive_insight(
        self,
        *,
        signal: str,
        alert_title: str,
        alert_message: str,
        snapshot: dict[str, Any],
        evidence: dict[str, Any],
        prescriptive_diagnosis: dict[str, Any] | None,
    ) -> LlmInsight | None:
        return self.generate_alert_insight(
            layer="predictive_statistics",
            signal=signal,
            alert_title=alert_title,
            alert_message=alert_message,
            snapshot=snapshot,
            evidence=evidence,
            prescriptive_diagnosis=prescriptive_diagnosis,
            predictive_diagnosis=evidence,
        )

    def generate_alert_insight(
        self,
        *,
        layer: str,
        signal: str,
        alert_title: str,
        alert_message: str,
        snapshot: dict[str, Any],
        evidence: dict[str, Any],
        prescriptive_diagnosis: dict[str, Any] | None = None,
        predictive_diagnosis: dict[str, Any] | None = None,
    ) -> LlmInsight | None:
        if not self.enabled():
            return None

        try:
            payload = self._call_gemini(
                layer=layer,
                signal=signal,
                alert_title=alert_title,
                alert_message=alert_message,
                snapshot=snapshot,
                evidence=evidence,
                prescriptive_diagnosis=prescriptive_diagnosis,
                predictive_diagnosis=predictive_diagnosis,
            )
        except Exception as exc:  # pragma: no cover - falha externa
            self.logger.warning(
                "gemini_alert_insight_failed",
                extra={"signal": signal, "layer": layer, "error": str(exc)},
            )
            return None

        return LlmInsight(
            provider="gemini",
            model=self.settings.gemini_model,
            confidence=float(payload.confidence),
            summary=payload.summary,
            insights=payload.insights,
            observacoes=payload.observations,
            false_positive_risk=payload.false_positive_risk,
            hipoteses=[
                LlmInsightHypothesis(
                    causa=str(item.get("causa", "")),
                    confianca=float(item.get("confianca", 0.0)),
                    racional=None if not item.get("racional") else str(item.get("racional")),
                )
                for item in payload.hypotheses
                if item.get("causa")
            ],
            acoes_recomendadas=payload.recommended_actions,
        )

    def _call_gemini(
        self,
        *,
        layer: str,
        signal: str,
        alert_title: str,
        alert_message: str,
        snapshot: dict[str, Any],
        evidence: dict[str, Any],
        prescriptive_diagnosis: dict[str, Any] | None,
        predictive_diagnosis: dict[str, Any] | None,
    ) -> _GeminiInsightPayload:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self.settings.gemini_api_key)
        prompt = self._build_prompt(
            layer=layer,
            signal=signal,
            alert_title=alert_title,
            alert_message=alert_message,
            snapshot=snapshot,
            evidence=evidence,
            prescriptive_diagnosis=prescriptive_diagnosis,
            predictive_diagnosis=predictive_diagnosis,
        )
        response = client.models.generate_content(
            model=self.settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=self.settings.gemini_temperature,
                max_output_tokens=self.settings.gemini_max_output_tokens,
                response_mime_type="application/json",
                response_schema=_GeminiInsightPayload,
            ),
        )
        parsed = getattr(response, "parsed", None)
        if parsed is not None:
            return parsed
        text = getattr(response, "text", "") or "{}"
        return _GeminiInsightPayload.model_validate(json.loads(text))

    @staticmethod
    def _build_prompt(
        *,
        layer: str,
        signal: str,
        alert_title: str,
        alert_message: str,
        snapshot: dict[str, Any],
        evidence: dict[str, Any],
        prescriptive_diagnosis: dict[str, Any] | None,
        predictive_diagnosis: dict[str, Any] | None,
    ) -> str:
        return f"""
Voce e um analista industrial de confiabilidade.
Trabalhe com linguagem profissional, objetiva e operacional.
Nao afirme causa confirmada. Rankeie hipoteses e destaque risco de falso positivo.
Traduza termos estatisticos para linguagem simples e util para operacao.

Contexto do alerta:
- camada do alerta: {layer}
- sinal principal: {signal}
- titulo: {alert_title}
- mensagem: {alert_message}

Evidencias disponiveis:
{json.dumps(evidence, ensure_ascii=False, indent=2)}

Snapshot resumido:
{json.dumps(snapshot, ensure_ascii=False, indent=2)}

Diagnostico preditivo atual:
{json.dumps(predictive_diagnosis or {}, ensure_ascii=False, indent=2)}

Prescricao deterministica atual:
{json.dumps(prescriptive_diagnosis or {}, ensure_ascii=False, indent=2)}

Retorne JSON estruturado com:
- summary: resumo executivo em 1 ou 2 frases
- insights: lista curta de insights operacionais
- observations: lista curta de observacoes e cautelas
- false_positive_risk: low, medium ou high
- confidence: numero entre 0 e 1
- hypotheses: lista com causa, confianca e racional
- recommended_actions: lista curta e priorizada

Se a evidencia for fraca, reduza a confianca e explicite a cautela.
Se o alerta for estatistico, explique em palavras simples se isso parece:
- tendencia anormal sustentada
- comportamento fora do normal recente
- apenas oscilacao que pede observacao
""".strip()
