from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyCookie

from app.core.config import get_settings
from app.routers.auth import router as auth_router
from app.routers.health import router as health_router
from app.routers.hosted_zones import router as hosted_zones_router
from app.routers.dns_records import router as dns_records_router


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        description="Session-authenticated hosted-zone and DNS-record management for an AWS Route 53 workflow clone. No real DNS hosting or AWS provisioning.",
        version="0.1.0",
        openapi_tags=[{"name": "Hosted Zones", "description": (
            "Owner-scoped hosted zone management. Sign in through /api/auth/login first; "
            "same-origin Swagger requests use the HttpOnly session cookie. This mock API does not provision AWS or DNS."
        )}, {"name": "DNS Records", "description": (
            "Owner-scoped mock DNS storage with type validation, SQL search/filter/sort/pagination, "
            "and read-only system NS/SOA. No actual DNS infrastructure is provisioned."
        )}],
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[str(settings.frontend_origin).rstrip("/")],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Accept", "Content-Type", "Authorization"],
    )
    application.include_router(health_router)
    application.include_router(auth_router)
    # Document the configured cookie scheme. CurrentUser remains responsible for
    # authenticating its stored hash, expiry and user status on every operation.
    cookie_docs = Depends(APIKeyCookie(
        name=settings.session_cookie_name, scheme_name="SessionCookie", auto_error=False,
        description="HttpOnly cookie established by POST /api/auth/login; log in before trying these endpoints",
    ))
    application.include_router(hosted_zones_router, dependencies=[cookie_docs])
    application.include_router(dns_records_router, dependencies=[cookie_docs])

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Validation must not echo submitted passwords into an error response.
        errors = [{key: error[key] for key in ("type", "loc", "msg")} for error in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": errors}, headers={"Cache-Control": "no-store"})

    return application


app = create_app()
