from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.db.database import get_db_session
from services.db.models.user import User
from services.http.auth import resolve_optional_user
from services.http.schemas.auth import AuthStatusResponse

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
