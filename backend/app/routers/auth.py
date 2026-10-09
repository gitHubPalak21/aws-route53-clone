from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.dependencies.auth import (
    AuthSettings, CurrentSession, CurrentUser, Database,
    clear_session_cookie, require_trusted_origin,
)
from app.schemas.auth import AuthErrorResponse, AuthUserResponse, LoginRequest, LoginResponse, LogoutResponse, RegisterRequest
from app.services import auth_service

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
unauthorized = {401: {"model": AuthErrorResponse}}


def authenticated_response(response: Response, settings: AuthSettings, result: auth_service.LoginResult) -> LoginResponse:
    response.set_cookie(
        settings.session_cookie_name, result.raw_token,
        max_age=settings.session_ttl_hours * 3600, expires=result.expires_at,
        path="/", httponly=True, secure=bool(settings.session_cookie_secure), samesite="lax",
    )
    response.headers["Cache-Control"] = "no-store"
    return LoginResponse(user=AuthUserResponse.model_validate(result.user))


@router.post("/register", status_code=201, response_model=LoginResponse,
             summary="Create an account and sign in", responses={409: {"model": AuthErrorResponse}},
             dependencies=[Depends(require_trusted_origin)])
def register(payload: RegisterRequest, request: Request, response: Response, db: Database, settings: AuthSettings) -> LoginResponse:
    try:
        result = auth_service.register(
            db, settings, payload.display_name, payload.email, payload.password.get_secret_value(),
            request.cookies.get(settings.session_cookie_name),
        )
    except auth_service.EmailAlreadyExists:
        raise HTTPException(status_code=409, detail="An account with this email already exists.",
                            headers={"Cache-Control": "no-store"}) from None
    return authenticated_response(response, settings, result)


@router.post("/login", response_model=LoginResponse, responses=unauthorized,
             dependencies=[Depends(require_trusted_origin)])
def login(payload: LoginRequest, request: Request, response: Response, db: Database, settings: AuthSettings) -> LoginResponse:
    result = auth_service.login(
        db, settings, payload.email, payload.password.get_secret_value(),
        request.cookies.get(settings.session_cookie_name),
    )
    if result is None:
        raise HTTPException(status_code=401, detail="Invalid email or password", headers={"Cache-Control": "no-store"})
    return authenticated_response(response, settings, result)


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
