import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.question import Question, UserQuestionSetting
from app.models.user import User
from app.schemas.question import (
    QuestionCreate,
    QuestionOut,
    QuestionToggle,
    QuestionUpdate,
)

router = APIRouter(prefix="/questions", tags=["questions"])


async def _get_setting(
    db: AsyncSession, user_id: uuid.UUID, question_id: uuid.UUID
) -> UserQuestionSetting | None:
    return (
        await db.execute(
            select(UserQuestionSetting).where(
                UserQuestionSetting.user_id == user_id,
                UserQuestionSetting.question_id == question_id,
            )
        )
    ).scalar_one_or_none()


async def _get_or_create_setting(
    db: AsyncSession, user_id: uuid.UUID, question_id: uuid.UUID
) -> UserQuestionSetting:
    s = await _get_setting(db, user_id, question_id)
    if s is None:
        s = UserQuestionSetting(user_id=user_id, question_id=question_id)
        db.add(s)
    return s


def _to_out(q: Question, s: UserQuestionSetting | None) -> QuestionOut:
    return QuestionOut(
        id=q.id,
        sector_id=q.sector_id,
        criteria=q.criteria,
        text=q.text,
        is_system=q.is_system,
        user_id=q.user_id,
        enabled=s.enabled if s is not None else True,
        custom_text=s.custom_text if s is not None else None,
    )


@router.get("", response_model=list[QuestionOut])
async def list_questions(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    system_qs = (
        await db.execute(
            select(Question).where(Question.is_system.is_(True), Question.user_id.is_(None))
        )
    ).scalars().all()
    own_qs = (await db.execute(select(Question).where(Question.user_id == user.id))).scalars().all()
    all_qs = list(system_qs) + list(own_qs)

    settings: dict[uuid.UUID, UserQuestionSetting] = {}
    ids = [q.id for q in all_qs]
    if ids:
        rows = (
            await db.execute(
                select(UserQuestionSetting).where(
                    UserQuestionSetting.user_id == user.id,
                    UserQuestionSetting.question_id.in_(ids),
                )
            )
        ).scalars().all()
        settings = {r.question_id: r for r in rows}

    return [_to_out(q, settings.get(q.id)) for q in all_qs]


@router.post("", response_model=QuestionOut, status_code=status.HTTP_201_CREATED)
async def create_question(
    body: QuestionCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = Question(
        sector_id=body.sector_id,
        criteria=body.criteria,
        text=body.text,
        is_system=False,
        user_id=user.id,
    )
    db.add(q)
    await db.commit()
    await db.refresh(q)
    return _to_out(q, None)


@router.patch("/{question_id}", response_model=QuestionOut)
async def update_question(
    question_id: uuid.UUID,
    body: QuestionUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = await db.get(Question, question_id)
    if q is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pergunta não encontrada")

    is_system = q.is_system and q.user_id is None

    if is_system:
        s = await _get_or_create_setting(db, user.id, q.id)
        if body.text is not None:
            s.custom_text = body.text
        if body.enabled is not None:
            s.enabled = body.enabled
        await db.commit()
        return _to_out(q, s)
    else:
        if q.user_id != user.id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Sem permissão")
        if body.criteria is not None:
            q.criteria = body.criteria
        if body.text is not None:
            q.text = body.text
        if body.sector_id is not None:
            q.sector_id = body.sector_id
        if body.enabled is not None:
            s = await _get_or_create_setting(db, user.id, q.id)
            s.enabled = body.enabled
        await db.commit()
        await db.refresh(q)
        s = await _get_setting(db, user.id, q.id)
        return _to_out(q, s)


@router.post("/{question_id}/toggle", response_model=QuestionOut)
async def toggle_question(
    question_id: uuid.UUID,
    body: QuestionToggle,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = await db.get(Question, question_id)
    if q is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pergunta não encontrada")
    if q.user_id is not None and q.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Sem permissão")

    s = await _get_or_create_setting(db, user.id, q.id)
    s.enabled = body.enabled
    await db.commit()
    return _to_out(q, s)


@router.delete("/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_question(
    question_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = await db.get(Question, question_id)
    if q is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pergunta não encontrada")

    if q.is_system and q.user_id is None:
        # pergunta padrão: "deletar" = desligar
        s = await _get_or_create_setting(db, user.id, q.id)
        s.enabled = False
        await db.commit()
        return

    if q.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Sem permissão")
    await db.delete(q)
    await db.commit()
