from __future__ import annotations

import json
from typing import Any

from . import contract_json_digest, contract_resource
from .frozen_validator import validate_frozen_records


VERSION = 1
POLICY_ID = "sagekit-task-dispatch-v1"
SCOPE = "closed-legacy"
FROZEN_VALIDATOR_REGISTRY_SHA256 = (
    "287760d3ccf9f3f752ee42377753ca0195d54fd32e18b957c3ca2e41a6985ca7"
)


def policy_sha256() -> str:
    return contract_json_digest(VERSION, "policy.json")


def contract_metadata() -> dict[str, Any]:
    return {
        "version": VERSION,
        "policy_id": POLICY_ID,
        "policy_sha256": policy_sha256(),
        "scope": SCOPE,
    }


def validate_records(
    task: dict[str, Any],
    evidence: dict[str, Any],
    *,
    gate_ready: bool = False,
) -> list[str]:
    errors: list[str] = []
    metadata_records: list[tuple[str, dict[str, Any]]] = []
    for label, record in (("task", task), ("evidence", evidence)):
        metadata = record.get("validation_contract")
        if metadata is None:
            continue
        if not isinstance(metadata, dict):
            errors.append(f"{label} validation_contract is invalid")
            continue
        metadata_records.append((label, metadata))
    expected: dict[str, Any] | None = None
    if metadata_records:
        try:
            expected = contract_metadata()
        except (OSError, UnicodeError, ValueError):
            expected = None
    for label, metadata in metadata_records:
        if expected is None:
            break
        for field, expected_value in expected.items():
            actual = metadata.get(field)
            if actual != expected_value:
                description = "policy snapshot" if field == "policy_sha256" else field
                errors.append(
                    f"{label} validation contract {description} mismatch: "
                    f"expected {expected_value}, got {actual}"
                )
    errors.extend(
        validate_frozen_records(
            VERSION,
            task,
            evidence,
            gate_ready=gate_ready,
            validator_registry_sha256=FROZEN_VALIDATOR_REGISTRY_SHA256,
        )
    )
    return errors


def policy_payload() -> dict[str, Any]:
    return json.loads(contract_resource(VERSION, "policy.json").read_text(encoding="utf-8"))
