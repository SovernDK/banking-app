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
