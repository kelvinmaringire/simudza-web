from __future__ import annotations

import hashlib
import hmac
import uuid

import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class PaystackError(Exception):
    pass


def _secret_key():
    key = getattr(settings, "PAYSTACK_SECRET_KEY", "")
    if not key:
        raise ImproperlyConfigured("Paystack secret key is not configured.")
    return key


def paystack_configured():
    return bool(
        getattr(settings, "PAYSTACK_SECRET_KEY", "")
        and getattr(settings, "PAYSTACK_PUBLIC_KEY", "")
    )


def generate_reference():
    return f"sim-{uuid.uuid4().hex}"


def get_currency():
    from marketplace.settings import get_marketplace_currency

    return get_marketplace_currency()


def initialize_transaction(*, email, amount_cents, reference, callback_url, metadata=None):
    payload = {
        "email": email,
        "amount": int(amount_cents),
        "reference": reference,
        "callback_url": callback_url,
        "currency": get_currency(),
    }
    if metadata:
        payload["metadata"] = metadata
    response = requests.post(
        "https://api.paystack.co/transaction/initialize",
        json=payload,
        headers={
            "Authorization": f"Bearer {_secret_key()}",
            "Content-Type": "application/json",
        },
        timeout=30,
    )
    data = response.json()
    if not response.ok or not data.get("status"):
        message = data.get("message") or "Paystack initialize failed."
        raise PaystackError(message)
    return data["data"]


def verify_transaction(reference):
    response = requests.get(
        f"https://api.paystack.co/transaction/verify/{reference}",
        headers={"Authorization": f"Bearer {_secret_key()}"},
        timeout=30,
    )
    data = response.json()
    if not response.ok or not data.get("status"):
        message = data.get("message") or "Paystack verify failed."
        raise PaystackError(message)
    return data["data"]


def signature_valid(raw_body: bytes, signature_header: str) -> bool:
    if not signature_header:
        return False
    digest = hmac.new(
        _secret_key().encode("utf-8"),
        raw_body,
        hashlib.sha512,
    ).hexdigest()
    return hmac.compare_digest(digest, signature_header)
