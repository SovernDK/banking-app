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

    def open_manage_categories(self) -> None:
        self.page.get_by_test_id("manage-categories").click()

    def rename_category(self, name: str, new_name: str) -> None:
        field = self.page.get_by_label(f"Name of {name}", exact=True)
        field.fill(new_name)
        field.press("Enter")

    def delete_category(self, name: str) -> None:
        self.page.get_by_role("button", name=f"Delete {name}", exact=True).click()

    def confirm_delete(self) -> None:
        self.page.get_by_test_id("confirm-delete").click()

    def legend_entry(self, legend: Locator, label: str) -> Locator:
        return legend.get_by_role("listitem").filter(has=self.page.get_by_text(label, exact=True))

    def scroll_position(self) -> int:
        return self.page.evaluate("window.scrollY")

    @property
    def payment_methods_legend(self) -> Locator:
        return self.page.get_by_role("list", name="Payment methods")

    @property
    def categories_legend(self) -> Locator:
        return self.page.get_by_role("list", name="Categories")

    @property
    def counterparties(self) -> Locator:
        return self.page.get_by_test_id("counterparties")

    @property
    def empty_state(self) -> Locator:
        return self.page.get_by_test_id("empty-state")

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
