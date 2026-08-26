"""Agente de análise de ativos (chatbot).

O agente segue uma diretriz crítica de confiabilidade: busca dados no site de
Relações com Investidores (RI) / fontes confiáveis via Tavily e NUNCA assume ou
alucina informações; toda resposta cita a fonte.
"""

import json
from collections.abc import AsyncGenerator
from typing import Any

from app.services.llm import LLMClient
from app.services.sector_mapper import classify_sector, sector_slugs
from app.services.tavily import TavilyClient

# Diretriz crítica de confiabilidade — presente em todo prompt do agente.
SYSTEM_PROMPT = """\
Você é um analista fundamentalista de ações da B3 (bolsa de valores do Brasil).
Sua função é avaliar empresas respondendo a um questionário com base EXCLUSIVAMENTE em dados reais.

DIRETRIZES CRÍTICAS DE CONFIABILIDADE (obrigatórias):
1. Todos os dados DEVEM ser obtidos por busca na web no site oficial de Relações com Investidores (RI) da empresa ou em fontes financeiras confiáveis (CVM, B3, relatórios trimestrais/anuais, fatos relevantes, comunicados oficiais).
2. É ESTRITAMENTE PROIBIDO assumir, estimar, deduzir ou inventar (alucinar) qualquer informação. Se o dado não estiver presente nas fontes consultadas, responda explicitamente que não foi possível confirmar o dado nas fontes consultadas.
3. Toda resposta DEVE terminar com a citação da fonte no formato: "As informações foram retiradas de <fonte>. Link: <URL>".
4. Nunca mencione uma fonte que não foi de fato consultada.
"""

IDENTIFY_SYSTEM = """\
Você identifica empresas da bolsa brasileira (B3). Responda APENAS um JSON válido, sem markdown, no formato:
{"company": "<nome oficial da empresa>", "sector_slug": "<slug>"}
Os slugs de setor válidos são: {slugs}
Se não conseguir identificar o setor, use "outros".
"""

ANSWER_TEMPLATE = """\
Pergunta: {question}

Contexto obtido via busca (use SOMENTE este contexto; não invente nada fora dele):
{context}

Responda a pergunta com base exclusivamente no contexto acima. Se o contexto não contiver a informação, diga explicitamente que não foi possível confirmar o dado nas fontes consultadas. Termine a resposta com a citação no formato: "As informações foram retiradas de <fonte>. Link: <URL>".
"""


def build_identify_user(query: str) -> str:
    return f"Identifique a empresa e o setor B3 para: {query}"


def parse_identification(raw: str) -> dict[str, Any]:
    """Extrai {'company', 'sector_slug'} de uma resposta LLM, tolerando markdown."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.removeprefix("json").strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        # fallback: procura o primeiro objeto JSON na string
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("resposta de identificação sem JSON") from None
        data = json.loads(cleaned[start : end + 1])
    slug = (data.get("sector_slug") or "").strip().lower()
    if slug not in sector_slugs():
        slug = "outros"
    return {"company": (data.get("company") or "").strip(), "sector_slug": slug}


def format_citations(results: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {"source": r.get("title") or "Fonte", "title": r.get("title") or "", "url": r.get("url", "")}
        for r in results
        if r.get("url")
    ]


def build_context(results: list[dict[str, Any]]) -> str:
    blocks = []
    for i, r in enumerate(results, 1):
        blocks.append(f"[{i}] {r.get('title', '')}\n{r.get('content', '')}\nURL: {r.get('url', '')}")
    return "\n\n".join(blocks) or "(nenhum resultado de busca)"


def build_answer_user(question_text: str, results: list[dict[str, Any]]) -> str:
    return ANSWER_TEMPLATE.format(question=question_text, context=build_context(results))


async def identify(
    llm: LLMClient, tavily: TavilyClient, query: str
) -> tuple[str, str, list[dict[str, Any]]]:
    """Identifica a empresa e o setor B3 a partir da mensagem do usuário."""
    results = await tavily.search(tavily.build_ri_query(query, "relações com investidores"))
    company = query.strip()
    sector_slug = classify_sector(query) or "outros"

    raw = await llm.complete(
        IDENTIFY_SYSTEM.format(slugs=", ".join(sector_slugs())), build_identify_user(query)
    )
    try:
        ident = parse_identification(raw)
        if ident["company"]:
            company = ident["company"]
        sector_slug = ident["sector_slug"]
    except (ValueError, json.JSONDecodeError):
        # mantém fallback determinístico
        pass

    if sector_slug == "outros" or sector_slug is None:
        sector_slug = classify_sector(query) or "outros"

    return company, sector_slug, results


async def answer_question(
    llm: LLMClient, tavily: TavilyClient, company: str, question_text: str
) -> tuple[str, list[dict[str, str]]]:
    """Responde uma pergunta com busca real e citação de fonte."""
    results = await tavily.search(
        tavily.build_ri_query(company, question_text), max_results=4
    )
    answer = await llm.complete(SYSTEM_PROMPT, build_answer_user(question_text, results))
    citations = format_citations(results)
    return answer, citations


async def run_analysis(
    llm: LLMClient,
    tavily: TavilyClient,
    company: str,
    questions: list[dict[str, Any]],
) -> AsyncGenerator[dict[str, Any], None]:
    """Gera a análise pergunta a pergunta, emitindo eventos SSE.

    A empresa já vem identificada pelo chamador. Eventos:
    {"type": "question", ...} -> {"type": "token", "text": ...} ->
    {"type": "citations", ...} -> {"type": "done"}
    """
    for q in questions:
        question_text = q.get("custom_text") or q.get("text")
        yield {"type": "question", "id": str(q["id"]), "text": question_text}

        results = await tavily.search(tavily.build_ri_query(company, question_text), max_results=4)
        citations = format_citations(results)

        async for token in llm.stream(SYSTEM_PROMPT, build_answer_user(question_text, results)):
            yield {"type": "token", "text": token}

        yield {"type": "citations", "items": citations, "question_id": str(q["id"])}

    yield {"type": "done"}
