# JustAbackEnd

Production-ready **FastAPI** backend template with **LangChain** and **Google Gemini**, structured for AI applications. Includes health checks, request logging, correlation IDs, and optional LangSmith tracing.

---

## Features

- **FastAPI** with ORJSON responses, CORS, and centralized exception handling
- **LLM integration** via LangChain (Google Gemini); chat completion endpoint at `/api/v1/chat`
- **Health endpoints**: `/health`, `/health/live`, `/health/ready` (readiness checks LLM init)
- **Structured logging** (JSON logs, optional file rotation, optional webhook alerts on errors)
- **Request middleware**: correlation ID (`Request-ID`), request logging
- **Pydantic Settings** from `.env` (API keys, model name, LangSmith, webhook URL)
- **Docker**: multi-stage build with **uv**, non-root user, Gunicorn + Uvicorn workers

---

## Tech stack

| Layer        | Technology                    |
|-------------|-------------------------------|
| Framework   | FastAPI                       |
| Server      | Uvicorn (dev) / Gunicorn+Uvicorn (prod) |
| LLM         | LangChain + `langchain-google-genai` (Gemini) |
| Config      | pydantic-settings, `.env`     |
| Package mgr | **uv**                        |
| Runtime     | Python 3.13+                  |

---

## Project structure (high level)

```
src/JustAbackEnd/
├── main.py              # Entrypoint: run_app() for Gunicorn, run_app_locally() for dev
├── bootstrap/           # App factory, lifespan (settings → logging → runtime → app.state)
├── core/                # Settings, constants, logger, runtime (LLM init/teardown)
├── api/                 # Routers (health, llm), middleware, exceptions, schemas, dependencies
├── ai_engine/           # Model init (LangChain), prompts
├── services/            # Business logic (e.g. llm_service.chat_completion)
└── utils/               # Helpers (e.g. setup_logging)
```

---

## Prerequisites

- **Git**
- **Python 3.13+**
- **uv** ([install](https://docs.astral.sh/uv/getting-started/installation/))
- **Docker** (optional, for containerized run)
- **Gemini API key** (required for LLM)

---

## Quick start (local)

### 1. Clone and enter the repo

```bash
git clone https://github.com/balalaika-tools/fastapi-ai-backend-template.git
cd fastapi-ai-backend-template
```

### 2. Create and edit `.env`

```bash
cp .env_example .env
# Edit .env and add your API keys (at least GEMINI_API_KEY)
```

Required: `GEMINI_API_KEY`. Optional: `LANGSMITH_*`, `MODEL_NAME`, `TEMPERATURE`, `WEBHOOK_URL`.

### 3. Install dependencies with uv

```bash
uv sync
```

### 4. Run locally (development)

```bash
uv run python -m JustAbackEnd.main
```

App runs at **http://0.0.0.0:6757** with reload. Docs: http://0.0.0.0:6757/docs.

---

## Run with Docker (production-style)

Build the image and run the container, **injecting your `.env` file** so the app gets `GEMINI_API_KEY` and other variables.

### 1. Prepare environment

```bash
git clone https://github.com/balalaika-tools/fastapi-ai-backend-template.git
cd fastapi-ai-backend-template
cp .env_example .env
# Edit .env and add your API keys
```

### 2. Build the image

```bash
docker build -t justabackend .
```

### 3. Run the container with `.env` injected

```bash
docker run -p 8000:8000 --env-file .env justabackend
```

- **`--env-file .env`** passes all variables from `.env` into the container (recommended for local/dev).  
- For production, prefer secrets or your orchestrator’s env config instead of committing `.env`.

App is available at **http://localhost:8000**. Docs: http://localhost:8000/docs.

### Optional: name the container and run in background

```bash
docker run -d -p 8000:8000 --name justabackend-app --env-file .env justabackend
docker logs -f justabackend-app
```

---

## API overview

| Method | Path              | Description                    |
|--------|-------------------|--------------------------------|
| GET    | `/health`         | Full health (version, platform, services) |
| GET    | `/health/live`    | Liveness probe                 |
| GET    | `/health/ready`   | Readiness (e.g. LLM initialized) |
| POST   | `/api/v1/chat`    | Chat completion (body: `prompt`, optional `session_id`) |

---

## Environment variables

| Variable              | Required | Description                          |
|-----------------------|----------|--------------------------------------|
| `GEMINI_API_KEY`      | Yes      | Google Gemini API key                |
| `LANGSMITH_TRACING`   | No       | `true` to enable LangSmith           |
| `LANGSMITH_API_KEY`   | No       | LangSmith API key                    |
| `LANGSMITH_PROJECT`   | No       | LangSmith project name (e.g. `stock-agent`) |
| `MODEL_NAME`          | No       | e.g. `google_genai:gemini-2.5-flash` |
| `TEMPERATURE`         | No       | Model temperature (default `0`)       |
| `WEBHOOK_URL`         | No       | Optional URL for error log alerts    |

---
