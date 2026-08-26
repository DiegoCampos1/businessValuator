import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_encryption
from app.core.config import settings
from app.core.db import async_session_factory, get_db
from app.models.api_key import UserApiKey
from app.models.conversation import Conversation, Message
from app.models.sector import Sector
from app.models.user import User
from app.schemas.chat import ChatRequest
from app.services.agent import (
    SYSTEM_PROMPT,
    build_answer_user,
    format_citations,
    identify,
)
from app.services.llm import LLMClient
from app.services.question_service import get_enabled_questions
from app.services.tavily import TavilyClient

router = APIRouter(prefix="/chat", tags=["chat"])


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


async def _resolve_llm(db: AsyncSession, user: User) -> LLMClient:
    keys = (
        await db.execute(select(UserApiKey).where(UserApiKey.user_id == user.id))
    ).scalars().all()
    if not keys:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Adicione uma chave de API de LLM (DeepSeek ou OpenAI) antes de usar o chat.",
        )
    chosen = next((k for k in keys if k.provider == "deepseek"), keys[0])
    encryption = get_encryption()
    plain = encryption.decrypt(chosen.encrypted_key)
    return LLMClient(chosen.provider, plain)


@router.post("")
async def chat(
    body: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    llm = await _resolve_llm(db, user)
    tavily = TavilyClient(settings.tavily_api_key)

    conversation = None
    if body.conversation_id is not None:
        conversation = await db.get(Conversation, body.conversation_id)
        if conversation is None or conversation.user_id != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversa não encontrada")
    else:
        conversation = Conversation(user_id=user.id, title=body.message[:80])
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)

    db.add(Message(conversation_id=conversation.id, role="user", content=body.message))
    await db.commit()

    company, sector_slug, _ri_results = await identify(llm, tavily, body.message)

    sector_id: uuid.UUID | None = None
    if sector_slug and sector_slug != "outros":
        sector = (
            await db.execute(select(Sector).where(Sector.slug == sector_slug))
        ).scalar_one_or_none()
        if sector is not None:
            sector_id = sector.id
            conversation.sector_id = sector.id
            conversation.title = company[:255]
            await db.commit()

    questions = await get_enabled_questions(db, user.id, sector_id)
    conversation_id = conversation.id

    async def gen():
        yield _sse({"type": "start", "company": company, "sector_slug": sector_slug})
        async with async_session_factory() as s:
            for q in questions:
                yield _sse({"type": "question", "id": str(q["id"]), "text": q["text"]})
                results = await tavily.search(
                    tavily.build_ri_query(company, q["text"]), max_results=4
                )
                citations = format_citations(results)
                parts: list[str] = []
                async for token in llm.stream(SYSTEM_PROMPT, build_answer_user(q["text"], results)):
                    parts.append(token)
                    yield _sse({"type": "token", "text": token})
                s.add(
                    Message(
                        conversation_id=conversation_id,
                        role="assistant",
                        content="".join(parts),
                        citations=citations,
                    )
                )
                await s.commit()
                yield _sse({"type": "citations", "items": citations, "question_id": str(q["id"])})
        yield _sse({"type": "done", "conversation_id": str(conversation_id)})

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
