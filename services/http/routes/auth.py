from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.db.database import get_db_session
from services.db.models.user import User
from services.http.auth import clear_auth_cookie, create_access_token, hash_password, resolve_optional_user, set_auth_cookie, verify_password
from services.http.schemas.auth import AuthStatusResponse, LoginRequest, RegisterRequest, UserOut

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.get(
    "/status",
    response_model=AuthStatusResponse,
    summary="Check whether the single-user account has been initialized and if the caller is authenticated",
)
async def auth_status(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
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
    payload: RegisterRequest,
    response: Response,
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
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user.id, user.username)
    set_auth_cookie(response, token)
    return user


@router.post(
    "/login",
    response_model=UserOut,
    summary="Authenticate with username and password and set HttpOnly JWT cookie",
)
async def login(
    payload: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
):
    username = payload.username.strip().lower()
    user = (
        await db.execute(select(User).where(User.username == username))
    ).scalar_one_or_none()

    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    token = create_access_token(user.id, user.username)
    set_auth_cookie(response, token)
    return user


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Clear the HttpOnly JWT session cookie",
)
async def logout(response: Response):
    clear_auth_cookie(response)
