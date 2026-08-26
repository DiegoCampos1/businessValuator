# PLAN.md — Business Valuator (SaaS de Análise de Ações B3)

## 1. Visão Geral

Monorepo para um SaaS de análise fundamentalista de ações da B3, cujo núcleo é um **chatbot agente** que recebe o nome/ticker de uma empresa (ex.: "Banco do Brasil" ou "BBAS3"), identifica o setor e responde a um questionário de avaliação (`question.md`) usando **dados reais** obtidos por Web Search (Tavily) — nunca informações alucinadas — sempre citando a fonte.

Repositório de produção: `git@github.com:DiegoCampos1/businessValuator.git`

## 2. Stack Tecnológica (decidida)

| Camada | Escolha |
|---|---|
| Frontend | Next.js (App Router) + TypeScript + Tailwind CSS (mobile-first, dark default) |
| Tabela | `@tanstack/react-table` |
| Server state | TanStack Query (`useMutation` com update otimista) |
| Backend | **FastAPI** + SQLAlchemy 2.0 (async) + Alembic |
| Banco | PostgreSQL 16 |
| LLM | OpenAI + DeepSeek via **SDK OpenAI-compatível** (base_url trocável por provider) |
| Web Search | **Tavily** |
| Criptografia | `cryptography` (Fernet) — master key no `.env` |
| Auth | Google OAuth (ID token) → JWT próprio (access + refresh) |
| Chat streaming | **SSE** (Server-Sent Events), não WebSocket |
| Deploy | Railway (Docker, reaproveitando a lógica do BasketRandomizerApp) |

## 3. Arquitetura

```
┌──────────────┐  SSE (streaming)  ┌──────────────────────┐   Tavily   ┌─────────┐
│  Next.js     │ ◄───────────────► │   FastAPI  :8000     │ ──────────► │ Web API │
│  web  :3000  │   REST + JWT      │   + Agente (LLM)     │             └─────────┘
└──────────────┘                   └───────┬──────────────┘
                                           │  Fernet (keys)   ┌──────────┐
                                           └──► PostgreSQL 16 │ LLM APIs │
                                                              └──────────┘
```

- O agente orquestra: (1) recebe empresa/ticker → (2) identifica setor → (3) carrega perguntas habilitadas do usuário (gerais + específicas do setor) → (4) para cada pergunta, chama Tavily apontando para sites de RI/fontes confiáveis → (5) responde com citação de fonte.
- O backend só decifra a API key do usuário **em memória** no momento da chamada ao LLM.
- **Integração FE↔BE (chat):** `POST /api/v1/chat` retorna `StreamingResponse` (`text/event-stream`). O fluxo é one-way (cliente manda o ativo, servidor devolve tokens + citações), então SSE é suficiente e mais simples que WebSocket (auto-reconnect nativo, sem handshake próprio). WebSocket só seria necessário com mensagens servidor→cliente não solicitadas; não é o caso.
- **Redis é opcional/deferido:** o chat é request/stream efêmero e não precisa de broker. Redis entraria apenas para (a) escalar a API em múltiplas réplicas com pub/sub, (b) fila de jobs assíncronos, (c) rate-limit/cache distribuído, ou (d) notificações/presence em tempo real (nenhum é requisito do MVP). O `docker-compose.yml` mantém o slot pronto.

## 4. Estrutura do Monorepo

```
businessValuator/
├── docker-compose.yml
├── PLAN.md
├── question.md                  # origem das perguntas padrão
├── backend/
│   ├── Dockerfile               # python:3.12-slim
│   ├── pyproject.toml           # black/isort/ruff
│   ├── alembic/
│   ├── seed/                    # seed de setores B3 + perguntas (question.md)
│   └── app/
│       ├── main.py
│       ├── core/                # config (pydantic-settings), db, security (JWT)
│       ├── models/              # SQLAlchemy
│       ├── schemas/             # Pydantic
│       ├── api/                 # routers: auth, sectors, questions, api_keys, chat
│       ├── services/            # encryption, tavily, llm, agent, sector_mapper
│       └── db/                  # session, base
└── frontend/
    ├── Dockerfile               # node:22-alpine
    └── src/
        ├── app/(auth)/login/
        ├── app/(protected)/chat/
        ├── app/(protected)/questions/
        ├── components/          # chat UI, question table
        ├── hooks/               # TanStack Query (useQuestions, useChat, ...)
        ├── lib/api/             # cliente fetch + SSE
        └── store/               # sessão/auth
```

## 5. Modelagem de Dados

Todos os IDs são `UUID` (`uuid4`). `users.email` é a chave única.

**users**
- `id` UUID PK, `email` UNIQUE, `name`, `avatar_url`, `google_sub` UNIQUE, `created_at`, `updated_at`

**user_api_keys** (chaves de LLM do usuário, **criptografadas**)
- `id` UUID PK, `user_id` FK→users, `provider` ENUM(`openai`,`deepseek`,`other`), `encrypted_key` TEXT (Fernet), `key_hint` VARCHAR(12), `created_at`, `updated_at`
- **Nunca** há coluna com chave em texto plano. `GET` devolve só `provider` + `key_hint`.

**sectors** (12 setores oficiais da B3)
- `id` UUID PK, `name` UNIQUE, `slug` UNIQUE, `is_active`
- Seed: Bens Industriais, Comunicações, Construção e Transporte, Consumo Cíclico, Consumo não Cíclico, Financeiro, Materiais Básicos, Outros, Petróleo Gás e Biocombustíveis, Saúde, Tecnologia da Informação, Utilidade Pública.

**questions** (perguntas padrão + criadas pelo usuário)
- `id` UUID PK, `sector_id` FK→sectors **NULLABLE** (NULL = geral), `criteria` TEXT, `text` TEXT, `is_system` BOOL, `user_id` FK→users **NULLABLE** (NULL = padrão do sistema), `created_at`, `updated_at`

**user_question_settings** (relação usuário ↔ pergunta; liga/desliga/edita)
- `id` UUID PK, `user_id` FK→users, `question_id` FK→questions, `enabled` BOOL, `custom_text` TEXT NULL, UNIQUE(`user_id`,`question_id`)

**conversations**
- `id` UUID PK, `user_id` FK→users, `title`, `sector_id` FK NULL, `created_at`, `updated_at`

**messages**
- `id` UUID PK, `conversation_id` FK→conversations, `role` ENUM(`user`,`assistant`), `content` TEXT, `citations` JSONB, `created_at`

> CRUD de perguntas: "adicionar" = `questions` com `user_id`; "delete" de própria = hard delete; "desligar" padrão = `enabled=false`; "editar" padrão = `custom_text`; "ligar/desligar" = toggle `enabled`.

## 6. Autenticação & Segurança

- **Google OAuth:** frontend obtém `id_token` → `POST /api/v1/auth/google` → backend valida (`google-auth`) e emite **JWT próprio** (access curto + refresh). `email` é a chave única.
- **Criptografia de API keys:** `Fernet(MASTER_KEY)`, `MASTER_KEY` no `.env` (secrets do Railway). Encrypt no write, decrypt **apenas em memória**. Logs nunca exibem chave; resposta expõe só `key_hint`.
- **Segurança geral:** secrets via env, CORS restrito, rate-limit, validação Pydantic.

## 7. Backend — FastAPI (endpoints)

Prefixados por `/api/v1`.

| Método | Endpoint | Descrição |
|---|---|---|
| POST | `auth/google` | ID token → JWT (access + refresh) |
| POST | `auth/refresh` | Renova access token |
| GET | `me` | Dados do usuário |
| GET | `sectors` | Lista os 12 setores B3 |
| GET | `questions` | Perguntas do usuário (status) |
| POST/PATCH/DELETE | `questions[/{id}]` | CRUD de perguntas próprias |
| POST | `questions/{id}/toggle` | Liga/desliga |
| GET | `api-keys` | Lista providers + hints |
| POST | `api-keys` | Salva/atualiza chave (encrypt) |
| DELETE | `api-keys/{id}` | Remove chave |
| GET | `conversations` | Histórico |
| GET | `conversations/{id}/messages` | Mensagens |
| POST | `chat` | Inicia conversa — **streaming SSE** |

- `services/`: `encryption.py`, `tavily.py`, `llm.py`, `agent.py`, `sector_mapper.py`.

## 8. Agente (chatbot) — Diretriz Crítica de Confiabilidade

- **System prompt explícito:** o agente **DEVE** buscar dados via ferramenta de busca no site de **Relações com Investidores (RI)** ou fontes seguras; **proibido assumir/inventar**; se não achar fonte, declarar que não encontrou.
- **Tool specification (Tavily):** com parâmetros de domínio para sites de RI (ex.: `ri.<empresa>.com.br`, `api.mziq.com/mzfilemanager`, CVM, B3) e/ou consultas "relatório trimestral", "DRE", "índice de Basileia".
- **Citação obrigatória:** toda resposta termina com fonte (ex.: *"As informações foram retiradas do último relatório trimestral. Link: [URL]"*) — persistido em `messages.citations`.
- **Fluxo:** identifica ativo/setor → carrega perguntas habilitadas → busca e responde → cita fonte.
- **Providers:** OpenAI (GPT) e DeepSeek (`base_url` OpenAI-compatível), usando a chave criptografada do usuário.

## 9. Frontend — Next.js (páginas)

1. **`/login`** — botão "Entrar com Google".
2. **`/` (chat)** — input de empresa/ticker, streaming SSE, histórico, citações clicáveis. Mobile-first, dark default.
3. **`/questions`** — tabela `@tanstack/react-table` + CRUD via `useMutation` com **update otimista** (rollback em erro).

- Sessão JWT (access em memória, refresh em cookie httpOnly), interceptor renova em 401.
- Dark mode default com tokens preparados para light mode futuro.

## 10. Deploy & Infraestrutura (Railway)

Reaproveitar a lógica do `BasketRandomizerApp`:
- **`docker-compose.yml`** dev: `db` (postgres:16-alpine) + `api` (FastAPI, volume-mounted, hot-reload) + `web` (Next.js dev). Redis **opcional**.
- **`backend/Dockerfile`**: `python:3.12-slim`, `pip install`, `alembic upgrade head` + seed, `uvicorn`.
- **`frontend/Dockerfile`**: `node:22-alpine`, `npm ci`, `npm run build`, `npm run start -- -p $PORT`.
- **Railway:** 2 serviços (`api`, `web`) + Postgres; secrets via env (`MASTER_KEY`, `GOOGLE_CLIENT_ID/SECRET`, `JWT_SECRET`, `DATABASE_URL`, `TAVILY_API_KEY`).

## 11. Fases de Implementação

| Fase | Entrega | MVP? |
|---|---|---|
| **0. Scaffold** | Git init, monorepo, docker-compose, configs base, Dockerfiles | ✅ |
| **1. Dados** | Models + Alembic + seed setores (12 B3) e perguntas + `sector_mapper` | ✅ |
| **2. Auth** | Google OAuth → JWT, `me`, middleware | ✅ |
| **3. API Keys** | CRUD com criptografia Fernet + hints | ✅ |
| **4. Web Search** | Serviço Tavily com hints de domínio RI | ✅ |
| **5. Agente** | System prompt + tool spec + orquestração + LLM (OpenAI/DeepSeek) | ✅ |
| **6. Chat** | Endpoint SSE streaming + conversations/messages | ✅ |
| **7. FE Login** | Página `/login` + sessão JWT + interceptor refresh | ✅ |
| **8. FE Chat** | Página `/` com streaming e histórico | ✅ |
| **9. FE Perguntas** | Tabela `@tanstack/react-table` + CRUD otimista | — |
| **10. Deploy** | Config Railway + env + healthchecks | — |

**MVP = fases 0–8** (login + chat funcionando de ponta a ponta com busca real). Fases 9–10 completam o produto.

## 12. Testes

- **Backend (pytest + httpx/async):** unit de `encryption` (roundtrip Fernet, nunca plaintext), `sector_mapper`, `agent` (system prompt contém diretriz de não-alucinar + tool Tavily; respostas com citação), endpoints (auth, questions, api-keys não retornam plaintext). Integração com Postgres real, mock do Tavily/LLM fora do sistema sob teste.
- **Frontend:** `tsc --noEmit`, testes do update otimista (mutation + rollback).
- **E2E (smoke):** login → "BBAS3" → resposta com citação.

## 13. Riscos & Fora de Escopo

- **Riscos:** variação de formato dos sites de RI (mitigação: Tavily + hints + fallback); custo/rate-limit das LLMs (rate-limit por usuário, cache).
- **Fora de escopo (v1):** light mode (só tokens), multi-idioma, multi-tenant/orgs, billing, exportação, banco próprio de empresas (o agente descobre via busca).
