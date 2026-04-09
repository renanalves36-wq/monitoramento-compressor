"""Rotas relacionadas a status, leituras e score."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from app.domain.schemas import (
    ReadingsResponse,
    RiskScoresResponse,
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


@router.get("", response_model=StatusResponse)
def get_service_status(
    service: HealthService = Depends(get_health_service),
) -> StatusResponse:
    return service.get_service_status()
