import uuid

import jwt as pyjwt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_google_id_token,
)
from app.models.user import User
from app.schemas.auth import GoogleTokenRequest, RefreshRequest, TokenResponse, UserOut

router = APIRouter(tags=["auth"])


def _token_response(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user.id, user.email),
        refresh_token=create_refresh_token(user.id, user.email),
        user=UserOut.model_validate(user),
    )


@router.post("/auth/google", response_model=TokenResponse)
async def google_login(body: GoogleTokenRequest, db: AsyncSession = Depends(get_db)):
    try:
        info = verify_google_id_token(body.id_token)
    except ValueError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "id_token inválido") from exc

    email = info.get("email")
    if not email:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "id_token sem email")

    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None:
        user = User(
            email=email,
            name=info.get("name"),
            avatar_url=info.get("picture"),
            google_sub=info.get("sub"),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    else:
        changed = False
        for field, value in (
            ("name", info.get("name")),
            ("avatar_url", info.get("picture")),
            ("google_sub", info.get("sub")),
        ):
            if value and getattr(user, field) is None:
                setattr(user, field, value)
                changed = True
        if changed:
            await db.commit()
            await db.refresh(user)

    return _token_response(user)


@router.post("/auth/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        payload = decode_token(body.refresh_token)
    except pyjwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "refresh token inválido") from exc
    if payload.get("type") != "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "refresh token inválido")
    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "refresh token inválido") from exc

    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuário não encontrado")
    return _token_response(user)


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return UserOut.model_validate(user)
