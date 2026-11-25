from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.audio_routes import audio_router
from app.api.avatar_routes import avatar_router
from app.api.routes import router
from app.api.visual_routes import visual_router
from app.core.config import settings
from app.core.logging import logger


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "Self-hosted AI Video Studio backend for vertical 9:16 (1080x1920) "
            "top/bottom 50/50 educational videos."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.FRONTEND_URL, "http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "type": type(exc).__name__},
        )

    app.include_router(router)
    app.include_router(audio_router)
    app.include_router(avatar_router)
    app.include_router(visual_router)
    return app


app = create_app()
