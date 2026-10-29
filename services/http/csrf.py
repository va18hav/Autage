import secrets

from fastapi import HTTPException, Request, Response, status

from services.config import settings

CSRF_COOKIE_NAME = "autage_csrf"
CSRF_HEADER_NAME = "X-CSRF-Token"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})


def _valid_token(token: str | None) -> bool:
    if not token or not 32 <= len(token) <= 128:
        return False
    return all(character.isalnum() or character in "-_" for character in token)


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=token,
        httponly=False,
        samesite="lax",
        secure=settings.COOKIE_SECURE,
        max_age=settings.JWT_EXPIRE_MINUTES * 60,
        path="/",
    )


def issue_csrf_token(response: Response) -> str:
    """Issue a fresh CSRF token and store it in a dashboard-readable cookie."""
    token = secrets.token_urlsafe(32)
    _set_cookie(response, token)
    return token


def ensure_csrf_token(request: Request, response: Response) -> str:
    """Reuse the current token when valid, otherwise issue a new one."""
    token = request.cookies.get(CSRF_COOKIE_NAME)
    if _valid_token(token):
        return token
    return issue_csrf_token(response)


def clear_csrf_cookie(response: Response) -> None:
    response.delete_cookie(
        key=CSRF_COOKIE_NAME,
        httponly=False,
        samesite="lax",
        secure=settings.COOKIE_SECURE,
        path="/",
    )


def require_csrf(request: Request) -> None:
    """Reject cookie-authenticated state-changing requests without a matching token."""
    if request.method.upper() in SAFE_METHODS:
        return

    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    header_token = request.headers.get(CSRF_HEADER_NAME)

    if (
        not _valid_token(cookie_token)
        or not _valid_token(header_token)
        or not secrets.compare_digest(
            header_token.encode("utf-8"),
            cookie_token.encode("utf-8"),
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF validation failed.",
        )
