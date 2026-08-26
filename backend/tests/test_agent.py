from app.services.agent import (
    ANSWER_TEMPLATE,
    SYSTEM_PROMPT,
    build_answer_user,
    format_citations,
    parse_identification,
)


def test_system_prompt_forbids_hallucination():
    assert "PROIBIDO" in SYSTEM_PROMPT
    assert "Relações com Investidores" in SYSTEM_PROMPT
    assert "alucinar" in SYSTEM_PROMPT.lower()


def test_answer_template_requires_citation():
    assert "Link:" in ANSWER_TEMPLATE
    assert "SOMENTE este contexto" in ANSWER_TEMPLATE


def test_parse_identification_plain_json():
    d = parse_identification('{"company": "Banco do Brasil S.A.", "sector_slug": "financeiro"}')
    assert d["company"] == "Banco do Brasil S.A."
    assert d["sector_slug"] == "financeiro"


def test_parse_identification_with_markdown_fence():
    d = parse_identification(
        '```json\n{"company": "Petrobras", "sector_slug": "petroleo-gas-biocombustiveis"}\n```'
    )
    assert d["company"] == "Petrobras"
    assert d["sector_slug"] == "petroleo-gas-biocombustiveis"


def test_parse_identification_unknown_sector_falls_back_to_outros():
    d = parse_identification('{"company": "X", "sector_slug": "setor-inexistente"}')
    assert d["sector_slug"] == "outros"


def test_format_citations_keeps_urls():
    results = [
        {"title": "Relatório 3T24", "url": "https://ri.empresa.com.br/3t24", "content": "..."}
    ]
    citations = format_citations(results)
    assert citations[0]["url"] == "https://ri.empresa.com.br/3t24"
    assert citations[0]["source"] == "Relatório 3T24"


def test_build_answer_user_includes_context_and_citation_instruction():
    user = build_answer_user("ROE > 5%?", [{"title": "t", "url": "u", "content": "c"}])
    assert "ROE > 5%?" in user
    assert "URL: u" in user
    assert "Link:" in user
