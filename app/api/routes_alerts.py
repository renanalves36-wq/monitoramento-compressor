"""Rotas de alertas."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from app.domain.schemas import AlertsResponse
from app.services.health_service import HealthService

router = APIRouter(prefix="/alerts", tags=["alerts"])


def get_health_service(request: Request) -> HealthService:
    return request.app.state.health_service


@router.get("", response_model=AlertsResponse)
def list_active_alerts(
    service: HealthService = Depends(get_health_service),
) -> AlertsResponse:
    return service.get_active_alerts()


@router.get("/recent", response_model=AlertsResponse)
def list_recent_alerts(
    limit: int = Query(default=200, ge=1, le=5000),
    subsystem: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    service: HealthService = Depends(get_health_service),
) -> AlertsResponse:
    return service.get_recent_alerts(limit=limit, subsystem=subsystem, severity=severity)
