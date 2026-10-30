"""Opt-in image-analysis boundary. Production providers are configured in later decisions."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class AnalysisSuggestion:
    primary_subject: str | None
    tags: list[dict[str, Any]]
    suggested_edits: str
    raw_response: dict[str, Any]
    usage: dict[str, Any] | None = None
    actual_cost: Decimal | None = None

    def sanitized(self) -> dict[str, Any]:
        return {
            "primary_subject": self.primary_subject,
            "tags": self.tags,
            "suggested_edits": self.suggested_edits,
        }


class AnalysisProvider(Protocol):
    provider_name: str
    model: str
    template_version: str
    config_signature: str
    currency: str

    def estimate(self, image_count: int) -> Decimal: ...

    def analyze(self, image_path: Path, context: dict[str, Any]) -> AnalysisSuggestion: ...


class AnalysisUnavailable(RuntimeError):
    """No real provider has been selected/configured for this local installation."""


class UnavailableAnalysisProvider:
    provider_name = "unconfigured"
    model = "unconfigured"
    template_version = "phase03-v1"
    config_signature = "unconfigured:phase03-v1"
    currency = "USD"

    def estimate(self, image_count: int) -> Decimal:
        raise AnalysisUnavailable("No analysis provider is configured; no API call was made")

    def analyze(self, image_path: Path, context: dict[str, Any]) -> AnalysisSuggestion:
        raise AnalysisUnavailable("No analysis provider is configured; no API call was made")


def suggestion_dict(value: AnalysisSuggestion) -> dict[str, Any]:
    result = asdict(value)
    if value.actual_cost is not None:
        result["actual_cost"] = str(value.actual_cost)
    return result
