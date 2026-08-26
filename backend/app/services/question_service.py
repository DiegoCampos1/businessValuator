from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.question import Question, UserQuestionSetting


async def get_enabled_questions(
    db: AsyncSession, user_id: Any, sector_id: Any = None
) -> list[dict[str, Any]]:
    """Retorna as perguntas habilitadas do usuário (gerais + do setor)."""
    system_qs = (
        await db.execute(
            select(Question).where(Question.is_system.is_(True), Question.user_id.is_(None))
        )
    ).scalars().all()
    own_qs = (
        await db.execute(select(Question).where(Question.user_id == user_id))
    ).scalars().all()
    all_qs = list(system_qs) + list(own_qs)

    settings: dict[Any, UserQuestionSetting] = {}
    ids = [q.id for q in all_qs]
    if ids:
        rows = (
            await db.execute(
                select(UserQuestionSetting).where(
                    UserQuestionSetting.user_id == user_id,
                    UserQuestionSetting.question_id.in_(ids),
                )
            )
        ).scalars().all()
        settings = {r.question_id: r for r in rows}

    result: list[dict[str, Any]] = []
    for q in all_qs:
        if q.sector_id is not None and (sector_id is None or q.sector_id != sector_id):
            continue
        s = settings.get(q.id)
        if s is not None and not s.enabled:
            continue
        text = (s.custom_text if s is not None and s.custom_text else q.text)
        result.append({"id": q.id, "text": text, "criteria": q.criteria})
    return result
