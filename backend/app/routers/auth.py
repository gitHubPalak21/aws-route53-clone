from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.dependencies.auth import (
    AuthSettings, CurrentSession, CurrentUser, Database,
    clear_session_cookie, require_trusted_origin,
)
from app.schemas.auth import AuthErrorResponse, AuthUserResponse, LoginRequest, LoginResponse, LogoutResponse
from app.services import auth_service

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
unauthorized = {401: {"model": AuthErrorResponse}}


@router.post("/login", response_model=LoginResponse, responses=unauthorized,
             dependencies=[Depends(require_trusted_origin)])
def login(payload: LoginRequest, request: Request, response: Response, db: Database, settings: AuthSettings) -> LoginResponse:
    result = auth_service.login(
        db, settings, payload.email, payload.password.get_secret_value(),
        request.cookies.get(settings.session_cookie_name),
    )
    if result is None:
        raise HTTPException(status_code=401, detail="Invalid email or password", headers={"Cache-Control": "no-store"})
    response.set_cookie(
        settings.session_cookie_name, result.raw_token,
        max_age=settings.session_ttl_hours * 3600, expires=result.expires_at,
        path="/", httponly=True, secure=bool(settings.session_cookie_secure), samesite="lax",
    )
    response.headers["Cache-Control"] = "no-store"
    return LoginResponse(user=AuthUserResponse.model_validate(result.user))


@router.get("/me", response_model=LoginResponse, responses=unauthorized)
def me(response: Response, user: CurrentUser, session: CurrentSession, db: Database) -> LoginResponse:
    auth_service.mark_session_seen(db, session)
    response.headers["Cache-Control"] = "no-store"
    return LoginResponse(user=AuthUserResponse.model_validate(user))


@router.post("/logout", response_model=LogoutResponse, dependencies=[Depends(require_trusted_origin)])
def logout(request: Request, response: Response, db: Database, settings: AuthSettings) -> LogoutResponse:
    auth_service.logout(db, request.cookies.get(settings.session_cookie_name))
    clear_session_cookie(response, settings)
    response.headers["Cache-Control"] = "no-store"
    return LogoutResponse()
