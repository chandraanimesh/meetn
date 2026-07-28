from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
import logging

from app.api.dependencies.services import get_readiness_service
from app.application.services.readiness_service import ReadinessService

logger = logging.getLogger("app.api.health")

router = APIRouter(prefix="/health", tags=["health"])

class HealthResponse(BaseModel):
    status: str

@router.get("/live", response_model=HealthResponse)
async def live():
    return {"status": "ok"}

@router.get(
    "/ready",
    response_model=HealthResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthResponse}},
)
async def ready(
    response: Response,
    readiness_service: ReadinessService = Depends(get_readiness_service),
):
    if not await readiness_service.is_ready():
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unavailable"}
    return {"status": "ok"}
