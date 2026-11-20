from fastapi import FastAPI
from nicegui import ui

from app.api.bank import create_router as create_bank_router
from app.api.health import router as health_router
from app.config import Settings
from app.modules import build_modules
from app.ui.pages import dashboard


def create_app(settings: Settings) -> FastAPI:
    modules = build_modules(settings)
    fastapi_app = FastAPI(title=settings.app_title)
    fastapi_app.include_router(health_router)
    complete = modules.bank.service.complete if modules.bank else None
    fastapi_app.include_router(create_bank_router(complete, settings.local_callback_path()))
    dashboard.register(modules)
    ui.run_with(fastapi_app, title=settings.app_title, storage_secret=settings.storage_secret)
    return fastapi_app


app = create_app(Settings())
