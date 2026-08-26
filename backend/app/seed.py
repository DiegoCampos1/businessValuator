"""Seed dos setores oficiais da B3 e das perguntas padrão (question.md).

Executado como: python -m app.seed
"""

import asyncio

from sqlalchemy import func, select

from app.core.db import Base, async_session_factory, engine
from app.models import Question, Sector  # noqa: F401
from app.services.sector_mapper import B3_SECTORS

# (sector_slug | None, criteria, text) — extraído de question.md
SEED_QUESTIONS: list[tuple[str | None, str, str]] = [
    # Gerais
    (None, "ROE", "ROE historicamente maior que 5%? (Considere anos anteriores)."),
    (None, "CAGR", "Tem um crescimento de receitas (ou lucro) superior a 5% nos últimos 5 anos?"),
    (None, "Dividendos", "A empresa tem um histórico de pagamento de dividendos?"),
    (
        None,
        "Tecnologia e Pesquisa",
        "A empresa investe amplamente em pesquisa e inovação? Setor Obsoleto = SEMPRE NÃO",
    ),
    (None, "Tempo de Mercado", "Tem mais de 30 anos de mercado? (Fundação)"),
    (
        None,
        "Vantagens Competitivas",
        "É líder nacional ou mundial no setor em que atua? (Só considera se for LÍDER, primeira colocada)",
    ),
    (None, "Perenidade", "O setor em que a empresa atua tem mais de 70 anos?"),
    (None, "Tamanho", "A empresa é uma BLUE CHIP?"),
    (None, "Governança", "A empresa tem uma boa gestão? Histórico de corrupção = SEMPRE NÃO"),
    (None, "Independência", "É livre de controle ESTATAL ou concentração em cliente único?"),
    (
        None,
        "Pouco Endividada",
        "Div. Líquida/EBITDA é menor que 2 nos últimos 5 anos?",
    ),
    # Elétricas -> Utilidade Pública
    (
        "utilidade-publica",
        "Qualidade ANEEL (DEC/FEC)",
        "A distribuidora cumpre os limites de DEC e FEC definidos pela ANEEL (sem histórico de violações)?",
    ),
    (
        "utilidade-publica",
        "Tensão (DRP/DRC)",
        "A empresa cumpre os limites de conformidade de tensão (DRP ≤ 3% e DRC ≤ 0,5%)?",
    ),
    (
        "utilidade-publica",
        "Concessão",
        "A concessão/outorga tem prazo longo restante (baixo risco de caducidade ou não renovação)?",
    ),
    (
        "utilidade-publica",
        "Revisão Tarifária",
        "Há revisão tarifária periódica iminente que possa reduzir a receita?",
    ),
    (
        "utilidade-publica",
        "Perdas Não Técnicas",
        "As perdas não técnicas (furtos) estão dentro da meta regulatória?",
    ),
    # Bancos -> Financeiro
    (
        "financeiro",
        "Basileia (Capitalização)",
        "O Índice de Basileia está confortavelmente acima do mínimo regulatório do BACEN (11% + buffers), com capital de melhor qualidade (CET1/Nível I) robusto?",
    ),
    (
        "financeiro",
        "Liquidez (LCR)",
        "O Índice de Liquidez de Curto Prazo (LCR) está acima de 100%?",
    ),
    (
        "financeiro",
        "Inadimplência (NPL)",
        "O índice de inadimplência (atrasos acima de 90 dias) é controlado e abaixo da média do setor?",
    ),
    (
        "financeiro",
        "Cobertura (Provisões)",
        "O índice de cobertura (provisões sobre inadimplência) está acima de 100%?",
    ),
    (
        "financeiro",
        "Eficiência Operacional",
        "O índice de eficiência (despesas sobre receitas) é baixo, abaixo da média do setor?",
    ),
]


async def seed() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as db:
        sector_count = (await db.execute(select(func.count()).select_from(Sector))).scalar()
        if sector_count == 0:
            for name, slug in B3_SECTORS:
                db.add(Sector(name=name, slug=slug))
            await db.commit()

        question_count = (await db.execute(select(func.count()).select_from(Question))).scalar()
        if question_count == 0:
            sectors = (await db.execute(select(Sector))).scalars().all()
            slug_to_id = {s.slug: s.id for s in sectors}
            for sector_slug, criteria, text in SEED_QUESTIONS:
                db.add(
                    Question(
                        sector_id=slug_to_id.get(sector_slug) if sector_slug else None,
                        criteria=criteria,
                        text=text,
                        is_system=True,
                        user_id=None,
                    )
                )
            await db.commit()


if __name__ == "__main__":
    asyncio.run(seed())
