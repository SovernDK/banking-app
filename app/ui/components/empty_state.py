from nicegui import ui


def empty_state(message: str) -> None:
    ui.label(message).classes("text-sm text-muted py-8 self-center").props(
        'data-testid="empty-state"'
    )
