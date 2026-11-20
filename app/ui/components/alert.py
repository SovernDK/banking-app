from nicegui import ui


class Alert:
    """A warning whose message `show` changes in place; None hides it."""

    def __init__(self, *, testid: str = "bank-error") -> None:
        with (
            ui.row()
            .classes("yiji-alert w-full items-center gap-2 rounded-xl p-4 text-sm")
            .props(f'role="alert" data-testid="{testid}"') as self._box
        ):
            ui.icon("warning").props('aria-hidden="true"')
            self._message = ui.label()

    def show(self, message: str | None) -> None:
        self._message.set_text(message or "")
        self._box.set_visibility(message is not None)


def alert(message: str, *, testid: str = "bank-error") -> None:
    Alert(testid=testid).show(message)
