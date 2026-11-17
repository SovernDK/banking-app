import re

from playwright.sync_api import Locator, Page


class DashboardPage:
    def __init__(self, page: Page) -> None:
        self.page = page

    def open(self, query: str = "") -> None:
        self.page.goto(f"/{query}")

    def connect_bank(self) -> None:
        self.connect_button.click()

    def select_period(self, label: str) -> None:
        self.period_filter.get_by_role("button", name=label).click()

    def category_select(self, counterparty: str) -> Locator:
        return self.page.get_by_label(f"Category for {counterparty}", exact=True)

    def assign_category(self, counterparty: str, category: str) -> None:
        self.category_select(counterparty).click()
        self.page.get_by_role("option", name=category, exact=True).click()

    def create_category(self, counterparty: str, category: str) -> None:
        self.category_select(counterparty).click()
        self.page.keyboard.type(category)
        self.page.keyboard.press("Enter")

    def choose_language(self, label: str) -> None:
        self.language_picker.click()
        self.page.get_by_role("option", name=label, exact=True).click()

    def open_settings(self) -> None:
        self.settings_button.click()

    def box_toggle(self, action: str, box: str) -> Locator:
        return self.settings_dialog.get_by_role("button", name=f'{action} "{box}"', exact=True)

    def expand(self, box: str) -> None:
        self.box_toggle("Expand", box).click()

    def close_settings(self) -> None:
        self.settings_dialog.get_by_role("button", name="Done").click()

    def category_name_field(self, name: str) -> Locator:
        return self.page.get_by_label(f"Name of {name}", exact=True)

    def rename_category(self, name: str, new_name: str) -> None:
        field = self.category_name_field(name)
        field.fill(new_name)
        field.press("Enter")

    def delete_category(self, name: str) -> None:
        self.page.get_by_role("button", name=f"Delete {name}", exact=True).click()

    def confirm_delete(self) -> None:
        self.page.get_by_test_id("confirm-delete").click()

    def select_comparison(self, label: str) -> None:
        self.comparison_filter.get_by_role("button", name=label).click()

    def search_counterparties(self, text: str) -> None:
        self.counterparty_filter.click()
        self.page.keyboard.type(text)

    def filter_by_counterparty(self, name: str) -> None:
        self.search_counterparties(name)
        self.page.get_by_role("option", name=name, exact=True).click()

    def filter_by_category(self, name: str) -> None:
        self.category_filter.click()
        self.page.get_by_role("option", name=name, exact=True).click()

    def clear_filters(self) -> None:
        self.clear_filters_button.click()

    def legend_entry(self, legend: Locator, label: str) -> Locator:
        return legend.get_by_role("listitem").filter(has=self.page.get_by_text(label, exact=True))

    def scroll_position(self) -> int:
        return self.page.evaluate("window.scrollY")

    def dialog_scroll_position(self) -> int:
        return self.settings_dialog.evaluate("card => card.scrollTop")

    @property
    def counterparties_legend(self) -> Locator:
        return self.page.get_by_role("list", name="Counterparties")

    @property
    def categories_legend(self) -> Locator:
        return self.page.get_by_role("list", name="Categories")

    @property
    def counterparties(self) -> Locator:
        return self.page.get_by_test_id("counterparties")

    @property
    def settings_button(self) -> Locator:
        return self.page.get_by_role("button", name="Settings", exact=True)

    @property
    def settings_dialog(self) -> Locator:
        return self.page.get_by_test_id("settings-dialog")

    @property
    def categories_list(self) -> Locator:
        return self.page.get_by_test_id("categories-list")

    @property
    def empty_state(self) -> Locator:
        return self.page.get_by_test_id("empty-state")

    @property
    def language_picker(self) -> Locator:
        return self.page.get_by_test_id("language")

    @property
    def dark_mode_toggle(self) -> Locator:
        return self.page.get_by_role("button", name="Toggle dark mode")

    @property
    def connect_button(self) -> Locator:
        return self.page.get_by_test_id("connect-bank")

    @property
    def error(self) -> Locator:
        return self.page.get_by_role("alert")

    @property
    def period_filter(self) -> Locator:
        return self.page.get_by_test_id("period-filter")

    @property
    def spending_chart(self) -> Locator:
        return self.page.get_by_test_id("spending-chart")

    @property
    def total(self) -> Locator:
        return self.page.get_by_test_id("total")

    @property
    def total_label(self) -> Locator:
        return self.page.get_by_test_id("total-label")

    @property
    def total_delta(self) -> Locator:
        return self.page.get_by_test_id("total-delta")

    @property
    def comparison_filter(self) -> Locator:
        return self.page.get_by_test_id("comparison-filter")

    @property
    def spending_heading(self) -> Locator:
        return self.page.get_by_role("heading", name=re.compile(r"^Spending per day"))

    @property
    def counterparty_filter(self) -> Locator:
        return self.page.get_by_test_id("counterparty-filter")

    @property
    def category_filter(self) -> Locator:
        return self.page.get_by_test_id("category-filter")

    @property
    def filter_options(self) -> Locator:
        return self.page.get_by_role("option")

    @property
    def clear_filters_button(self) -> Locator:
        return self.page.get_by_role("button", name="Clear filters")
