from collections.abc import Callable
from dataclasses import dataclass

from nicegui import ui
from nicegui.events import ValueChangeEventArguments

from app import texts
from app.i18n import Language
from app.spending_filter import ALL, SpendingFilter
from app.ui.components.ghost_button import ghost_button
from app.ui.palette import LIGHT

_ALL_VALUE = ""


@dataclass(frozen=True)
class CategoryOption:
    """`colour_slot` indexes the category colours; None draws the neutral grey."""

    id: str
    name: str
    colour_slot: int | None


def _swatch(option: CategoryOption) -> str:
    if option.colour_slot is None:
        return "var(--yiji-other-category)"
    return f"var(--yiji-category-{option.colour_slot % len(LIGHT.categories)})"


def _category_option_template(categories: list[CategoryOption]) -> str:
    # NiceGUI hands Quasar each option's position as its value, so the colours are looked up by
    # position. They are built here from CSS variable names only, never from user text.
    colours = ", ".join(["'transparent'", *(f"'{_swatch(option)}'" for option in categories)])
    return f"""
        <q-item v-bind="props.itemProps">
          <q-item-section side>
            <span class="inline-block w-3 h-3 rounded-sm"
                  :style="{{ backgroundColor: [{colours}][props.opt.value] }}"></span>
          </q-item-section>
          <q-item-section><q-item-label>{{{{ props.opt.label }}}}</q-item-label></q-item-section>
        </q-item>
    """


def _filter_select(
    options: dict[str, str],
    all_label: str,
    label: str,
    testid: str,
    on_change: Callable[[ValueChangeEventArguments], None],
    *,
    with_input: bool = False,
) -> ui.select:
    return (
        ui.select(
            {_ALL_VALUE: all_label, **options},
            value=_ALL_VALUE,
            label=label,
            with_input=with_input,
            on_change=on_change,
        )
        .classes("min-w-0 flex-1 sm:w-56 sm:flex-none")
        .props(f'dense outlined options-dense data-testid="{testid}"')
    )


class SpendingFilters:
    """Counterparty and category selects, one active at a time, plus a Clear filters button, on
    a row of their own that never wraps. `update_categories` changes the category options in
    place, so editing never moves the page."""

    def __init__(
        self,
        counterparties: list[str],
        categories: list[CategoryOption],
        value: SpendingFilter,
        on_change: Callable[[SpendingFilter], None],
        language: Language,
    ) -> None:
        self._all_label = texts.ALL(language)
        self._value = value
        self._on_change = on_change
        with ui.row().classes("w-full flex-nowrap items-center gap-2 sm:gap-4"):
            self._build(counterparties, language)
        self.update_categories(categories, value)

    def _build(self, counterparties: list[str], language: Language) -> None:
        self._counterparty = _filter_select(
            {name: name for name in counterparties},
            self._all_label,
            texts.COUNTERPARTY(language),
            "counterparty-filter",
            self._counterparty_changed,
            with_input=True,
        )
        self._category = _filter_select(
            {}, self._all_label, texts.CATEGORY(language), "category-filter", self._category_changed
        )
        self._clear = ghost_button(
            texts.CLEAR_FILTERS(language),
            self._cleared,
            icon="filter_alt_off",
            testid="clear-filters",
            icon_only_on_phones=True,
        ).classes("shrink-0")

    def update_categories(self, categories: list[CategoryOption], value: SpendingFilter) -> None:
        # Stored first so the change handler fired by `set_options` sees nothing new.
        self._value = value
        self._category.add_slot("option", _category_option_template(categories))
        self._category.set_options(
            {_ALL_VALUE: self._all_label, **{option.id: option.name for option in categories}},
            value=value.category_id or _ALL_VALUE,
        )
        self._show(value)

    def _counterparty_changed(self, event: ValueChangeEventArguments) -> None:
        if event.value:
            self._choose(SpendingFilter(counterparty=event.value))
        elif self._value.counterparty:
            self._choose(ALL)

    def _category_changed(self, event: ValueChangeEventArguments) -> None:
        if event.value:
            self._choose(SpendingFilter(category_id=event.value))
        elif self._value.category_id:
            self._choose(ALL)

    def _cleared(self) -> None:
        self._choose(ALL)

    def _choose(self, value: SpendingFilter) -> None:
        if value == self._value:
            return
        self._show(value)
        self._on_change(value)

    def _show(self, value: SpendingFilter) -> None:
        # Setting a select fires its change handler; the handlers see the new value already
        # stored and do nothing, so a choice reaches `on_change` once.
        self._value = value
        self._counterparty.set_value(value.counterparty or _ALL_VALUE)
        self._category.set_value(value.category_id or _ALL_VALUE)
        self._clear.set_enabled(value != ALL)
