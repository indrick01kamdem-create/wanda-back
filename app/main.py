from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import Base, engine
from app.routers import (
    admin,
    auth,
    drivers,
    notifications,
    payments,
    rides,
    settings as settings_router,
    wallet,
)
from app.tasks.scheduler import start_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Crée les tables au boot (phase dev). Les migrations Alembic restent
    # la méthode officielle en production.
    if settings.app_env in ("development", "test"):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    start_scheduler()
    logger.info("Wanda API démarrée (env=%s)", settings.app_env)
    yield


app = FastAPI(
    title="Wanda API",
    version=settings.app_version,
    description="Backend de l'application de transport Wanda (Cameroon).",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(payments.router, prefix="/api/v1")
app.include_router(rides.router, prefix="/api/v1")
app.include_router(drivers.router, prefix="/api/v1")
app.include_router(wallet.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(notifications.router, prefix="/api/v1")
app.include_router(settings_router.router, prefix="/api/v1")


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok", "app": settings.app_name, "version": settings.app_version}
