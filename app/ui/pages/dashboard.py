from nicegui import ui

from app.config import get_settings
from app.ui.components import empty_state, overview_band, page_shell


def register() -> None:
    @ui.page("/")
    def dashboard_page() -> None:
        with page_shell(get_settings().app_title), overview_band():
            ui.label("Overview").classes("text-2xl font-normal").props(
                'role="heading" aria-level="1"'
            )
            empty_state("No transactions yet. Connect a bank account to see your history.")
