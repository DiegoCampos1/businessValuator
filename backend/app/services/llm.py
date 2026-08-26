"""Cliente de LLM (OpenAI / DeepSeek) via SDK OpenAI-compatível.

A chave de API é fornecida já decifrada (somente em memória) pelo chamador.
"""

from openai import AsyncOpenAI

PROVIDER_BASE_URL = {
    "openai": "https://api.openai.com/v1",
    "deepseek": "https://api.deepseek.com",
    "other": "https://api.openai.com/v1",
}

PROVIDER_DEFAULT_MODEL = {
    "openai": "gpt-4o-mini",
    "deepseek": "deepseek-chat",
    "other": "gpt-4o-mini",
}


class LLMClient:
    def __init__(self, provider: str, api_key: str):
        self.provider = provider
        self.model = PROVIDER_DEFAULT_MODEL.get(provider, "gpt-4o-mini")
        self._client = AsyncOpenAI(api_key=api_key, base_url=PROVIDER_BASE_URL.get(provider))

    async def complete(self, system: str, user: str, temperature: float = 0.2) -> str:
        resp = await self._client.chat.completions.create(
            model=self.model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content or ""

    async def stream(self, system: str, user: str):
        """Gera tokens de forma incremental (async generator)."""
        stream = await self._client.chat.completions.create(
            model=self.model,
            temperature=0.2,
            stream=True,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
