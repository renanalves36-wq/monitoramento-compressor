"""Entrada principal da API FastAPI."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes_analysis import router as analysis_router
from app.api.routes_alerts import router as alerts_router
from app.api.routes_dashboard import router as dashboard_router
from app.api.routes_status import router as status_router
from app.config import get_settings
from app.services.health_service import HealthService
from app.storage.alert_repository import AlertRepository
from app.utils.logger import configure_logging, get_logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    logger = get_logger(__name__)

    repository = AlertRepository(settings.sqlite_path)
    repository.initialize()

    health_service = HealthService(settings=settings, repository=repository)
    app.state.health_service = health_service
    health_service.refresh(force=True)

    logger.info(
        "application_started",
        extra={"app_name": settings.app_name, "environment": settings.environment},
    )
    yield


app = FastAPI(
    title="TA6000 Monitoring API",
    version="0.1.0",
    lifespan=lifespan,
    description=(
        "Monitoramento inteligente, alerta antecipado e base para predicao "
        "assistida por IA do compressor industrial TA6000."
    ),
)

STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

app.include_router(status_router)
app.include_router(alerts_router)
app.include_router(analysis_router)
app.include_router(dashboard_router)
