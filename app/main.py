from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import uvicorn

from app.api.exception_handlers import add_exception_handlers
from app.api.routes import (
    assistant,
    auth,
    health,
    meetings,
    multimodal,
    recordings,
)
from app.core.config import settings
from app.core.logging import configure_logging
from app.core.middleware import RequestIDMiddleware
from app.infrastructure.llm.groq_provider import GroqLLMProvider
from app.web.routes import STATIC_DIRECTORY, router as web_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    timeout = httpx.Timeout(settings.groq.groq_timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout) as client:
        api_key = settings.groq.groq_api_key
        app.state.llm_provider = (
            GroqLLMProvider(
                client=client,
                api_key=api_key,
                model=settings.groq.groq_model,
                max_completion_tokens=(settings.groq.groq_max_completion_tokens),
                reasoning_effort=settings.groq.groq_reasoning_effort,
            )
            if api_key is not None and api_key.get_secret_value().strip()
            else None
        )
        yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Meetn Copilot",
        lifespan=lifespan,
    )

    # Middleware
    app.add_middleware(RequestIDMiddleware)

    # Exception Handlers
    add_exception_handlers(app)

    # Health probes are root-level deployment contracts. Keep the original
    # versioned paths as hidden compatibility aliases for existing callers.
    app.include_router(health.router)
    app.include_router(health.router, prefix="/api/v1", include_in_schema=False)
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(meetings.router)
    app.include_router(recordings.router)
    app.include_router(assistant.router)
    app.include_router(multimodal.router)
    app.mount(
        "/static",
        StaticFiles(directory=STATIC_DIRECTORY),
        name="static",
    )
    app.include_router(web_router)

    return app


app = create_app()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
