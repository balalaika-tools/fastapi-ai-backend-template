```md
backend/
├── bootstrap/                               # Application bootstrap & lifecycle orchestration (startup/shutdown)
│   ├── lifespan.py                          # FastAPI lifespan: initialize/close Settings, Logging, Container/Runtime, app.state
│   └── app_factory.py                       # create_app(): builds FastAPI app, attaches lifespan, registers API wiring
│
├── core/                                    # Cross-cutting, framework-agnostic primitives
│   ├── settings.py                          # Pydantic Settings (env/.env loading), validation, computed fields
│   ├── runtime.py                           # Runtime state container (formerly context.py): AppRuntime/AppContext, init/close services
│   ├── constants.py                         # Project-wide constants (logger names, defaults, limits)
│   ├── logging.py                           # Logging setup (configure_logging/shutdown_logging), formatters, handlers, correlation ID
│   └── exceptions.py                        # Custom error types raised by services/AI/DB layers (no HTTP status codes here)
│
├── api/                                     # FastAPI presentation layer (HTTP boundaries only)
│   ├── routers/                             # APIRouters (endpoints grouped by feature)
│   ├── middleware/                          # FastAPI/Starlette middleware (auth, request-id, timing, etc.)
│   ├── exceptions/                          # HTTP exception mapping: handlers, error response formatting, validation handlers
│   ├── dependencies/                        # FastAPI dependencies (get_runtime, get_settings, get_db_session, etc.)
│   ├── schemas/                             # API request/response Pydantic models (DTOs exposed over HTTP)
│   └── auth/                                # This folder hosts authentication/authorization components
│
├── ai_engine/                               # AI/LLM layer (agents, graphs, prompts, structured outputs) — formerly ai_core
│   ├── agents/                              # Agent builders/factories, tool wiring, policies
│   ├── graphs/                              # LangGraph/LangChain graphs, state machines, execution flows
│   ├── prompts/                             # Prompt templates, system prompts, prompt utilities
│   ├── tools/                               # Tool definitions & implementations (LLM-callable functions, MCP adapters, etc)
│   └── schemas/                             # AI-internal Pydantic models (structured outputs, tool inputs, internal DTOs)
│
├── db/                                      # Persistence layer (optional; add when you introduce a database)
│   ├── models/                              # ORM entities / DB models (SQLAlchemy/SQLModel/Tortoise, etc.)
│   ├── session.py                           # Engine + Session/Sessionmaker factory (how to create sessions; no app lifecycle here)
│   └── repositories/                        # Data access layer (queries, CRUD, unit-of-work patterns)
│
├── utils/                                   # Small shared utilities (pure helpers, no side effects)
│   ├── files.py                             # Path helpers, file IO helpers (optional split)
│   └── misc.py                              # Generic utilities (or keep a single utils.py)
│
├── services/                                # Application/use-case layer (business orchestration)
│   ├── stock_service.py                     # Example: orchestrates domain logic + repositories + AI calls
│   └── session_service.py                   # Example: session management, workflows, transactions
│
└── main.py                                  # ASGI entrypoint: `app = create_app()` (no side effects; gunicorn/uvicorn loads this)
```