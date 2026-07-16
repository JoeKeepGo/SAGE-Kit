from __future__ import annotations

import hashlib
import json
from importlib import resources
from typing import Any


SUPPORTED_CONTRACT_VERSIONS = (1, 2)


def contract_resource(version: int, name: str) -> Any:
    if version not in SUPPORTED_CONTRACT_VERSIONS:
        raise ValueError(f"unsupported validation contract version: {version}")
    if name not in {"policy.json", "task.schema.json", "evidence.schema.json"}:
        raise ValueError(f"unknown validation contract resource: {name}")
    return resources.files("sagekit").joinpath("resources", "contracts", f"v{version}", name)


def contract_json_digest(version: int, name: str) -> str:
    payload = json.loads(contract_resource(version, name).read_text(encoding="utf-8"))
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()
