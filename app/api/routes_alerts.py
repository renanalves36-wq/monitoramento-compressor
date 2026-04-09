"""Rotas de alertas."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

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
