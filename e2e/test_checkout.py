import os
import re
import unittest

from playwright.sync_api import Page, Playwright, expect, sync_playwright

from e2e.checkout_page import CheckoutPage


class CheckoutE2ETests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright: Playwright = sync_playwright().start()
        headless = os.environ.get("E2E_HEADLESS", "1") != "0"
        cls.browser = cls.playwright.chromium.launch(headless=headless)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.page: Page = self.browser.new_page()
        self.checkout = CheckoutPage(self.page)

    def tearDown(self):
        self.page.close()

    def test_user_completes_payment_and_sees_final_status(self):
        self.checkout.open()
        self.checkout.fill_payment("4111111111111111", "12/30", "123", "100000")
        self.checkout.submit()

        expect(self.page).to_have_url(re.compile(r"#confirmation$"))
        expect(self.checkout.confirmation()).to_be_visible()
        expect(self.page.get_by_test_id("payment-reference")).to_have_text("E2E-001")
        expect(self.page.get_by_test_id("final-status")).to_have_text("Succeeded")

    def test_empty_and_invalid_fields_block_submission(self):
        fields = {
            "Card number": "4111111111111111",
            "Expiry": "12/30",
            "CVC": "123",
            "Amount": "100000",
        }
        invalid_values = {
            "Card number": "411111111111111",
            "Expiry": "2026-12",
            "CVC": "1",
        }

        for field_name in fields:
            with self.subTest(empty_field=field_name):
                self.checkout.open()
                for label, value in fields.items():
                    if label != field_name:
                        self.page.get_by_label(label).fill(value)
                self.checkout.submit()
                expect(self.checkout.confirmation()).to_be_hidden()
                expect(self.checkout.validation_error()).to_be_visible()

        for field_name, invalid_value in invalid_values.items():
            with self.subTest(invalid_field=field_name):
                self.checkout.open()
                for label, value in fields.items():
                    self.page.get_by_label(label).fill(
                        invalid_value if label == field_name else value
                    )
                self.checkout.submit()
                expect(self.checkout.confirmation()).to_be_hidden()
                expect(self.checkout.validation_error()).to_be_visible()

        for invalid_amount in ("0", "-1", "0.99"):
            with self.subTest(invalid_amount=invalid_amount):
                self.checkout.open()
                for label, value in fields.items():
                    self.page.get_by_label(label).fill(
                        invalid_amount if label == "Amount" else value
                    )
                self.checkout.submit()
                expect(self.checkout.confirmation()).to_be_hidden()
                expect(self.checkout.validation_error()).to_be_visible()


if __name__ == "__main__":
    unittest.main(verbosity=2)
