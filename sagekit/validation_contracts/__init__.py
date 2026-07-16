from __future__ import annotations

import hashlib
import json
from importlib import resources
from typing import Any


SUPPORTED_CONTRACT_VERSIONS = (0, 1, 2)


def contract_resource(version: int, name: str) -> Any:
    if version not in SUPPORTED_CONTRACT_VERSIONS:
        raise ValueError(f"unsupported validation contract version: {version}")
    allowed = {"policy.json", "task.schema.json", "evidence.schema.json"}
    if version in {0, 1}:
        allowed.add("rules.json")
    if version == 1:
        allowed.add("validator.json")
    if name not in allowed:
        raise ValueError(f"unknown validation contract resource: {name}")
    return resources.files("sagekit").joinpath("resources", "contracts", f"v{version}", name)


def contract_json_digest(version: int, name: str) -> str:
    payload = json.loads(contract_resource(version, name).read_text(encoding="utf-8"))
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def contract_schema_mismatches(version: int) -> list[str]:
    policy = json.loads(contract_resource(version, "policy.json").read_text(encoding="utf-8"))
    expected = policy.get("schema_sha256")
    if not isinstance(expected, dict):
        return [f"v{version} policy does not bind schema digests"]
    errors: list[str] = []
    for name in ("task.schema.json", "evidence.schema.json"):
        actual = contract_json_digest(version, name)
        if expected.get(name) != actual:
            errors.append(f"v{version} {name} digest does not match frozen policy")
    return errors
