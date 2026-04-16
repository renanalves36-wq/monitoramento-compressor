"""Rotas da analise de influencia da vazao Qn."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from app.domain.analysis_schemas import (
    LossOriginClassification,
    QnInfluenceAnalysisResponse,
    QnInfluenceHistoryResponse,
)
from app.services.health_service import HealthService

router = APIRouter(prefix="/analysis", tags=["analysis"])


def get_health_service(request: Request) -> HealthService:
    return request.app.state.health_service


@router.get("/qn-influence/current", response_model=QnInfluenceAnalysisResponse)
def get_qn_influence_current(
    range_value: int = Query(default=24, ge=1, le=5000),
    range_unit: str = Query(default="hours", pattern="^(points|minutes|hours|days)$"),
    service: HealthService = Depends(get_health_service),
) -> QnInfluenceAnalysisResponse:
    return service.get_qn_influence_current(
        range_value=range_value,
        range_unit=range_unit,
    )


@router.get("/qn-influence/history", response_model=QnInfluenceHistoryResponse)
def get_qn_influence_history(
    range_value: int = Query(default=24, ge=1, le=5000),
    range_unit: str = Query(default="hours", pattern="^(points|minutes|hours|days)$"),
    max_points: int = Query(default=240, ge=30, le=1000),
    service: HealthService = Depends(get_health_service),
) -> QnInfluenceHistoryResponse:
    return service.get_qn_influence_history(
        range_value=range_value,
        range_unit=range_unit,
        max_points=max_points,
    )


@router.get("/qn-loss-origin/current", response_model=LossOriginClassification)
def get_qn_loss_origin_current(
    range_value: int = Query(default=24, ge=1, le=5000),
    range_unit: str = Query(default="hours", pattern="^(points|minutes|hours|days)$"),
    service: HealthService = Depends(get_health_service),
) -> LossOriginClassification:
    return service.get_qn_loss_origin_current(
        range_value=range_value,
        range_unit=range_unit,
    )
