"""Optional server-side OpenAI Images API adapter; never enabled without local configuration."""

from __future__ import annotations

import base64
from decimal import Decimal
import json
import os
from pathlib import Path
import secrets
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from PIL import Image

from .editing import EditResult


class OpenAIEditProvider:
    def __init__(self, *, api_key: str, model: str, planning_cost_usd: Decimal):
        if not api_key or planning_cost_usd <= 0:
            raise ValueError("API key and positive per-image planning cost are required")
        if model not in ("gpt-image-2.5-sunburst", "gpt-image-2.5-flare"):
            raise ValueError("Select a supported GPT Image 2.5 model")
        self._api_key = api_key
        self.model = model
        self.estimated_cost_usd = planning_cost_usd

    def edit(self, publication_input: Path, prompt: str, mask: Path | None) -> EditResult:
        # The caller has verified that this path is the immutable publication derivative.
        with Image.open(publication_input) as image:
            width, height = image.size
        if not 1 / 3 <= width / height <= 3:
            raise ValueError("This panoramic aspect ratio exceeds the provider's supported range")
        if min(width, height) < 512:
            raise ValueError("This publication input is too small for the configured provider")
        width = round(width / 16) * 16
        height = round(height / 16) * 16
        boundary = "photo-mass-editor-" + secrets.token_hex(16)
        parts: list[bytes] = []

        def field(name: str, value: str) -> None:
            parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode())

        def file(name: str, path: Path, mime: str) -> None:
            parts.append(
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"; filename=\"{path.name}\"\r\n"
                f"Content-Type: {mime}\r\n\r\n".encode() + path.read_bytes() + b"\r\n"
            )

        field("model", self.model)
        field("prompt", prompt)
        field("quality", "medium")
        field("output_format", "png")
        field("size", f"{width}x{height}")
        file("image", publication_input, "image/jpeg")
        if mask:
            file("mask", mask, "image/png")
        body = b"".join(parts) + f"--{boundary}--\r\n".encode()
        request = Request(
            "https://api.openai.com/v1/images/edits", data=body, method="POST",
            headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        try:
            with urlopen(request, timeout=180) as response:
                result = json.load(response)
        except HTTPError as exc:
            raise RuntimeError(f"OpenAI image edit returned HTTP {exc.code}; inspect account status and model access") from exc
        except URLError as exc:
            raise RuntimeError("OpenAI image edit request failed before a response; inspect job receipt before retrying") from exc
        data = result.get("data") or []
        if not data or not data[0].get("b64_json"):
            raise RuntimeError("OpenAI image edit returned no image; inspect job receipt before retrying")
        return EditResult(
            image_bytes=base64.b64decode(data[0]["b64_json"], validate=True),
            suffix=".png", model=self.model, usage=result.get("usage") or {},
            actual_cost_usd=None,  # Usage is retained; the provider does not return an invoice amount here.
        )


def configured_provider():
    from .editing import UnavailableEditProvider
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        return UnavailableEditProvider()
    planning = os.getenv("PHOTO_EDIT_PLANNING_COST_USD", "").strip()
    if not planning:
        return UnavailableEditProvider()
    return OpenAIEditProvider(
        api_key=key,
        model=os.getenv("PHOTO_EDIT_MODEL", "gpt-image-2.5-sunburst"),
        planning_cost_usd=Decimal(planning),
    )
