import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_encryption
from app.core.db import get_db
from app.core.encryption import EncryptionService, key_hint
from app.models.api_key import PROVIDERS, UserApiKey
from app.models.user import User
from app.schemas.api_key import ApiKeyCreate, ApiKeyOut

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


@router.get("", response_model=list[ApiKeyOut])
async def list_api_keys(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    keys = (
        await db.execute(
            select(UserApiKey).where(UserApiKey.user_id == user.id).order_by(UserApiKey.provider)
        )
    ).scalars().all()
    return [ApiKeyOut.model_validate(k) for k in keys]


@router.post("", response_model=ApiKeyOut, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    body: ApiKeyCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    encryption: EncryptionService = Depends(get_encryption),
):
    if body.provider not in PROVIDERS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "provider inválido")

    encrypted = encryption.encrypt(body.api_key)
    hint = key_hint(body.api_key)

    existing = (
        await db.execute(
            select(UserApiKey).where(
                UserApiKey.user_id == user.id, UserApiKey.provider == body.provider
            )
        )
    ).scalar_one_or_none()

    if existing is not None:
        existing.encrypted_key = encrypted
        existing.key_hint = hint
        await db.commit()
        await db.refresh(existing)
        return ApiKeyOut.model_validate(existing)

    key = UserApiKey(
        user_id=user.id, provider=body.provider, encrypted_key=encrypted, key_hint=hint
    )
    db.add(key)
    await db.commit()
    await db.refresh(key)
    return ApiKeyOut.model_validate(key)


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(
    key_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    key = await db.get(UserApiKey, key_id)
    if key is None or key.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chave não encontrada")
    await db.delete(key)
    await db.commit()
