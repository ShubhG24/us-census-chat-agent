import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from contextlib import asynccontextmanager
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import get_settings
from app.rate_limit import limiter
from app.routers import chat
from app.services.snowflake import SnowflakeService
from app.services.session import session_manager
from app.services.guardrails import GuardrailsService
from app.services.agent import ChatAgent

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup and cleanup on shutdown."""
    settings = get_settings()
    
    snowflake_service = SnowflakeService(settings)
    app.state.snowflake = snowflake_service
    
    try:
        await snowflake_service.initialize()
        logger.info("Snowflake connection initialized successfully")
    except Exception as e:
        logger.warning(f"Failed to initialize Snowflake: {e}")
    
    import anthropic
    shared_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    guardrails = GuardrailsService(settings, client=shared_client)
    agent = ChatAgent(
        settings=settings,
        snowflake_service=snowflake_service,
        session_manager=session_manager,
        guardrails=guardrails,
        client=shared_client,
    )
    app.state.agent = agent
    
    yield
    
    if hasattr(app.state, 'snowflake'):
        app.state.snowflake.close()


app = FastAPI(
    title="US Census Chat Agent",
    description="A chat agent that answers natural language questions about US population data",
    version="1.0.0",
    lifespan=lifespan
)

app.state.limiter = limiter


def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please wait a moment and try again."},
    )


app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)

app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api", tags=["chat"])


def _timed_check(fn) -> tuple[bool, float]:
    """Run a boolean check and return (result, elapsed_ms)."""
    t0 = time.perf_counter()
    try:
        ok = fn()
    except Exception:
        ok = False
    return ok, round((time.perf_counter() - t0) * 1000, 1)


_TEMPLATE_DIR = Path(__file__).parent / "templates"
_status_template: str | None = None


def _load_status_template() -> str:
    global _status_template
    if _status_template is None:
        _status_template = (_TEMPLATE_DIR / "status.html").read_text()
    return _status_template


@app.get("/health")
@limiter.limit("30/minute")
async def health_check(request: Request):
    """Health check endpoint - returns HTML status page or JSON based on Accept header."""
    sf = getattr(request.app.state, "snowflake", None)
    snowflake_ok, snowflake_ms = _timed_check(lambda: sf.is_healthy if sf else False)

    anthropic_ok, anthropic_ms = _timed_check(
        lambda: bool(get_settings().anthropic_api_key and str(get_settings().anthropic_api_key).strip())
    )

    api_ok = True
    api_ms = 0.0
    all_ok = api_ok and snowflake_ok and anthropic_ok
    checked_at = datetime.now(timezone.utc).isoformat()

    accept = request.headers.get("accept", "")
    if "application/json" in accept or "text/html" not in accept:
        return {
            "status": "healthy" if all_ok else "degraded",
            "checked_at": checked_at,
            "service": "us-census-chat-agent",
            "components": {
                "api": {"healthy": api_ok, "response_time_ms": api_ms},
                "snowflake": {"healthy": snowflake_ok, "response_time_ms": snowflake_ms},
                "anthropic": {"healthy": anthropic_ok, "response_time_ms": anthropic_ms},
            },
        }

    initial_data = json.dumps({
        "status": "healthy" if all_ok else "degraded",
        "checked_at": checked_at,
        "components": {
            "api": {"healthy": api_ok, "response_time_ms": api_ms},
            "snowflake": {"healthy": snowflake_ok, "response_time_ms": snowflake_ms},
            "anthropic": {"healthy": anthropic_ok, "response_time_ms": anthropic_ms},
        },
    })

    template = _load_status_template()
    html = template.replace("{{INITIAL_DATA}}", initial_data)
    return HTMLResponse(content=html)


STATIC_DIR = Path(__file__).parent.parent / "static"

if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")
    
    @app.get("/{full_path:path}")
    async def serve_frontend(request: Request, full_path: str):
        """Serve frontend for all non-API routes."""
        file_path = STATIC_DIR / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(STATIC_DIR / "index.html")
else:
    @app.get("/")
    async def root():
        """Root endpoint with API information."""
        return {
            "message": "US Census Chat Agent API",
            "docs": "/docs",
            "health": "/health"
        }
