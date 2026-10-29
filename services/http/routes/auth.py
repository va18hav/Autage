import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from services.config import settings
from services.db.database import get_db_session
from services.db.models.user import User
from services.http.auth import (
    clear_auth_cookie,
    create_access_token,
    get_current_user,
    hash_password,
    resolve_optional_user,
    set_auth_cookie,
    verify_password,
)
from services.http.csrf import (
    clear_csrf_cookie,
    ensure_csrf_token,
    issue_csrf_token,
    require_csrf,
)
from services.http.rate_limit import (
    RateLimitBackendError,
    clear_failures,
    client_ip,
    get_rate_limit_redis,
    login_rate_limit_key,
    password_reset_rate_limit_key,
    record_failure,
    retry_after,
    setup_rate_limit_key,
)
from services.http.schemas.auth import (
    AuthStatusResponse,
    LoginRequest,
    PasswordResetRequest,
    RegisterRequest,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["Auth"])

# Used to keep unknown-user login timing comparable to a wrong password.
_DUMMY_PASSWORD_HASH = hash_password("autage-dummy-password-not-real")


async def _enforce_auth_rate_limit(request: Request, key: str):
    redis = get_rate_limit_redis(request)
    try:
        wait_seconds = await retry_after(redis, key)
    except RateLimitBackendError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is temporarily unavailable. Try again shortly.",
        ) from exc

    if wait_seconds is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many authentication attempts. Try again later.",
            headers={"Retry-After": str(wait_seconds)},
        )
    return redis


async def _record_auth_failure(redis, key: str) -> None:
    try:
        await record_failure(redis, key)
    except RateLimitBackendError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is temporarily unavailable. Try again shortly.",
        ) from exc


async def _clear_auth_failures(redis, key: str) -> None:
    try:
        await clear_failures(redis, key)
    except RateLimitBackendError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is temporarily unavailable. Try again shortly.",
        ) from exc


async def _verify_setup_token(
    setup_token: str | None,
    redis,
    rate_limit_key: str,
    unavailable_detail: str,
) -> None:
    configured_token = settings.AUTAGE_SETUP_TOKEN
    if not configured_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=unavailable_detail,
        )
    if not setup_token or not secrets.compare_digest(
        setup_token.encode("utf-8"),
        configured_token.encode("utf-8"),
    ):
        await _record_auth_failure(redis, rate_limit_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid setup token.",
        )

    await _clear_auth_failures(redis, rate_limit_key)


@router.get(
    "/status",
    response_model=AuthStatusResponse,
    summary="Check whether the single-user account has been initialized and if the caller is authenticated",
)
async def auth_status(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
):
    ensure_csrf_token(request, response)
    count = (await db.execute(select(func.count()).select_from(User))).scalar_one()
    initialized = count > 0

    if not initialized:
        return AuthStatusResponse(
            initialized=False,
            authenticated=False,
            user=None,
        )

    user = await resolve_optional_user(request, db)
    return AuthStatusResponse(
        initialized=True,
        authenticated=user is not None,
        user=user,
    )


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Initial setup: register the single admin user if no user exists yet",
)
async def register(
    request: Request,
    payload: RegisterRequest,
    response: Response,
    setup_token: str | None = Header(
        default=None,
        alias="X-Autage-Setup-Token",
    ),
    db: AsyncSession = Depends(get_db_session),
):
    existing_count = (
        await db.execute(select(func.count()).select_from(User))
    ).scalar_one()
    if existing_count > 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Instance already initialized. Only one user account is permitted.",
        )

    setup_limit_key = setup_rate_limit_key(client_ip(request))
    redis = await _enforce_auth_rate_limit(request, setup_limit_key)

    await _verify_setup_token(
        setup_token,
        redis,
        setup_limit_key,
        unavailable_detail=(
            "Initial setup is locked. Set AUTAGE_SETUP_TOKEN in the deployment "
            "environment and restart the API."
        ),
    )

    username = payload.username.strip().lower()
    name = payload.name.strip()
    if not username or not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Name and username cannot be blank.",
        )

    user = User(
        username=username,
        name=name,
        password_hash=hash_password(payload.password),
        instance_key=1,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as exc:
        # The unique single-instance constraint is the final guard against two
        # simultaneous first-registration requests both succeeding.
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Instance already initialized. Only one user account is permitted.",
        ) from exc
    await db.refresh(user)

    issue_csrf_token(response)
    token = create_access_token(user.id, user.username)
    set_auth_cookie(response, token)
    return user


@router.post(
    "/login",
    response_model=UserOut,
    summary="Authenticate with username and password and set HttpOnly JWT cookie",
)
async def login(
    request: Request,
    payload: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
):
    login_limit_key = login_rate_limit_key(client_ip(request))
    redis = await _enforce_auth_rate_limit(request, login_limit_key)

    username = payload.username.strip().lower()
    user = (
        await db.execute(select(User).where(User.username == username))
    ).scalar_one_or_none()

    candidate_hash = user.password_hash if user else _DUMMY_PASSWORD_HASH
    password_ok = verify_password(payload.password, candidate_hash)
    if user is None or not password_ok:
        await _record_auth_failure(redis, login_limit_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    await _clear_auth_failures(redis, login_limit_key)

    issue_csrf_token(response)
    token = create_access_token(user.id, user.username)
    set_auth_cookie(response, token)
    return user


@router.post(
    "/reset-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Reset the administrator password using the configured setup token",
)
async def reset_password(
    request: Request,
    payload: PasswordResetRequest,
    setup_token: str | None = Header(
        default=None,
        alias="X-Autage-Setup-Token",
    ),
    db: AsyncSession = Depends(get_db_session),
):
    users = (await db.execute(select(User))).scalars().all()
    if not users:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Instance is not initialized.",
        )

    limit_key = password_reset_rate_limit_key(client_ip(request))
    redis = await _enforce_auth_rate_limit(request, limit_key)

    await _verify_setup_token(
        setup_token,
        redis,
        limit_key,
        unavailable_detail=(
            "Password reset is locked. Set AUTAGE_SETUP_TOKEN in the deployment "
            "environment and restart the API."
        ),
    )

    if payload.new_password != payload.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match.",
        )

    await _clear_auth_failures(redis, login_rate_limit_key(client_ip(request)))

    user = users[0]
    user.password_hash = hash_password(payload.new_password)
    await db.commit()


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Clear the HttpOnly JWT session cookie",
)
async def logout(
    response: Response,
    _: None = Depends(require_csrf),
):
    clear_auth_cookie(response)
    clear_csrf_cookie(response)


@router.get(
    "/me",
    response_model=UserOut,
    summary="Return the currently authenticated user",
)
async def me(current_user: User = Depends(get_current_user)):
    return current_user
