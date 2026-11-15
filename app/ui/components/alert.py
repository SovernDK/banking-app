from nicegui import ui


def alert(message: str) -> None:
    with (
        ui.row()
        .classes("yiji-alert w-full items-center gap-2 rounded-xl p-4 text-sm")
        .props('role="alert" data-testid="bank-error"')
    ):
        ui.icon("warning").props('aria-hidden="true"')
        ui.label(message)
