import json
import logging
import os
import uuid
from http.client import HTTPConnection


LOGGER = logging.getLogger("payment_api_tests")
logging.basicConfig(
    level=os.environ.get("PAYMENT_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)


class PaymentApiClient:
    """Тонкая обёртка над HTTP API без знания внутренностей sandbox."""

    def __init__(self, base_url=None):
        self.base_url = base_url or os.environ.get("PAYMENT_BASE_URL", "127.0.0.1:8080")

    def request(self, method, path, body=None, headers=None):
        connection = HTTPConnection(self.base_url, timeout=5)
        request_body = (
            body
            if isinstance(body, str)
            else None if body is None else json.dumps(body)
        )
        request_headers = {"Content-Type": "application/json"}
        request_headers.update(headers or {})
        LOGGER.info(
            "REQUEST %s %s body=%s idempotency_key=%r simulate=%r",
            method,
            path,
            request_body,
            request_headers.get("Idempotency-Key"),
            request_headers.get("X-Simulate"),
        )
        connection.request(method, path, request_body, request_headers)
        response = connection.getresponse()
        raw_body = response.read()
        connection.close()
        parsed_body = json.loads(raw_body or b"{}")
        LOGGER.info("RESPONSE %s %s body=%s", response.status, path, parsed_body)
        return response.status, parsed_body


class PaymentDataFactory:
    """Object Mother для валидного платежа и уникальных тестовых идентификаторов."""

    @staticmethod
    def payment(key=None, ref=None, **overrides):
        body = {
            "corridor": "RUB/THB",
            "amount": 100000,
            "currency": "RUB",
            "beneficiary_ref": ref or "qa-" + uuid.uuid4().hex,
        }
        body.update(overrides)
        headers = {"Idempotency-Key": key or "key-" + uuid.uuid4().hex}
        return body, headers
