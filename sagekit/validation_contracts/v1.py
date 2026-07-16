from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import contract_json_digest, contract_resource


VERSION = 1
POLICY_ID = "sagekit-task-dispatch-v1"
SCOPE = "closed-legacy"


def policy_sha256() -> str:
    return contract_json_digest(VERSION, "policy.json")


def contract_metadata() -> dict[str, Any]:
    return {
        "version": VERSION,
        "policy_id": POLICY_ID,
        "policy_sha256": policy_sha256(),
        "scope": SCOPE,
    }


def schema_dir() -> Path:
    return Path(str(contract_resource(VERSION, "policy.json"))).parent


def validate_records(
    task: dict[str, Any],
    evidence: dict[str, Any],
    *,
    gate_ready: bool = False,
) -> list[str]:
    from ..task_dispatch_validator import validate_records as validate_legacy_records

    errors: list[str] = []
    expected = contract_metadata()
    for label, record in (("task", task), ("evidence", evidence)):
        metadata = record.get("validation_contract")
        if metadata is None:
            continue
        if not isinstance(metadata, dict):
            errors.append(f"{label} validation_contract is invalid")
            continue
        for field, expected_value in expected.items():
            actual = metadata.get(field)
            if actual != expected_value:
                description = "policy snapshot" if field == "policy_sha256" else field
                errors.append(
                    f"{label} validation contract {description} mismatch: "
                    f"expected {expected_value}, got {actual}"
                )
    errors.extend(
        validate_legacy_records(task, evidence, schema_dir(), gate_ready=gate_ready)
    )
    return errors


def policy_payload() -> dict[str, Any]:
    return json.loads(contract_resource(VERSION, "policy.json").read_text(encoding="utf-8"))
