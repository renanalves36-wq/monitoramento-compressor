"""Rotas relacionadas a status, leituras e score."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from app.domain.schemas import (
    AiStatusResponse,
    FlowEstimateResponse,
    MultiSignalTrendResponse,
    ReadingsResponse,
    RiskScoresResponse,
    SignalCatalogResponse,
    SignalTrendResponse,
    SnapshotResponse,
    StatusResponse,
)
from app.services.health_service import HealthService

router = APIRouter(prefix="/status", tags=["status"])


def get_health_service(request: Request) -> HealthService:
    return request.app.state.health_service


@router.get("/current", response_model=SnapshotResponse)
def get_current_status(
    service: HealthService = Depends(get_health_service),
) -> SnapshotResponse:
    return service.get_latest_snapshot()


@router.get("/flow", response_model=FlowEstimateResponse)
def get_flow_estimate(
    service: HealthService = Depends(get_health_service),
) -> FlowEstimateResponse:
    return service.get_flow_estimate()


@router.get("/readings", response_model=ReadingsResponse)
def get_latest_readings(
    limit: int = Query(default=20, ge=1, le=500),
    service: HealthService = Depends(get_health_service),
) -> ReadingsResponse:
    return service.get_latest_readings(limit=limit)


@router.get("/scores", response_model=RiskScoresResponse)
def get_risk_scores(
    service: HealthService = Depends(get_health_service),
) -> RiskScoresResponse:
    return service.get_risk_scores()


@router.get("/ai", response_model=AiStatusResponse)
def get_ai_status(
    service: HealthService = Depends(get_health_service),
) -> AiStatusResponse:
    return service.get_ai_status()


@router.post("/ai/refresh", response_model=AiStatusResponse)
def refresh_ai_insights(
    service: HealthService = Depends(get_health_service),
) -> AiStatusResponse:
    return service.force_ai_refresh()


@router.get("/ai/refresh", response_model=AiStatusResponse)
def refresh_ai_insights_from_browser(
    service: HealthService = Depends(get_health_service),
) -> AiStatusResponse:
    return service.force_ai_refresh()


@router.get("/catalog", response_model=SignalCatalogResponse)
def get_signal_catalog(
    service: HealthService = Depends(get_health_service),
) -> SignalCatalogResponse:
    return service.get_signal_catalog()


@router.get("/trend", response_model=SignalTrendResponse)
def get_signal_trend(
    signal: str = Query(..., min_length=3),
    range_value: int = Query(default=6, ge=1, le=5000),
    range_unit: str = Query(default="hours", pattern="^(points|minutes|hours|days)$"),
    bucket: str = Query(default="raw", pattern="^(raw|minutes|hours|days)$"),
    max_points: int = Query(default=600, ge=60, le=4000),
    service: HealthService = Depends(get_health_service),
) -> SignalTrendResponse:
    return service.get_signal_trend_window(
        signal=signal,
        range_value=range_value,
        range_unit=range_unit,
        bucket=bucket,
        max_points=max_points,
    )


@router.get("/trends", response_model=MultiSignalTrendResponse)
def get_multi_signal_trend(
    signals: list[str] = Query(...),
    range_value: int = Query(default=6, ge=1, le=5000),
    range_unit: str = Query(default="hours", pattern="^(points|minutes|hours|days)$"),
    bucket: str = Query(default="raw", pattern="^(raw|minutes|hours|days)$"),
    max_points: int = Query(default=600, ge=60, le=4000),
    service: HealthService = Depends(get_health_service),
) -> MultiSignalTrendResponse:
    return service.get_multi_signal_trend_window(
        signals=signals,
        range_value=range_value,
        range_unit=range_unit,
        bucket=bucket,
        max_points=max_points,
    )


@router.get("", response_model=StatusResponse)
def get_service_status(
    service: HealthService = Depends(get_health_service),
) -> StatusResponse:
    return service.get_service_status()
