"""Load the private, repository-local server configuration without logging secrets."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
import os
from pathlib import Path
from typing import MutableMapping


CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "openAI.env"
FIELDS = {"OPENAI_API_KEY", "PHOTO_EDIT_MODEL", "PHOTO_EDIT_PLANNING_COST_USD"}


def load_local_config(path: Path = CONFIG_PATH, environ: MutableMapping[str, str] | None = None) -> bool:
    """Load local fields, preferring the file's planning amount when present."""
    if not path.is_file():
        return False
    target = os.environ if environ is None else environ
    values: dict[str, str] = {}
    for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        name, separator, value = stripped.partition("=")
        name = name.strip()
        if not separator or name not in FIELDS:
            raise ValueError(f"config/openAI.env line {number}: expected a supported NAME=value field")
        if name in values:
            raise ValueError(f"config/openAI.env line {number}: duplicate {name}")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        values[name] = value

    required = ("OPENAI_API_KEY", "PHOTO_EDIT_PLANNING_COST_USD")
    for name in required:
        if not values.get(name) and not target.get(name):
            raise ValueError(f"config/openAI.env: set {name} before starting the paid provider")
    key = target.get("OPENAI_API_KEY") or values.get("OPENAI_API_KEY", "")
    if key == "YOUR_KEY_HERE":
        raise ValueError("config/openAI.env: replace the OPENAI_API_KEY example value")
    # The owner-edited local file is authoritative for this application budget
    # estimate. A stale shell value must not silently replace it.
    planning = values.get("PHOTO_EDIT_PLANNING_COST_USD") or target.get("PHOTO_EDIT_PLANNING_COST_USD", "")
    try:
        if Decimal(planning) <= 0 or not Decimal(planning).is_finite():
            raise InvalidOperation
    except InvalidOperation as exc:
        raise ValueError("config/openAI.env: PHOTO_EDIT_PLANNING_COST_USD must be a positive number") from exc
    for name, value in values.items():
        if (name == "PHOTO_EDIT_PLANNING_COST_USD" and value) or not target.get(name):
            target[name] = value
    return True
