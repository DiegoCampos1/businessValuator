"""Cliente fino para a API de busca da Tavily."""

from typing import Any

import httpx

TAVILY_SEARCH_URL = "https://api.tavily.com/search"

# Domínios preferenciais de Relações com Investidores / fontes oficiais.
RI_DOMAINS = [
    "ri.",
    ".com.br",
    "api.mziq.com",
    "gov.br",
    "b3.com.br",
]


class TavilyError(Exception):
    pass


class TavilyClient:
    def __init__(self, api_key: str):
        if not api_key:
            raise TavilyError("TAVILY_API_KEY não configurada")
        self._api_key = api_key

    async def search(
        self,
        query: str,
        include_domains: list[str] | None = None,
        max_results: int = 5,
    ) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {
            "api_key": self._api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": "advanced",
        }
        if include_domains:
            payload["include_domains"] = include_domains

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(TAVILY_SEARCH_URL, json=payload)
            if resp.status_code != 200:
                raise TavilyError(f"Tavily retornou {resp.status_code}: {resp.text[:200]}")
            data = resp.json()

        results = data.get("results", [])
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", ""),
            }
            for r in results
        ]

    def build_ri_query(self, company: str, topic: str) -> str:
        """Monta uma consulta apontando para RI / fontes oficiais."""
        return f"{company} {topic} site de relações com investidores relatório oficial"
