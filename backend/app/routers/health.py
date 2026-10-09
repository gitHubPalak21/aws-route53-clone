from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.schemas.health import HealthResponse, RootResponse

router = APIRouter(tags=["Service"])


@router.get("/", response_model=RootResponse)
def root(settings: Annotated[Settings, Depends(get_settings)]) -> RootResponse:
    return RootResponse(message=settings.app_name)


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness check; does not create tables or contact the database."""
    return HealthResponse()
