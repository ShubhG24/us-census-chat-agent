# US Census Chat Agent

A natural language interface for querying US Census data, powered by Anthropic Claude and Snowflake.

**Live app** &rarr; https://censusai.up.railway.app/

https://github.com/user-attachments/assets/158eae7b-949a-4ffe-b8c3-6ebb8a23f831

## Overview

Ask questions about US population data in plain English. The agent translates natural language into SQL, executes it against Snowflake's US Open Census dataset, and returns interpreted results — all through a conversational chat interface.

### Example questions

- "What is the total population of California?"
- "Which state has the highest median household income?"
- "Compare the populations of New York and Florida"
- "How many households are renter-occupied vs owner-occupied in LA County?"
- "What are the top 10 states by poverty rate?"

## Features

- **Natural language to SQL** — Claude generates and executes SQL from plain English questions
- **Multi-turn conversations** — context is preserved across messages for follow-up questions
- **Streaming responses** — answers appear in real time as they're generated
- **Guardrails** — topic validation, SQL safety checks (SELECT-only), and prompt injection detection
- **Graceful error handling** — clear messages for ambiguous queries, timeouts, and unsupported questions
- **Dark/light mode** — theme toggle with full UI adaptation
- **Health monitoring** — `/health` endpoint with component-level status and response times

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        React Frontend                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │ ChatInterface│  │ MessageBubble│  │      InputBar          │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP / SSE
┌────────────────────────────▼────────────────────────────────────┐
│                      FastAPI Backend                            │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    Guardrails Layer                       │  │
│  │  • Topic validation (census-related only)                 │  │
│  │  • SQL safety checks (SELECT only, no injections)         │  │
│  │  • Output sanitization                                    │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                      Chat Agent                           │  │
│  │  • Context management (10 messages)                       │  │
│  │  • SQL generation via Claude                              │  │
│  │  • Result interpretation                                  │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                   Session Manager                         │  │
│  │  • In-memory session storage                              │  │
│  │  • 24-hour TTL with cleanup                               │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────┘
                             │
        ┌────────────────────┴────────────────────┐
        ▼                                         ▼
┌───────────────────┐                  ┌─────────────────────┐
│  Anthropic Claude  │                  │     Snowflake       │
│ (Claude Haiku 4.5) │                  │  US Open Census     │
└───────────────────┘                  └─────────────────────┘
```

## Technology stack


| Layer      | Technology                   | Why                                                          |
| ---------- | ---------------------------- | ------------------------------------------------------------ |
| Backend    | FastAPI (Python 3.11)        | Async support, native SSE streaming, type-safe with Pydantic |
| Frontend   | React 18 + TypeScript + Vite | Fast builds, type safety, modern DX                          |
| LLM        | Anthropic Claude Haiku 4.5   | Fast SQL generation, prompt caching for low latency          |
| Database   | Snowflake                    | Required data source (US Open Census dataset)                |
| Styling    | Tailwind CSS                 | Utility-first, rapid iteration                               |
| Deployment | Railway (Nixpacks)           | Git-push deploys, environment management, public URL         |


## Project structure

```
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, health endpoint, static file serving
│   │   ├── config.py            # Pydantic settings (env vars)
│   │   ├── rate_limit.py        # slowapi rate limiting
│   │   ├── routers/
│   │   │   └── chat.py          # /api/chat, /api/session, /api/schema endpoints
│   │   ├── services/
│   │   │   ├── agent.py         # Two-step LLM agent (SQL gen → result interpretation)
│   │   │   ├── guardrails.py    # Input validation, SQL safety, output sanitization
│   │   │   ├── session.py       # In-memory session store with TTL
│   │   │   └── snowflake.py     # Connection pool, schema cache, query execution
│   │   ├── prompts/
│   │   │   └── templates.py     # System prompt, schema docs, few-shot examples
│   │   └── templates/
│   │       └── status.html      # Health status page (auto-refreshing)
│   ├── tests/                   # 76 tests (guardrails, session, agent, API)
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── App.tsx              # Root component, theme, health polling
│   │   ├── components/          # ChatInterface, MessageBubble, InputBar, Sidebar, WelcomeScreen
│   │   ├── hooks/               # useChat (streaming), useConversations, useTheme
│   │   └── lib/
│   │       └── storage.ts       # localStorage persistence for conversations
│   ├── public/                  # Favicon, icons
│   ├── package.json
│   └── vite.config.ts
├── Dockerfile                   # Multi-stage build (frontend + backend)
├── nixpacks.toml                # Railway Nixpacks config
├── railway.json                 # Railway deploy settings
├── REFLECTION.md                # Design decisions, tradeoffs, and future improvements
└── README.md
```

## How it works

1. **User asks a question** in natural language
2. **Guardrails validate** the input (topic relevance, injection detection)
3. **Context is assembled** — system prompt with schema docs + conversation history
4. **Claude generates SQL** based on the question and schema
5. **SQL is validated** — SELECT-only, valid table references, no dangerous patterns
6. **Query executes** against Snowflake with a 30-second timeout
7. **Claude interprets** the raw results into a natural language answer
8. **Response streams** back to the user via SSE

## API endpoints


| Endpoint                    | Method | Description                                                          |
| --------------------------- | ------ | -------------------------------------------------------------------- |
| `/health`                   | GET    | Health/status page (HTML) or JSON probe (`Accept: application/json`) |
| `/api/chat/stream`          | POST   | Send a message and receive a streaming response                      |
| `/api/chat`                 | POST   | Send a message (non-streaming)                                       |
| `/api/session/new`          | POST   | Create a new session                                                 |
| `/api/session/{id}`         | GET    | Get session info                                                     |
| `/api/session/{id}/history` | GET    | Get conversation history                                             |
| `/api/session/{id}`         | DELETE | Delete a session                                                     |
| `/api/schema`               | GET    | Get database schema info                                             |
| `/api/welcome`              | GET    | Get welcome message                                                  |


## Testing

76 unit tests covering guardrails, session management, agent logic, and API integration.

```bash
cd backend
pip install -r requirements.txt
pytest
```

Test areas:

- **Guardrails** — input validation, SQL injection prevention, output sanitization
- **Session management** — creation, retrieval, TTL expiration, concurrent access
- **Agent logic** — message processing, SQL extraction, error handling
- **API integration** — endpoint responses, request validation, error codes

## Security

- **SQL injection prevention** — dedicated validation layer blocks non-SELECT/WITH queries
- **Prompt injection detection** — regex patterns + LLM-based topic validation
- **Output sanitization** — API keys and secrets are redacted before responses reach the client
- **Rate limiting** — 10 requests/min per IP on chat endpoints (via `slowapi`)
- **No write operations** — all database access is read-only

## Deployment

The app is deployed on **Railway** with Nixpacks. Frontend is built and served as static files by the FastAPI backend.

The app is configured for git-push deploys via `nixpacks.toml` and `railway.json`. Environment variables (`SNOWFLAKE_`*, `ANTHROPIC_API_KEY`) are set in the Railway dashboard. A root `Dockerfile` is also included for standalone container builds.

## License

MIT
