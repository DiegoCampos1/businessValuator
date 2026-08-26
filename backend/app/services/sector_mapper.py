"""Setores oficiais da B3 + mapeamento das categorias do question.md.

O question.md usa categorias internas (Gerais, Elétricas, Bancos). Estas são
mapeadas para os 12 setores oficiais da B3:
  - Elétricas -> Utilidade Pública
  - Bancos    -> Financeiro
  - Gerais    -> sem setor (aplicam a todos)
"""

B3_SECTORS: list[tuple[str, str]] = [
    ("Bens Industriais", "bens-industriais"),
    ("Comunicações", "comunicacoes"),
    ("Construção e Transporte", "construcao-transporte"),
    ("Consumo Cíclico", "consumo-ciclico"),
    ("Consumo não Cíclico", "consumo-nao-ciclico"),
    ("Financeiro", "financeiro"),
    ("Materiais Básicos", "materiais-basicos"),
    ("Outros", "outros"),
    ("Petróleo Gás e Biocombustíveis", "petroleo-gas-biocombustiveis"),
    ("Saúde", "saude"),
    ("Tecnologia da Informação", "tecnologia-da-informacao"),
    ("Utilidade Pública", "utilidade-publica"),
]

# Categoria do question.md -> slug de setor B3 (None = pergunta geral)
CATEGORY_TO_SECTOR_SLUG: dict[str, str | None] = {
    "Gerais": None,
    "Elétricas": "utilidade-publica",
    "Bancos": "financeiro",
}

# Palavras-chave para classificação determinística de setor (fallback / testes).
_KEYWORD_SECTOR: list[tuple[str, list[str]]] = [
    ("financeiro", ["banco", "bancário", "seguradora", "financeira", "crédito", "asset"]),
    ("utilidade-publica", ["elétrica", "energia", "saneamento", "água", "concessionária", "distribuidora", "transmissão"]),
    ("saude", ["saúde", "hospital", "farmacêutica", "laboratório", "plano de saúde"]),
    ("tecnologia-da-informacao", ["software", "tecnologia", "ti", "computação", "internet", "app"]),
    ("petroleo-gas-biocombustiveis", ["petróleo", "petrobras", "óleo", "gás", "biocombustível", "etanol", "refinaria"]),
    ("materiais-basicos", ["mineração", "siderurgia", "celulose", "química", "aço", "papel"]),
    ("consumo-nao-ciclico", ["alimentos", "bebidas", "higiene", "varejo alimentar", "agro"]),
    ("consumo-ciclico", ["varejo", "vestuário", "automóvel", "montadora", "e-commerce", "turismo", "construção civil"]),
    ("bens-industriais", ["industrial", "máquinas", "equipamentos", "aeroespacial", "defesa"]),
    ("comunicacoes", ["telecom", "telefonia", "mídia", "broadcast"]),
    ("construcao-transporte", ["concessão rodoviária", "rodovia", "ferrovia", "logística", "aeroporto", "porto"]),
]


def sector_slugs() -> list[str]:
    return [slug for _, slug in B3_SECTORS]


def category_to_sector_slug(category: str) -> str | None:
    return CATEGORY_TO_SECTOR_SLUG.get(category.strip())


def classify_sector(text: str) -> str | None:
    """Classifica um texto (nome/ticker/descrição) no setor B3 correspondente.

    Retorna o slug do setor ou None quando não há correspondência.
    """
    normalized = (text or "").lower()
    for slug, keywords in _KEYWORD_SECTOR:
        if any(kw in normalized for kw in keywords):
            return slug
    return None
