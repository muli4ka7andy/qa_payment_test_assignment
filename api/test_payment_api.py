import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor

from api.api_client import PaymentApiClient, PaymentDataFactory


class PaymentApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = PaymentApiClient()

    def test_health(self):
        status, body = self.client.request("GET", "/health")
        self.assertEqual(status, 200)
        self.assertEqual(body, {"status": "ok"})

    def test_get_created_payment_by_id(self):
        body, headers = PaymentDataFactory.payment()
        create_status, created = self.client.request("POST", "/v1/payments", body, headers)
        status, payment = self.client.request(
            "GET", "/v1/payments/" + created["payment_id"]
        )

        self.assertEqual(create_status, 201)
        self.assertEqual(status, 200)
        self.assertEqual(payment, created)

    def test_get_unknown_payment_returns_not_found(self):
        status, _ = self.client.request("GET", "/v1/payments/P-does-not-exist")
        self.assertEqual(status, 404)

    def test_same_key_and_body_returns_same_payment(self):
        body, headers = PaymentDataFactory.payment()
        first_status, first = self.client.request("POST", "/v1/payments", body, headers)
        second_status, second = self.client.request("POST", "/v1/payments", body, headers)

        self.assertEqual(first_status, 201)
        self.assertEqual(second_status, 200)
        self.assertEqual(second["payment_id"], first["payment_id"])
        status, debug = self.client.request(
            "GET", "/debug/payments?beneficiary_ref=" + body["beneficiary_ref"]
        )
        self.assertEqual(status, 200)
        self.assertEqual(debug["count"], 1)

    def test_same_key_and_different_body_is_conflict(self):
        body, headers = PaymentDataFactory.payment()
        status, _ = self.client.request("POST", "/v1/payments", body, headers)
        self.assertEqual(status, 201)

        changed_body = dict(body, amount=body["amount"] + 1)
        status, error = self.client.request("POST", "/v1/payments", changed_body, headers)
        _, debug = self.client.request(
            "GET", "/debug/payments?beneficiary_ref=" + body["beneficiary_ref"]
        )
        self.assertEqual((status, debug["count"]), (409, 1), error)

    def test_same_key_and_any_changed_field_is_conflict(self):
        changed_bodies = (
            {"corridor": "USD/THB"},
            {"currency": "USD"},
            {"beneficiary_ref": "qa-other-beneficiary"},
        )
        for change in changed_bodies:
            with self.subTest(change=change):
                body, headers = PaymentDataFactory.payment()
                create_status, _ = self.client.request("POST", "/v1/payments", body, headers)
                changed_body = dict(body, **change)
                status, _ = self.client.request(
                    "POST", "/v1/payments", changed_body, headers
                )
                self.assertEqual(create_status, 201)
                self.assertEqual(status, 409)

    def test_same_key_with_extra_field_is_conflict(self):
        body, headers = PaymentDataFactory.payment()
        create_status, _ = self.client.request("POST", "/v1/payments", body, headers)
        changed_body = dict(body, extra_field="must-not-be-ignored")
        status, _ = self.client.request("POST", "/v1/payments", changed_body, headers)
        self.assertEqual(create_status, 201)
        self.assertEqual(status, 409)

    def test_different_keys_create_different_payments(self):
        body, first_headers = PaymentDataFactory.payment()
        _, second_headers = PaymentDataFactory.payment(ref=body["beneficiary_ref"])
        first_status, first = self.client.request("POST", "/v1/payments", body, first_headers)
        second_status, second = self.client.request("POST", "/v1/payments", body, second_headers)

        self.assertEqual(first_status, 201)
        self.assertEqual(second_status, 201)
        self.assertNotEqual(first["payment_id"], second["payment_id"])
        status, debug = self.client.request(
            "GET", "/debug/payments?beneficiary_ref=" + body["beneficiary_ref"]
        )
        self.assertEqual(status, 200)
        self.assertEqual(debug["count"], 2)

    def test_retry_after_unknown_result_does_not_create_second_payment(self):
        body, headers = PaymentDataFactory.payment()
        failed_status, _ = self.client.request(
            "POST",
            "/v1/payments",
            body,
            dict(headers, **{"X-Simulate": "fail-after-create"}),
        )
        retry_status, retry = self.client.request("POST", "/v1/payments", body, headers)
        status, debug = self.client.request(
            "GET", "/debug/payments?beneficiary_ref=" + body["beneficiary_ref"]
        )

        self.assertEqual(failed_status, 500)
        self.assertEqual(status, 200)
        self.assertEqual((retry_status, debug["count"]), (200, 1))
        self.assertEqual(retry["beneficiary_ref"], body["beneficiary_ref"])

    def test_missing_idempotency_key_is_bad_request(self):
        body, _ = PaymentDataFactory.payment()
        status, _ = self.client.request("POST", "/v1/payments", body)
        self.assertEqual(status, 400)

    def test_empty_or_whitespace_idempotency_key_is_bad_request(self):
        body, _ = PaymentDataFactory.payment()
        for key in ("", "   "):
            with self.subTest(key=repr(key)):
                status, _ = self.client.request(
                    "POST", "/v1/payments", body, {"Idempotency-Key": key}
                )
                self.assertEqual(status, 400)

    def test_zero_and_negative_amount_are_unprocessable(self):
        for amount in (0, -1):
            with self.subTest(amount=amount):
                body, headers = PaymentDataFactory.payment(amount=amount)
                status, _ = self.client.request("POST", "/v1/payments", body, headers)
                self.assertEqual(status, 422)

    def test_unsupported_currency_is_unprocessable(self):
        body, headers = PaymentDataFactory.payment(currency="GBP")
        status, _ = self.client.request("POST", "/v1/payments", body, headers)
        self.assertEqual(status, 422)

    def test_allowed_currencies_are_accepted(self):
        for currency in ("RUB", "USD", "THB"):
            with self.subTest(currency=currency):
                body, headers = PaymentDataFactory.payment(currency=currency)
                status, response = self.client.request("POST", "/v1/payments", body, headers)
                self.assertEqual(status, 201)
                self.assertEqual(response["currency"], currency)

    def test_invalid_json_returns_unprocessable(self):
        status, _ = self.client.request(
            "POST",
            "/v1/payments",
            "{invalid-json",
            {"Idempotency-Key": "key-" + uuid.uuid4().hex},
        )
        self.assertEqual(status, 422)

    def test_null_json_body_returns_unprocessable(self):
        status, _ = self.client.request(
            "POST",
            "/v1/payments",
            "null",
            {"Idempotency-Key": "key-" + uuid.uuid4().hex},
        )
        self.assertEqual(status, 422)

    def test_missing_required_fields_are_unprocessable(self):
        body, headers = PaymentDataFactory.payment()
        for field in ("corridor", "amount", "currency", "beneficiary_ref"):
            with self.subTest(field=field):
                invalid_body = dict(body)
                del invalid_body[field]
                status, _ = self.client.request(
                    "POST", "/v1/payments", invalid_body, dict(headers, **{
                        "Idempotency-Key": "key-" + uuid.uuid4().hex
                    })
                )
                self.assertEqual(status, 422)

    def test_invalid_amount_type_is_unprocessable(self):
        for amount in ("100000", None, True):
            with self.subTest(amount=amount):
                body, headers = PaymentDataFactory.payment(amount=amount)
                status, _ = self.client.request("POST", "/v1/payments", body, headers)
                self.assertEqual(status, 422)

    def test_fractional_and_large_amounts_are_accepted(self):
        for amount in (0.01, 10**18):
            with self.subTest(amount=amount):
                body, headers = PaymentDataFactory.payment(amount=amount)
                status, response = self.client.request("POST", "/v1/payments", body, headers)
                self.assertEqual(status, 201)
                self.assertEqual(response["amount"], amount)

    def test_empty_beneficiary_ref_is_unprocessable(self):
        body, headers = PaymentDataFactory.payment(ref="")
        status, _ = self.client.request("POST", "/v1/payments", body, headers)
        self.assertEqual(status, 422)

    def test_unknown_endpoints_return_not_found(self):
        get_status, _ = self.client.request("GET", "/v1/unknown")
        post_status, _ = self.client.request("POST", "/v1/unknown", {})
        self.assertEqual(get_status, 404)
        self.assertEqual(post_status, 404)

    def test_concurrent_requests_with_same_key_create_one_payment(self):
        body, headers = PaymentDataFactory.payment()

        def send_request(_):
            return self.client.request("POST", "/v1/payments", body, headers)[0]

        with ThreadPoolExecutor(max_workers=10) as executor:
            statuses = list(executor.map(send_request, range(10)))

        status, debug = self.client.request(
            "GET", "/debug/payments?beneficiary_ref=" + body["beneficiary_ref"]
        )
        self.assertEqual(status, 200)
        self.assertEqual(statuses.count(201), 1, statuses)
        self.assertEqual(statuses.count(200), 9, statuses)
        self.assertEqual(debug["count"], 1)

    def test_debug_endpoint_requires_beneficiary_ref(self):
        status, _ = self.client.request("GET", "/debug/payments")
        self.assertEqual(status, 400)


if __name__ == "__main__":
    unittest.main()