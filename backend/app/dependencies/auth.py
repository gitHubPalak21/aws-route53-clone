from typing import Annotated

from fastapi import Depends, HTTPException, Request, Response

from sqlalchemy.orm import Session as DBSession

from app.core.config import Settings, get_settings
from app.dependencies.database import get_db
from app.models import Session, User
from app.services.auth_service import resolve_session

Database = Annotated[DBSession, Depends(get_db)]
AuthSettings = Annotated[Settings, Depends(get_settings)]


def clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        settings.session_cookie_name, path="/", httponly=True,
        secure=bool(settings.session_cookie_secure), samesite="lax",
    )


def get_current_session(request: Request, db: Database, settings: AuthSettings) -> Session:
    session = resolve_session(db, request.cookies.get(settings.session_cookie_name))
    if session is None:
        # HTTPException creates a new response, so include cookie removal in its headers.
        response = Response()
        clear_session_cookie(response, settings)
        raise HTTPException(
            status_code=401, detail="Not authenticated",
            headers={"Set-Cookie": response.headers["set-cookie"], "Cache-Control": "no-store"},
        )
    return session


CurrentSession = Annotated[Session, Depends(get_current_session)]


def get_current_user(session: CurrentSession) -> User:
    return session.user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_trusted_origin(request: Request, settings: AuthSettings) -> None:
    """Protect cookie-changing POSTs from browser requests on untrusted origins.

    Origin-free CLI clients and same-origin Swagger remain usable.
    CORS alone restricts response access, not whether a request changes state.
    """
    origin = request.headers.get("origin")
    allowed = {str(settings.frontend_origin).rstrip("/"), str(request.base_url).rstrip("/")}
    if origin is not None and origin not in allowed:
        raise HTTPException(status_code=403, detail="Untrusted origin", headers={"Cache-Control": "no-store"})
