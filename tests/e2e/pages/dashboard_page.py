from playwright.sync_api import Locator, Page


class DashboardPage:
    def __init__(self, page: Page) -> None:
        self.page = page

    def open(self) -> None:
        self.page.goto("/")

    @property
    def empty_state(self) -> Locator:
        return self.page.get_by_test_id("empty-state")

    @property
    def dark_mode_toggle(self) -> Locator:
        return self.page.get_by_role("button", name="Toggle dark mode")
