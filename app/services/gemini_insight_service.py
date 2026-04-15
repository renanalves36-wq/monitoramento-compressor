"""Camada opcional de enriquecimento com Gemini para insights operacionais."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
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
    hypotheses: list[LlmInsightHypothesis] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)


class GeminiInsightService:
    """Gera leitura profissional sobre alertas, quando habilitado."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.logger = get_logger(__name__)
        self.attempts = 0
        self.successes = 0
        self.failures = 0
        self.cache_hits = 0
        self.last_attempt_at: datetime | None = None
        self.last_success_at: datetime | None = None
        self.last_error: str | None = None
        self.last_signal: str | None = None
        self.last_layer: str | None = None
        self._insight_cache: dict[str, LlmInsight] = {}

    def enabled(self) -> bool:
        return bool(self.settings.gemini_enabled and self.settings.gemini_api_key)

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled(),
            "has_api_key": bool(self.settings.gemini_api_key),
            "model": self.settings.gemini_model,
            "attempts": self.attempts,
            "successes": self.successes,
            "failures": self.failures,
            "cache_hits": self.cache_hits,
            "cached_insights": len(self._insight_cache),
            "last_attempt_at": self.last_attempt_at,
            "last_success_at": self.last_success_at,
            "last_error": self.last_error,
            "last_signal": self.last_signal,
            "last_layer": self.last_layer,
        }

    def generate_predictive_insight(
        self,
        *,
        signal: str,
        alert_title: str,
        alert_message: str,
        snapshot: dict[str, Any],
        evidence: dict[str, Any],
        prescriptive_diagnosis: dict[str, Any] | None,
        cache_key: str | None = None,
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
            cache_key=cache_key,
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
        cache_key: str | None = None,
    ) -> LlmInsight | None:
        if not self.enabled():
            return None
        if cache_key and cache_key in self._insight_cache:
            self.cache_hits += 1
            return self._insight_cache[cache_key].model_copy(deep=True)

        self.attempts += 1
        self.last_attempt_at = datetime.now(timezone.utc)
        self.last_signal = signal
        self.last_layer = layer
        self.last_error = None

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
            self.failures += 1
            self.last_error = str(exc)
            self.logger.warning(
                "gemini_alert_insight_failed",
                extra={"signal": signal, "layer": layer, "error": str(exc)},
            )
            return None

        self.successes += 1
        self.last_success_at = datetime.now(timezone.utc)

        insight = LlmInsight(
            provider="gemini",
            model=self.settings.gemini_model,
            confidence=float(payload.confidence),
            summary=payload.summary,
            insights=payload.insights,
            observacoes=payload.observations,
            false_positive_risk=payload.false_positive_risk,
            hipoteses=[
                LlmInsightHypothesis(
                    causa=item.causa,
                    confianca=float(item.confianca),
                    racional=item.racional,
                )
                for item in payload.hypotheses
                if item.causa
            ],
            acoes_recomendadas=payload.recommended_actions,
        )
        if cache_key:
            self._insight_cache[cache_key] = insight.model_copy(deep=True)
        return insight

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
            ),
        )
        parsed = getattr(response, "parsed", None)
        if parsed is not None:
            return _GeminiInsightPayload.model_validate(parsed)
        text = getattr(response, "text", "") or ""
        return self._parse_payload_from_text(text)

    @classmethod
    def _parse_payload_from_text(cls, text: str) -> _GeminiInsightPayload:
        cleaned = cls._strip_json_fence(text)
        candidates = [cleaned, cls._extract_json_object(cleaned)]

        for candidate in candidates:
            if not candidate:
                continue
            try:
                return _GeminiInsightPayload.model_validate(json.loads(candidate))
            except (TypeError, ValueError, json.JSONDecodeError):
                continue

        recovered = cls._recover_payload_from_malformed_json(cleaned)
        if recovered is not None:
            return recovered

        return cls._fallback_payload_from_text(text)

    @staticmethod
    def _strip_json_fence(text: str) -> str:
        cleaned = (text or "").strip()
        if not cleaned.startswith("```"):
            return cleaned

        lines = cleaned.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()

    @staticmethod
    def _extract_json_object(text: str) -> str | None:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return None
        return text[start : end + 1]

    @classmethod
    def _recover_payload_from_malformed_json(cls, text: str) -> _GeminiInsightPayload | None:
        summary = cls._extract_string_field(text, "summary")
        insights = cls._extract_string_array(text, "insights")
        observations = cls._extract_string_array(text, "observations")
        actions = cls._extract_string_array(text, "recommended_actions")
        false_positive_risk = cls._extract_choice_field(
            text,
            "false_positive_risk",
            allowed={"low", "medium", "high"},
            default="medium",
        )
        confidence = cls._extract_number_field(text, "confidence")

        if not summary and not insights and not observations and not actions:
            return None

        return _GeminiInsightPayload(
            summary=summary or (insights[0] if insights else "A IA retornou uma leitura parcial."),
            insights=cls._unique_texts(insights),
            observations=cls._unique_texts(
                [
                    *observations,
                    "A resposta da IA veio parcialmente fora do formato esperado; o sistema recuperou os trechos uteis.",
                ]
            ),
            false_positive_risk=false_positive_risk,
            confidence=0.45 if confidence is None else max(0.0, min(1.0, confidence)),
            hypotheses=[],
            recommended_actions=cls._unique_texts(actions),
        )

    @classmethod
    def _extract_string_field(cls, text: str, field: str) -> str | None:
        match = re.search(rf'"{re.escape(field)}"\s*:\s*"', text)
        if not match:
            return None

        value_chars: list[str] = []
        escaped = False
        for char in text[match.end() :]:
            if escaped:
                value_chars.append(char)
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == '"':
                break
            value_chars.append(char)

        return cls._clean_ai_text("".join(value_chars))

    @classmethod
    def _extract_string_array(cls, text: str, field: str) -> list[str]:
        match = re.search(rf'"{re.escape(field)}"\s*:\s*\[', text)
        if not match:
            return []

        start = match.end()
        end = text.find("]", start)
        segment = text[start:] if end < 0 else text[start:end]
        values = [
            cls._clean_ai_text(raw)
            for raw in re.findall(r'"((?:\\.|[^"\\])*)"', segment)
        ]
        return [value for value in values if value]

    @staticmethod
    def _extract_number_field(text: str, field: str) -> float | None:
        match = re.search(rf'"{re.escape(field)}"\s*:\s*([0-9]+(?:\.[0-9]+)?)', text)
        if not match:
            return None
        try:
            return float(match.group(1))
        except ValueError:
            return None

    @staticmethod
    def _extract_choice_field(
        text: str,
        field: str,
        *,
        allowed: set[str],
        default: str,
    ) -> str:
        match = re.search(rf'"{re.escape(field)}"\s*:\s*"([^"]+)"', text)
        if not match:
            return default
        value = match.group(1).strip().lower()
        return value if value in allowed else default

    @staticmethod
    def _clean_ai_text(text: str | None) -> str | None:
        if not text:
            return None
        cleaned = text.replace("\\n", " ").replace("\n", " ")
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,")
        if not cleaned:
            return None
        if len(cleaned) > 700:
            cleaned = f"{cleaned[:700]}..."
        return cleaned

    @staticmethod
    def _unique_texts(items: list[str | None]) -> list[str]:
        unique: list[str] = []
        seen: set[str] = set()
        for item in items:
            text = (item or "").strip()
            if not text:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            unique.append(text)
        return unique

    @staticmethod
    def _fallback_payload_from_text(text: str) -> _GeminiInsightPayload:
        cleaned = " ".join((text or "").split())
        if len(cleaned) > 900:
            cleaned = f"{cleaned[:900]}..."

        summary = cleaned or "A IA respondeu, mas nao retornou um texto aproveitavel."
        return _GeminiInsightPayload(
            summary=summary,
            insights=[],
            observations=[
                "A resposta da IA veio fora do formato JSON esperado; o sistema exibiu a leitura em modo texto seguro.",
            ],
            false_positive_risk="medium",
            confidence=0.35,
            hypotheses=[],
            recommended_actions=[
                "Validar este alerta junto das regras, tendencias e prescricao deterministica do sistema.",
            ],
        )

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
Responda somente com JSON valido, sem markdown, sem comentarios antes ou depois.
Nao use quebra de linha dentro de strings; use frases curtas.

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

Formato obrigatorio:
{{
  "summary": "resumo executivo em 1 ou 2 frases",
  "insights": ["insight operacional curto"],
  "observations": ["cautela ou observacao curta"],
  "false_positive_risk": "low|medium|high",
  "confidence": 0.0,
  "hypotheses": [
    {{"causa": "hipotese sem afirmar causa confirmada", "confianca": 0.0, "racional": "evidencia usada"}}
  ],
  "recommended_actions": ["acao priorizada curta"]
}}

Se a evidencia for fraca, reduza a confianca e explicite a cautela.
Se o alerta for estatistico, explique em palavras simples se isso parece:
- tendencia anormal sustentada
- comportamento fora do normal recente
- apenas oscilacao que pede observacao
""".strip()
