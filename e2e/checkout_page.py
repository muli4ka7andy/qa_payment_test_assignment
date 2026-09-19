from pathlib import Path

from playwright.sync_api import Page


class CheckoutPage:
    def __init__(self, page: Page):
        self.page = page
        self.file_url = (Path(__file__).parent / "checkout.html").resolve().as_uri()

    def open(self):
        self.page.goto(self.file_url)

    def fill_payment(self, card_number, expiry, cvc, amount):
        self.page.get_by_label("Card number").fill(card_number)
        self.page.get_by_label("Expiry").fill(expiry)
        self.page.get_by_label("CVC").fill(cvc)
        self.page.get_by_label("Amount").fill(amount)

    def submit(self):
        self.page.get_by_role("button", name="Pay").click()

    def confirmation(self):
        return self.page.get_by_test_id("confirmation-page")

    def validation_error(self):
        return self.page.get_by_test_id("validation-error")
