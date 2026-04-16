"""Schemas da analise de influencia da vazao Qn."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AnalysisQualityFlag(BaseModel):
    code: str
    severity: str = "info"
    message: str
    signal: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class AnalysisDataWindow(BaseModel):
    start_timestamp: datetime | None = None
    end_timestamp: datetime | None = None
    raw_rows: int = 0
    valid_rows: int = 0
    normal_operation_rows: int = 0
    excluded_transition_rows: int = 0


class InfluenceItem(BaseModel):
    variavel: str
    label: str
    unidade: str | None = None
    subsistema: str
    influencia: float
    sinal: str
    tipo: str
    coeficiente: float | None = None
    coeficiente_padronizado: float | None = None
    interpretacao_curta: str


class ModelQuality(BaseModel):
    target: str
    r2: float | None = None
    erro_medio_abs: float | None = None
    pontos_validos: int = 0
    features_usadas: list[str] = Field(default_factory=list)
    features_removidas: list[str] = Field(default_factory=list)
    observacoes: list[str] = Field(default_factory=list)


class LossOriginClassification(BaseModel):
    classificacao: str
    confianca: float
    explicacao_curta: str
    variaveis_dominantes: list[str] = Field(default_factory=list)
    recomendacao_analitica: str


class QnInfluenceAnalysisResponse(BaseModel):
    generated_at: datetime
    range_value: int
    range_unit: str
    data_window: AnalysisDataWindow
    contexto_operacional: dict[str, Any] = Field(default_factory=dict)
    qn_atual: float | None = None
    qn_esperada: float | None = None
    delta_q: float | None = None
    delta_q_percentual: float | None = None
    influencia_direta: list[InfluenceItem] = Field(default_factory=list)
    influencia_indireta: list[InfluenceItem] = Field(default_factory=list)
    qualidade_modelo_direto: ModelQuality
    qualidade_modelo_desvio: ModelQuality
    classificacao_origem: LossOriginClassification
    resumo_textual: str
    qualidade_dados: list[AnalysisQualityFlag] = Field(default_factory=list)


class QnInfluenceHistoryPoint(BaseModel):
    timestamp: datetime
    qn_real: float | None = None
    qn_esperada: float | None = None
    delta_q: float | None = None
    delta_q_percentual: float | None = None


class QnInfluenceHistoryResponse(BaseModel):
    generated_at: datetime
    range_value: int
    range_unit: str
    analysis: QnInfluenceAnalysisResponse
    points: list[QnInfluenceHistoryPoint] = Field(default_factory=list)
