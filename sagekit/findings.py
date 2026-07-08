from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


LEVELS = {"PASS", "WARN", "FAIL"}


@dataclass(frozen=True)
class Finding:
    level: str
    rule: str
    path: str | None
    line: int | None
    message: str
    suggestion: str | None = None

    def __post_init__(self) -> None:
        if self.level not in LEVELS:
            raise ValueError(f"invalid finding level: {self.level}")

    def to_json(self) -> dict[str, Any]:
        payload = asdict(self)
        return {key: value for key, value in payload.items() if value is not None}

    def to_text(self) -> str:
        location = f"{self.path}: " if self.path else ""
        text = f"{self.level} {self.rule}: {location}{self.message}"
        if self.suggestion:
            text += f" Suggestion: {self.suggestion}"
        return text


def has_fail(findings: list[Finding]) -> bool:
    return any(finding.level == "FAIL" for finding in findings)
