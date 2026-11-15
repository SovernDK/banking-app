from fastapi import FastAPI
from nicegui import ui

from app.api.bank import create_router as create_bank_router
from app.api.health import router as health_router
from app.config import get_settings
from app.ui.pages import dashboard


def create_app() -> FastAPI:
    settings = get_settings()
    fastapi_app = FastAPI(title=settings.app_title)
    fastapi_app.include_router(health_router)
    fastapi_app.include_router(create_bank_router(settings.local_callback_path()))
    dashboard.register()
    ui.run_with(fastapi_app, title=settings.app_title, storage_secret=settings.storage_secret)
    return fastapi_app


app = create_app()
