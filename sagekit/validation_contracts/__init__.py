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
        allowed.update({"rules.json", "validator.json"})
    if name not in allowed:
        raise ValueError(f"unknown validation contract resource: {name}")
    return resources.files("sagekit").joinpath("resources", "contracts", f"v{version}", name)


def contract_json_digest(version: int, name: str) -> str:
    payload = json.loads(contract_resource(version, name).read_text(encoding="utf-8"))
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def contract_schema_mismatches(
    version: int,
    *,
    policy: dict[str, Any] | None = None,
) -> list[str]:
    if policy is None:
        path = contract_resource(version, "policy.json")
        if not path.is_file():
            return [f"v{version} frozen artifact missing: policy.json"]
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeError, OSError) as exc:
            return [f"v{version} frozen artifact is not valid JSON: policy.json: {exc}"]
        if not isinstance(loaded, dict):
            return [
                f"v{version} frozen artifact must contain a JSON object: policy.json"
            ]
        policy = loaded
    expected = policy.get("schema_sha256")
    if not isinstance(expected, dict):
        return [f"v{version} policy does not bind schema digests"]
    errors: list[str] = []
    for name in ("task.schema.json", "evidence.schema.json"):
        path = contract_resource(version, name)
        if not path.is_file():
            errors.append(f"v{version} schema file missing: {name}")
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeError, OSError) as exc:
            errors.append(f"v{version} schema file is not valid JSON: {name}: {exc}")
            continue
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
        actual = hashlib.sha256(canonical).hexdigest()
        if expected.get(name) != actual:
            errors.append(f"v{version} {name} digest does not match frozen policy")
    return errors
