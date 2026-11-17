from nicegui import ui


def alert(message: str, *, testid: str = "bank-error") -> None:
    with (
        ui.row()
        .classes("yiji-alert w-full items-center gap-2 rounded-xl p-4 text-sm")
        .props(f'role="alert" data-testid="{testid}"')
    ):
        ui.icon("warning").props('aria-hidden="true"')
        ui.label(message)
