"""Versioned standard-rate usage calculations; never a provider invoice."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


PRICE_VERSION = "openai-standard-2026-11-04-v1"
# USD per million tokens for the standard API tier, not Batch/Fast/region pricing.
IMAGE_RATES = {"text_input": Decimal("5"), "image_input": Decimal("8"),
               "image_output": Decimal("30")}
TEXT_RATES = {"input": Decimal("0.10"), "cached_input": Decimal("0.01"),
              "output": Decimal("0.50")}


class PaidRequestError(RuntimeError):
    def __init__(self, message: str, *, request_id: str | None = None, usage: dict | None = None):
        super().__init__(message)
        self.request_id = request_id
        self.usage = usage


def _count(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def calculate(provider: str, model: str, usage: dict | None, *, direct_images: bool = False) -> tuple[str | None, str | None]:
    """Return (calculated USD, rate version), or unknown when usage/rate is incomplete."""
    if provider != "openai" or not isinstance(usage, dict):
        return None, None
    if direct_images and model in ("gpt-image-2.5-sunburst", "gpt-image-2.5-flare"):
        details = usage.get("input_tokens_details")
        if not isinstance(details, dict):
            return None, None
        text = _count(details.get("text_tokens"))
        image = _count(details.get("image_tokens"))
        output = _count(usage.get("output_tokens"))
        output_details = usage.get("output_tokens_details") or {}
        if not isinstance(output_details, dict) or _count(output_details.get("text_tokens", 0)) != 0:
            return None, None
        if None in (text, image, output) or text + image != usage.get("input_tokens"):
            return None, None
        amount = (text * IMAGE_RATES["text_input"] + image * IMAGE_RATES["image_input"]
                  + output * IMAGE_RATES["image_output"]) / Decimal(1_000_000)
    elif not direct_images and model == "gpt-6-luna":
        input_tokens = _count(usage.get("input_tokens"))
        output = _count(usage.get("output_tokens"))
        details = usage.get("input_tokens_details") or {}
        cached = _count(details.get("cached_tokens", 0)) if isinstance(details, dict) else None
        if None in (input_tokens, output, cached) or cached > input_tokens:
            return None, None
        amount = ((input_tokens - cached) * TEXT_RATES["input"]
                  + cached * TEXT_RATES["cached_input"] + output * TEXT_RATES["output"]) / Decimal(1_000_000)
    else:
        return None, None
    return str(amount.quantize(Decimal("0.00000001"))), PRICE_VERSION


def billed_amount(value: str) -> str:
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("Billed amount must be a finite nonnegative USD decimal") from exc
    if not amount.is_finite() or amount < 0:
        raise ValueError("Billed amount must be a finite nonnegative USD decimal")
    return str(amount)
