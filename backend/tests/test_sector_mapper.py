from app.services.sector_mapper import B3_SECTORS, category_to_sector_slug, classify_sector


def test_b3_has_twelve_sectors():
    assert len(B3_SECTORS) == 12


def test_category_mapping():
    assert category_to_sector_slug("Elétricas") == "utilidade-publica"
    assert category_to_sector_slug("Bancos") == "financeiro"
    assert category_to_sector_slug("Gerais") is None


def test_classify_bank():
    assert classify_sector("Banco do Brasil") == "financeiro"
    assert classify_sector("Itaú Unibanco") == "financeiro"


def test_classify_utility():
    assert classify_sector("CEMIG energia elétrica") == "utilidade-publica"


def test_classify_oil():
    assert classify_sector("Petrobras petróleo") == "petroleo-gas-biocombustiveis"


def test_classify_unknown_returns_none():
    assert classify_sector("xyz não classificado") is None
