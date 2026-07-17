from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from . import contract_resource, contract_schema_mismatches


def validator_engine_sha256() -> str:
    text = Path(__file__).read_text(encoding="utf-8").replace("\r\n", "\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def frozen_contract_mismatches(
    version: int,
    *,
    validator_registry_sha256: str | None = None,
) -> list[str]:
    errors, _, _ = _frozen_contract_artifacts(
        version,
        validator_registry_sha256=validator_registry_sha256,
    )
    return errors


def _frozen_contract_artifacts(
    version: int,
    *,
    validator_registry_sha256: str | None,
) -> tuple[list[str], dict[str, Any] | None, dict[str, Any] | None]:
    errors: list[str] = []
    policy = _load_frozen_json(version, "policy.json", errors)
    rules = _load_frozen_json(version, "rules.json", errors)
    binding = _load_frozen_json(version, "validator.json", errors)
    if policy is not None:
        errors.extend(contract_schema_mismatches(version, policy=policy))
    if binding is None or rules is None or policy is None:
        return errors, binding, rules

    actual_registry = _canonical_digest(binding)
    if (
        validator_registry_sha256 is None
        or actual_registry != validator_registry_sha256
    ):
        errors.append(
            f"v{version} frozen validator registry digest does not match "
            "the version module"
        )
    actual_policy = _canonical_digest(policy)
    if binding.get("policy_sha256") != actual_policy:
        errors.append(f"v{version} policy digest does not match validator registry")
    actual_rules = _canonical_digest(rules)
    if binding.get("validator_rules_sha256") != actual_rules:
        errors.append(f"v{version} rules.json digest does not match frozen policy")
    if binding.get("validator_semantics_id") != rules.get("semantics_id"):
        errors.append(
            f"v{version} validator semantics identity does not match frozen policy"
        )
    actual_engine = validator_engine_sha256()
    if binding.get("validator_engine_sha256") != actual_engine:
        errors.append(f"v{version} frozen validator engine digest does not match policy")
    if not isinstance(binding.get("record_schema_enforced"), bool):
        errors.append(
            f"v{version} validator registry does not declare record schema behavior"
        )
    if binding.get("schema_artifacts_checked") != [
        "presence",
        "valid_json",
        "canonical_digest",
    ]:
        errors.append(
            f"v{version} validator registry does not declare frozen schema checks"
        )
    return errors, binding, rules


def validate_frozen_records(
    version: int,
    task: dict[str, Any],
    evidence: dict[str, Any],
    *,
    gate_ready: bool = False,
    validator_registry_sha256: str | None = None,
) -> list[str]:
    errors, binding, rules = _frozen_contract_artifacts(
        version,
        validator_registry_sha256=validator_registry_sha256,
    )
    if errors or binding is None or rules is None:
        return errors
    if binding.get("record_schema_enforced") is True:
        for label, filename, record in (
            ("task", "task.schema.json", task),
            ("evidence", "evidence.schema.json", evidence),
        ):
            try:
                schema = _load_json(version, filename)
            except (json.JSONDecodeError, UnicodeError, OSError, ValueError):
                continue
            _validate_schema_value(record, schema, label, schema, errors)
    _validate_historical_semantics(task, evidence, rules, gate_ready, errors)
    return errors


def _load_json(version: int, name: str) -> dict[str, Any]:
    payload = json.loads(contract_resource(version, name).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"v{version} {name} must contain a JSON object")
    return payload


def _load_frozen_json(
    version: int,
    name: str,
    errors: list[str],
) -> dict[str, Any] | None:
    path = contract_resource(version, name)
    if not path.is_file():
        errors.append(f"v{version} frozen artifact missing: {name}")
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeError, OSError) as exc:
        errors.append(f"v{version} frozen artifact is not valid JSON: {name}: {exc}")
        return None
    if not isinstance(payload, dict):
        errors.append(
            f"v{version} frozen artifact must contain a JSON object: {name}"
        )
        return None
    return payload


def _canonical_digest(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(canonical).hexdigest()


def _schema_type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return True


def _resolve_local_schema_ref(root_schema: dict[str, Any], reference: str) -> Any:
    if not reference.startswith("#/"):
        return None
    current: Any = root_schema
    for token in reference[2:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict) or token not in current:
            return None
        current = current[token]
    return current


def _validate_schema_value(
    value: Any,
    schema: Any,
    name: str,
    root_schema: dict[str, Any],
    errors: list[str],
) -> None:
    if not isinstance(schema, dict):
        return
    reference = schema.get("$ref")
    if isinstance(reference, str):
        resolved = _resolve_local_schema_ref(root_schema, reference)
        if resolved is None:
            errors.append(f"{name} uses unsupported schema reference: {reference}")
            return
        _validate_schema_value(value, resolved, name, root_schema, errors)
        return

    for branch in schema.get("allOf", []):
        _validate_schema_value(value, branch, name, root_schema, errors)
    for keyword, exact_count in (("anyOf", False), ("oneOf", True)):
        branches = schema.get(keyword)
        if isinstance(branches, list):
            matches = 0
            for branch in branches:
                branch_errors: list[str] = []
                _validate_schema_value(
                    value,
                    branch,
                    name,
                    root_schema,
                    branch_errors,
                )
                if not branch_errors:
                    matches += 1
            if (exact_count and matches != 1) or (not exact_count and matches == 0):
                errors.append(f"{name} must satisfy {keyword} schema constraint")
    negated = schema.get("not")
    if isinstance(negated, dict):
        negated_errors: list[str] = []
        _validate_schema_value(value, negated, name, root_schema, negated_errors)
        if not negated_errors:
            errors.append(f"{name} must not satisfy prohibited schema constraint")
    condition = schema.get("if")
    if isinstance(condition, dict):
        condition_errors: list[str] = []
        _validate_schema_value(value, condition, name, root_schema, condition_errors)
        branch = schema.get("then") if not condition_errors else schema.get("else")
        if isinstance(branch, dict):
            _validate_schema_value(value, branch, name, root_schema, errors)

    expected_types = schema.get("type")
    if isinstance(expected_types, str):
        expected_types = [expected_types]
    if isinstance(expected_types, list) and not any(
        isinstance(expected, str) and _schema_type_matches(value, expected)
        for expected in expected_types
    ):
        errors.append(
            f"{name} must match schema type: {' or '.join(map(str, expected_types))}"
        )
        return

    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{name} must be one of schema enum values: {schema['enum']}")
    if "const" in schema and value != schema["const"]:
        errors.append(f"{name} must equal schema constant: {schema['const']!r}")
    if isinstance(value, str):
        minimum = schema.get("minLength")
        if isinstance(minimum, int) and len(value) < minimum:
            errors.append(f"{name} must have length at least {minimum} by schema")
        pattern = schema.get("pattern")
        if isinstance(pattern, str) and re.search(pattern, value) is None:
            errors.append(f"{name} does not match schema pattern: {pattern}")
    if isinstance(value, list):
        minimum = schema.get("minItems")
        if isinstance(minimum, int) and len(value) < minimum:
            errors.append(f"{name} must contain at least {minimum} items by schema")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                _validate_schema_value(
                    item,
                    item_schema,
                    f"{name}[{index}]",
                    root_schema,
                    errors,
                )
        if schema.get("uniqueItems") is True:
            for index, item in enumerate(value):
                if any(item == previous for previous in value[:index]):
                    errors.append(f"{name} must contain unique items by schema")
                    break
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        minimum = schema.get("minimum")
        if isinstance(minimum, (int, float)) and value < minimum:
            errors.append(f"{name} must be at least {minimum} by schema")
    if isinstance(value, dict):
        required = schema.get("required", [])
        if isinstance(required, list):
            for field in required:
                if isinstance(field, str) and field not in value:
                    errors.append(f"{name}.{field} is required by schema")
        properties = schema.get("properties", {})
        if isinstance(properties, dict):
            for field, field_schema in properties.items():
                if field in value:
                    _validate_schema_value(
                        value[field],
                        field_schema,
                        f"{name}.{field}",
                        root_schema,
                        errors,
                    )


def _upper(value: Any) -> str:
    return str(value or "").strip().upper()


def _nonempty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        normalized = value.strip()
        return bool(normalized) and normalized.lower() not in {"n/a", "none", "null"}
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def _mapping(name: str, value: Any, errors: list[str]) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    errors.append(f"{name} must be a mapping")
    return {}


def _list(name: str, value: Any, errors: list[str]) -> list[Any]:
    if isinstance(value, list):
        return value
    errors.append(f"{name} must be a list")
    return []


def _validate_historical_semantics(
    task: dict[str, Any],
    evidence: dict[str, Any],
    rules: dict[str, Any],
    gate_ready: bool,
    errors: list[str],
) -> None:
    levels_defined = tuple(rules["levels"])
    task_terminal_statuses = set(rules["task_terminal_statuses"])
    evidence_terminal_statuses = set(rules["evidence_terminal_statuses"])
    passlike = set(rules["passlike_level_statuses"])
    profile = str(rules["profile"])

    for field in rules["task_required_fields"]:
        if field not in task:
            errors.append(f"task.{field} is required")
    for field in rules["evidence_required_fields"]:
        if field not in evidence:
            errors.append(f"evidence.{field} is required")

    task_id = str(task.get("id") or "").strip()
    evidence_task_id = str(evidence.get("task_id") or "").strip()
    if not task_id:
        errors.append("task.id must be a non-empty task id")
    elif re.fullmatch(r"TASK-[A-Za-z0-9._-]+", task_id) is None:
        errors.append("task.id must match TASK-<id>")
    if not evidence_task_id:
        errors.append("evidence.task_id must be a non-empty task id")
    elif re.fullmatch(r"TASK-[A-Za-z0-9._-]+", evidence_task_id) is None:
        errors.append("evidence.task_id must match TASK-<id>")
    if task_id and evidence_task_id and task_id != evidence_task_id:
        errors.append(
            f"task.id ({task_id}) does not match evidence.task_id ({evidence_task_id})"
        )

    if _upper(task.get("type")) not in set(rules["task_types"]):
        errors.append("task.type is not allowed by the frozen contract")
    if _upper(task.get("priority")) not in set(rules["priorities"]):
        errors.append("task.priority is not allowed by the frozen contract")
    task_status = _upper(task.get("status"))
    evidence_conclusion = _mapping(
        "evidence.conclusion",
        evidence.get("conclusion"),
        errors,
    )
    evidence_status = _upper(evidence_conclusion.get("status"))
    if task_status not in set(rules["task_statuses"]):
        errors.append("task.status is not allowed by the frozen contract")
    if evidence_status not in set(rules["evidence_statuses"]):
        errors.append(
            "evidence.conclusion.status is not allowed by the frozen contract"
        )

    task_terminal = task_status in task_terminal_statuses
    evidence_terminal = evidence_status in evidence_terminal_statuses
    if task_terminal and not evidence_terminal:
        errors.append(
            "terminal task requires terminal VERIFIED evidence conclusion"
        )
    if evidence_terminal and not task_terminal:
        errors.append(
            "VERIFIED evidence conclusion requires a terminal task status"
        )

    scope = _mapping("task.scope", task.get("scope"), errors)
    for field in rules["scope_required_fields"]:
        if field not in scope:
            errors.append(f"task.scope.{field} is required")
    for field in (
        "allowed_files",
        "read_only_files",
        "forbidden_files",
        "non_goals",
        "stop_conditions",
    ):
        _list(f"task.scope.{field}", scope.get(field), errors)
    verification = _mapping(
        "task.verification",
        task.get("verification"),
        errors,
    )
    raw_required_levels = _list(
        "task.verification.required_levels",
        verification.get("required_levels"),
        errors,
    )
    required_levels = [
        str(level).strip()
        for level in raw_required_levels
        if isinstance(level, str) and level.strip()
    ]
    if not required_levels:
        errors.append(
            "task.verification.required_levels must name at least one level"
        )
    for level in required_levels:
        if level not in levels_defined:
            errors.append(f"invalid required evidence level: {level}")

    dependencies = _mapping(
        "task.dependencies",
        task.get("dependencies"),
        errors,
    )
    for field in ("requires", "blocks"):
        values = _list(
            f"task.dependencies.{field}",
            dependencies.get(field),
            errors,
        )
        if task_id and task_id in values:
            errors.append(
                f"task.dependencies.{field} must not reference the task itself"
            )

    resources = _mapping("task.resources", task.get("resources"), errors)
    locks = _list("task.resources.locks", resources.get("locks"), errors)
    task_runs = _list("task.runs", task.get("runs"), errors)
    active_locks: list[dict[str, Any]] = []
    if profile == "hardened":
        active_locks = _validate_hardened_locks(locks, rules, errors)
        _validate_hardened_runs(
            "task",
            task_runs,
            rules,
            errors,
            infer_from_active_lock=bool(active_locks),
        )
    else:
        _validate_locks(locks, set(rules["active_lock_statuses"]), errors)
        _validate_runs(
            "task",
            task_runs,
            set(rules["active_run_statuses"]),
            errors,
        )

    evidence_levels = _mapping(
        "evidence.levels",
        evidence.get("levels"),
        errors,
    )
    for level in levels_defined:
        level_record = _mapping(
            f"evidence.levels.{level}",
            evidence_levels.get(level),
            errors,
        )
        status = _upper(level_record.get("status"))
        if status not in set(rules["level_statuses"]):
            errors.append(
                f"evidence.levels.{level}.status is not allowed by the frozen contract"
            )
    for level in required_levels:
        if level not in evidence_levels:
            errors.append(f"required level missing from evidence: {level}")

    artifacts = _mapping(
        "evidence.artifacts",
        evidence.get("artifacts"),
        errors,
    )
    for field in rules["artifact_fields"]:
        _list(f"evidence.artifacts.{field}", artifacts.get(field), errors)
    blockers = _list("evidence.blockers", evidence.get("blockers"), errors)
    evidence_runs = _list("evidence.runs", evidence.get("runs"), errors)
    if profile == "hardened":
        _validate_hardened_runs(
            "evidence",
            evidence_runs,
            rules,
            errors,
            infer_from_active_lock=bool(active_locks),
        )
    else:
        _validate_runs(
            "evidence",
            evidence_runs,
            set(rules["active_run_statuses"]),
            errors,
        )

    if evidence_terminal and blockers:
        errors.append("verified evidence cannot retain blockers")
    if gate_ready:
        if not task_terminal:
            errors.append(
                "gate-ready validation requires task.status to be VERIFIED or CLOSED"
            )
        if not evidence_terminal:
            errors.append(
                "gate-ready validation requires evidence.conclusion.status to be VERIFIED"
            )
        if blockers:
            errors.append(
                "gate-ready validation requires evidence.blockers to be empty"
            )

    verified = task_terminal or evidence_terminal or gate_ready
    if verified:
        for level in required_levels:
            level_record = _mapping(
                f"evidence.levels.{level}",
                evidence_levels.get(level),
                errors,
            )
            status = _upper(level_record.get("status"))
            if status not in passlike:
                errors.append(
                    f"verified task requires {level} to be PASS, N/A, or WAIVED; "
                    f"got {status or 'missing'}"
                )
            if status == "PASS" and not (
                _nonempty(level_record.get("evidence"))
                or _nonempty(level_record.get("commands"))
                or _nonempty(artifacts.get("commands"))
            ):
                errors.append(f"{level} is PASS but has no evidence or commands")
            if status in {"N/A", "WAIVED"} and not _nonempty(
                level_record.get("reason")
            ):
                errors.append(f"{level} is {status} but has no reason")
            if status == "WAIVED":
                for field in ("waived_by", "waiver_scope"):
                    if not _nonempty(level_record.get(field)):
                        errors.append(f"{level} is WAIVED but has no {field}")

    _validate_fallback(verification, evidence_conclusion, verified, errors)
    changed_surface = _list(
        "evidence.changed_surface",
        evidence.get("changed_surface"),
        errors,
    )
    _validate_surface_evidence(
        changed_surface,
        artifacts,
        verified,
        errors,
        hardened=profile == "hardened",
    )
    if profile == "hardened":
        _validate_hardened_semantics(
            task,
            evidence,
            verification,
            artifacts,
            evidence_levels,
            evidence_conclusion,
            task_terminal,
            evidence_terminal,
            required_levels,
            task_runs,
            evidence_runs,
            active_locks,
            gate_ready,
            rules,
            errors,
        )


def _validate_runs(
    label: str,
    runs: list[Any],
    active_statuses: set[str],
    errors: list[str],
) -> None:
    for index, raw_run in enumerate(runs):
        run = _mapping(f"{label}.runs[{index}]", raw_run, errors)
        if not run:
            continue
        for field in ("id", "attempt", "status"):
            if not _nonempty(run.get(field)):
                errors.append(f"{label}.runs[{index}].{field} is required")
        if _upper(run.get("status")) in active_statuses:
            lease = _mapping(
                f"{label}.runs[{index}].lease",
                run.get("lease"),
                errors,
            )
            for field in ("resource", "owner", "status"):
                if not _nonempty(lease.get(field)):
                    errors.append(
                        f"{label}.runs[{index}].lease.{field} is required "
                        "for active runs"
                    )
            if not (
                _nonempty(lease.get("expires_at"))
                or _nonempty(lease.get("release_rule"))
            ):
                errors.append(
                    f"{label}.runs[{index}].lease requires expires_at "
                    "or release_rule for active runs"
                )


def _validate_locks(
    locks: list[Any],
    active_statuses: set[str],
    errors: list[str],
) -> None:
    active_resources: set[str] = set()
    for index, raw_lock in enumerate(locks):
        lock = _mapping(f"task.resources.locks[{index}]", raw_lock, errors)
        if not lock:
            continue
        resource = str(lock.get("resource") or "").strip()
        if not resource:
            errors.append(f"task.resources.locks[{index}].resource is required")
        if _upper(lock.get("status")) in active_statuses:
            for field in ("owner", "mode"):
                if not _nonempty(lock.get(field)):
                    errors.append(
                        f"task.resources.locks[{index}].{field} is required "
                        "for active locks"
                    )
            if not (
                _nonempty(lock.get("expires_at"))
                or _nonempty(lock.get("release_rule"))
            ):
                errors.append(
                    f"task.resources.locks[{index}] requires expires_at "
                    "or release_rule for active locks"
                )
            if resource in active_resources:
                errors.append(f"duplicate active resource lock: {resource}")
            active_resources.add(resource)


def _resource_use_flag(
    run: dict[str, Any],
    inferred: bool,
    name: str,
    errors: list[str],
) -> bool:
    aliases = (
        "uses_shared_resource",
        "uses_scarce_resource",
        "shared_resource",
        "scarce_resource",
    )
    present = [field for field in aliases if field in run]
    if not present:
        return inferred
    value = run[present[0]]
    if not isinstance(value, bool):
        errors.append(f"{name}.{present[0]} must be a boolean")
        return inferred
    return value


def _validate_hardened_runs(
    label: str,
    runs: list[Any],
    rules: dict[str, Any],
    errors: list[str],
    *,
    infer_from_active_lock: bool,
) -> None:
    run_ids: set[str] = set()
    active_run_statuses = set(rules["active_run_statuses"])
    active_lock_statuses = set(rules["active_lock_statuses"])
    run_statuses = set(rules["run_statuses"])
    terminal_run_statuses = set(rules["terminal_run_statuses"])
    lease_statuses = set(rules["lease_statuses"])
    released_lease_statuses = set(rules["released_lease_statuses"])
    resource_modes = set(rules["resource_modes"])
    for index, raw_run in enumerate(runs):
        name = f"{label}.runs[{index}]"
        run = _mapping(name, raw_run, errors)
        if not run:
            continue
        run_id = str(run.get("id") or "").strip()
        if not run_id:
            errors.append(f"{name}.id is required")
        elif run_id in run_ids:
            errors.append(f"{name}.id duplicates run id: {run_id}")
        run_ids.add(run_id)
        attempt = run.get("attempt")
        if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt < 1:
            errors.append(f"{name}.attempt must be a positive integer")
        status = _upper(run.get("status"))
        if status not in run_statuses:
            errors.append(
                f"{name}.status is not allowed by the frozen contract"
            )

        raw_lease = run.get("lease")
        has_lease = isinstance(raw_lease, dict) and bool(raw_lease)
        uses_resource = _resource_use_flag(
            run,
            has_lease or infer_from_active_lock,
            name,
            errors,
        )
        if not uses_resource and has_lease:
            errors.append(
                f"{name} declares no shared resource but contains a lease"
            )
        lease: dict[str, Any] = {}
        if uses_resource and status in active_run_statuses:
            lease = _mapping(f"{name}.lease", raw_lease, errors)
        elif raw_lease is not None:
            lease = _mapping(f"{name}.lease", raw_lease, errors)
        if not lease:
            continue
        for field in ("resource", "owner", "mode", "status"):
            if not _nonempty(lease.get(field)):
                errors.append(f"{name}.lease.{field} is required")
        lease_status = _upper(lease.get("status"))
        lease_mode = _upper(lease.get("mode"))
        if lease_status not in lease_statuses:
            errors.append(
                f"{name}.lease.status is not allowed by the frozen contract"
            )
        if lease_mode not in resource_modes:
            errors.append(
                f"{name}.lease.mode is not allowed by the frozen contract"
            )
        if lease_status in active_lock_statuses and not (
            _nonempty(lease.get("expires_at"))
            or _nonempty(lease.get("release_rule"))
        ):
            errors.append(
                f"{name}.lease requires expires_at or release_rule while active"
            )
        if status in active_run_statuses and lease_status in released_lease_statuses:
            errors.append(f"{name} active run contradicts its released lease")
        if status in terminal_run_statuses and lease_status in active_lock_statuses:
            errors.append(f"{name} terminal run cannot retain an active lease")


def _validate_hardened_locks(
    locks: list[Any],
    rules: dict[str, Any],
    errors: list[str],
) -> list[dict[str, Any]]:
    active_resources: set[str] = set()
    active_locks: list[dict[str, Any]] = []
    active_statuses = set(rules["active_lock_statuses"])
    lock_statuses = set(rules["lock_statuses"])
    resource_modes = set(rules["resource_modes"])
    for index, raw_lock in enumerate(locks):
        name = f"task.resources.locks[{index}]"
        lock = _mapping(name, raw_lock, errors)
        if not lock:
            continue
        resource = str(lock.get("resource") or "").strip()
        status = _upper(lock.get("status"))
        mode = _upper(lock.get("mode"))
        if not resource:
            errors.append(f"{name}.resource is required")
        if status not in lock_statuses:
            errors.append(f"{name}.status is not allowed by the frozen contract")
        if mode not in resource_modes:
            errors.append(f"{name}.mode is not allowed by the frozen contract")
        if "carried" in lock and not isinstance(lock.get("carried"), bool):
            errors.append(f"{name}.carried must be a boolean")
        if lock.get("carried") is True and not _nonempty(lock.get("carried_from")):
            errors.append(f"{name}.carried_from is required for carried locks")
        if status not in active_statuses:
            continue
        for field in ("owner", "mode"):
            if not _nonempty(lock.get(field)):
                errors.append(f"{name}.{field} is required for active locks")
        if not (
            _nonempty(lock.get("expires_at"))
            or _nonempty(lock.get("release_rule"))
        ):
            errors.append(
                f"{name} requires expires_at or release_rule for active locks"
            )
        resource_key = resource.casefold()
        if resource_key in active_resources:
            errors.append(f"duplicate active resource lock: {resource}")
        active_resources.add(resource_key)
        active_locks.append(lock)
    return active_locks


def _validate_fallback(
    verification: dict[str, Any],
    conclusion: dict[str, Any],
    verified: bool,
    errors: list[str],
) -> None:
    mock_used = bool(conclusion.get("mock_used"))
    mock_allowed = bool(verification.get("mock_allowed"))
    accepted_fallback = bool(conclusion.get("accepted_fallback"))
    if verified and mock_used and not mock_allowed and not accepted_fallback:
        errors.append(
            "verified task used mock fallback without mock_allowed "
            "or accepted_fallback"
        )
    if accepted_fallback and not _nonempty(
        conclusion.get("accepted_fallback_reason")
    ):
        errors.append(
            "accepted_fallback requires accepted_fallback_reason"
        )
    if accepted_fallback:
        for field in ("accepted_fallback_by", "accepted_fallback_scope"):
            if not _nonempty(conclusion.get(field)):
                errors.append(f"accepted_fallback requires {field}")


def _validate_surface_evidence(
    changed_surface: list[Any],
    artifacts: dict[str, Any],
    verified: bool,
    errors: list[str],
    *,
    hardened: bool,
) -> None:
    if not verified:
        return
    categories: set[str] = set()
    aliases = {
        "api": {"api", "http", "service"},
        "sql": {"database", "db", "sql", "migration"},
        "browser": {"ui", "frontend", "browser"},
        "release": {"release", "deploy", "package"},
    }
    for item in changed_surface:
        surface = str(item).strip().replace("\\", "/").casefold()
        if not surface:
            continue
        if not hardened or "/" not in surface:
            categories.update(
                category
                for category, names in aliases.items()
                if surface in names
            )
            continue
        if surface.startswith("docs/") or surface.endswith((".md", ".rst", ".txt")):
            continue
        segments = {segment for segment in surface.split("/") if segment}
        if segments.intersection({"api", "apis", "routes", "endpoints", "openapi"}):
            categories.add("api")
        if segments.intersection({"db", "database", "sql", "migration", "migrations"}):
            categories.add("sql")
        if segments.intersection(
            {"ui", "frontend", "web", "browser", "components", "pages"}
        ):
            categories.add("browser")
        if segments.intersection(
            {"release", "releases", "deploy", "deployment", "packaging"}
        ):
            categories.add("release")
    for artifact_key in ("api", "sql", "browser", "release"):
        if artifact_key in categories and not _nonempty(artifacts.get(artifact_key)):
            errors.append(
                f"verified evidence for surface {artifact_key} "
                f"requires artifacts.{artifact_key}"
            )


def _validate_hardened_semantics(
    task: dict[str, Any],
    evidence: dict[str, Any],
    verification: dict[str, Any],
    artifacts: dict[str, Any],
    evidence_levels: dict[str, Any],
    conclusion: dict[str, Any],
    task_terminal: bool,
    evidence_terminal: bool,
    required_levels: list[str],
    task_runs: list[Any],
    evidence_runs: list[Any],
    active_locks: list[dict[str, Any]],
    gate_ready: bool,
    rules: dict[str, Any],
    errors: list[str],
) -> None:
    lifecycle = _mapping("task.lifecycle", task.get("lifecycle"), errors)
    if not _nonempty(task.get("title")):
        errors.append("task.title must be a non-empty string")
    for field in ("phase", "next_action"):
        if not _nonempty(lifecycle.get(field)):
            errors.append(f"task.lifecycle.{field} must be a non-empty string")
    if _upper(lifecycle.get("review_result")) not in set(rules["review_results"]):
        errors.append(
            "task.lifecycle.review_result is not allowed by the frozen contract"
        )
    scope = _mapping("task.scope", task.get("scope"), errors)
    if not _nonempty(scope.get("objective")):
        errors.append("task.scope.objective must be a non-empty string")
    if not _nonempty(verification.get("evidence_file")):
        errors.append(
            "task.verification.evidence_file must be a non-empty string"
        )
    if not isinstance(verification.get("mock_allowed"), bool):
        errors.append("task.verification.mock_allowed must be a boolean")

    task_authority = _mapping("task.authority", task.get("authority"), errors)
    evidence_authority = _mapping(
        "evidence.authority",
        evidence.get("authority"),
        errors,
    )
    for field in ("source", "grant", "scope"):
        if str(task_authority.get(field) or "").strip() != str(
            evidence_authority.get(field) or ""
        ).strip():
            errors.append(
                f"task.authority.{field} must match evidence.authority.{field}"
            )
    if str(lifecycle.get("phase") or "").strip() != str(
        evidence.get("phase") or ""
    ).strip():
        errors.append("task.lifecycle.phase must match evidence.phase")
    if _upper(lifecycle.get("review_result")) != _upper(
        conclusion.get("review_result")
    ):
        errors.append(
            "task.lifecycle.review_result must match "
            "evidence.conclusion.review_result"
        )
    if str(lifecycle.get("next_action") or "").strip() != str(
        conclusion.get("next_action") or ""
    ).strip():
        errors.append(
            "task.lifecycle.next_action must match "
            "evidence.conclusion.next_action"
        )
    if not _nonempty(evidence.get("phase")):
        errors.append("evidence.phase must be a non-empty string")
    if not _nonempty(evidence.get("runtime_shape")):
        errors.append("evidence.runtime_shape must be a non-empty string")
    if not _nonempty(conclusion.get("next_action")):
        errors.append(
            "evidence.conclusion.next_action must be a non-empty string"
        )
    if _upper(conclusion.get("review_result")) not in set(
        rules["review_results"]
    ):
        errors.append(
            "evidence.conclusion.review_result is not allowed by the frozen contract"
        )
    for field in ("mock_used", "accepted_fallback"):
        if not isinstance(conclusion.get(field), bool):
            errors.append(f"evidence.conclusion.{field} must be a boolean")

    task_status = _upper(task.get("status"))
    evidence_status = _upper(conclusion.get("status"))
    expected_evidence_statuses = {
        "NEW": {"PENDING"},
        "TRIAGED": {"PENDING"},
        "READY": {"PENDING"},
        "IN_PROGRESS": {"PENDING"},
        "READY_FOR_REVIEW": {"PENDING"},
        "VERIFIED": {"VERIFIED"},
        "CLOSED": {"VERIFIED"},
        "PARTIAL": {"PARTIAL"},
        "BLOCKED": set(rules["blocked_evidence_statuses"]),
    }
    expected = expected_evidence_statuses.get(task_status)
    if expected is not None and evidence_status not in expected:
        errors.append(
            f"task.status {task_status} requires a matching evidence conclusion"
        )

    if task_terminal:
        closure = _mapping("task.closure", task.get("closure"), errors)
        for field in ("accepted_by", "accepted_at", "review_result", "evidence_ref"):
            if not _nonempty(closure.get(field)):
                errors.append(
                    f"task.closure.{field} is required for terminal tasks"
                )
        acceptable = set(rules["acceptable_review_results"])
        if _upper(closure.get("review_result")) not in acceptable:
            errors.append(
                "task.closure.review_result must be acceptable for terminal tasks"
            )
        if _upper(lifecycle.get("review_result")) not in acceptable:
            errors.append(
                "terminal task requires an acceptable lifecycle review_result"
            )
    closure = _mapping("task.closure", task.get("closure"), errors)
    if task_status == "CLOSED" and not _nonempty(closure.get("closed_at")):
        errors.append("task.closure.closed_at is required for CLOSED tasks")
    if evidence_terminal:
        if _upper(conclusion.get("highest_level")) not in set(rules["levels"]):
            errors.append(
                "evidence.conclusion.highest_level must name L0-L4 when VERIFIED"
            )
        if _list("evidence.blockers", evidence.get("blockers"), errors):
            errors.append("verified evidence cannot retain blockers")

    task_run_statuses = _run_statuses(task_runs)
    evidence_run_statuses = _run_statuses(evidence_runs)
    active_statuses = set(rules["active_run_statuses"])
    task_active_runs = {
        run_id
        for run_id, status in task_run_statuses.items()
        if status in active_statuses
    }
    evidence_active_runs = {
        run_id
        for run_id, status in evidence_run_statuses.items()
        if status in active_statuses
    }
    execution_truth_required = (
        gate_ready
        or task_terminal
        or evidence_terminal
        or bool(task_active_runs or evidence_active_runs)
        or task_status
        in {"IN_PROGRESS", "READY_FOR_REVIEW", "PARTIAL", "BLOCKED"}
        or evidence_status != "PENDING"
    )
    task_run_ids = set(task_run_statuses)
    evidence_run_ids = set(evidence_run_statuses)
    if execution_truth_required:
        for run_id in sorted(task_run_ids - evidence_run_ids):
            errors.append(f"task run {run_id} is missing from evidence.runs")
        for run_id in sorted(evidence_run_ids - task_run_ids):
            errors.append(f"evidence run {run_id} is missing from task.runs")
    run_statuses = set(rules["run_statuses"])
    for run_id in sorted(task_run_ids & evidence_run_ids):
        task_run_status = task_run_statuses[run_id]
        evidence_run_status = evidence_run_statuses[run_id]
        if (
            task_run_status in run_statuses
            and evidence_run_status in run_statuses
            and task_run_status != evidence_run_status
        ):
            errors.append(
                f"task/evidence run {run_id} status mismatch: "
                f"task {task_run_status} != evidence {evidence_run_status}"
            )
    unaccounted_active_locks = [
        lock
        for lock in active_locks
        if not (
            lock.get("carried") is True
            and _nonempty(lock.get("carried_from"))
        )
    ]
    if task_terminal and (task_active_runs or evidence_active_runs):
        errors.append("terminal task cannot retain active runs")
    if task_terminal and unaccounted_active_locks:
        errors.append("terminal task cannot retain unaccounted active locks")
    if gate_ready:
        if task_active_runs or evidence_active_runs:
            errors.append("gate-ready validation cannot retain an active run")
        if unaccounted_active_locks:
            errors.append(
                "gate-ready validation cannot retain an unaccounted active lock"
            )

    _validate_required_commands(
        verification,
        artifacts,
        evidence_levels,
        required_levels,
        evidence,
        errors,
    )
    if bool(conclusion.get("mock_used")):
        mock_requirements = (
            (
                "rationale",
                ("mock_rationale", "accepted_fallback_reason", "rationale"),
            ),
            ("scope", ("mock_scope", "accepted_fallback_scope")),
            ("follow-up", ("mock_follow_up", "follow_up", "next_action")),
            (
                "accepted-by/authority metadata",
                (
                    "mock_accepted_by",
                    "mock_acceptance_actor",
                    "accepted_fallback_by",
                    "accepted_by",
                    "authority",
                ),
            ),
        )
        for description, fields in mock_requirements:
            if not any(_nonempty(conclusion.get(field)) for field in fields):
                errors.append(f"mock_used requires {description}")


def _run_statuses(runs: list[Any]) -> dict[str, str]:
    return {
        str(run.get("id") or "").strip(): _upper(run.get("status"))
        for run in runs
        if isinstance(run, dict)
    }


def _command_identity(value: Any) -> tuple[str, str, str, str] | None:
    if isinstance(value, str):
        command = " ".join(value.split())
        return ("", command, "", "") if command else None
    if not isinstance(value, dict):
        return None
    record_id = str(
        value.get("id") or value.get("command_id") or ""
    ).strip()
    command = " ".join(
        str(value.get("command") or value.get("cmd") or "").split()
    )
    source = " ".join(str(value.get("source") or "").split()).casefold()
    status = _upper(value.get("status"))
    return (record_id, command, source, status) if command else None


def _validate_required_commands(
    verification: dict[str, Any],
    artifacts: dict[str, Any],
    evidence_levels: dict[str, Any],
    required_levels: list[str],
    evidence: dict[str, Any],
    errors: list[str],
) -> None:
    required = [
        record
        for record in (
            _command_identity(value)
            for value in verification.get("required_commands", [])
        )
        if record is not None
    ]
    available_values = list(artifacts.get("commands", []))
    for level in required_levels:
        record = evidence_levels.get(level)
        if isinstance(record, dict):
            available_values.extend(record.get("commands", []))
    available = [
        record
        for record in (_command_identity(value) for value in available_values)
        if record is not None
    ]
    skipped_by_id: dict[str, dict[str, Any]] = {}
    for index, raw_skip in enumerate(
        _list(
            "evidence.skipped_checks",
            evidence.get("skipped_checks"),
            errors,
        )
    ):
        skipped = _mapping(
            f"evidence.skipped_checks[{index}]",
            raw_skip,
            errors,
        )
        if not skipped:
            continue
        for field in ("id", "check", "reason", "owner", "follow_up"):
            if not _nonempty(skipped.get(field)):
                errors.append(
                    f"evidence.skipped_checks[{index}].{field} is required"
                )
        skip_id = str(skipped.get("id") or "").strip()
        if skip_id in skipped_by_id:
            errors.append(
                f"evidence.skipped_checks contains duplicate id: {skip_id}"
            )
        elif skip_id:
            skipped_by_id[skip_id] = skipped
    for command_id, command, source, _ in required:
        matching = [
            record
            for record in available
            if record[0] == command_id
            and record[1] == command
            and record[2] == source
        ]
        if any(record[3] == "PASS" for record in matching):
            continue
        skipped = skipped_by_id.get(command_id) if command_id else None
        if skipped is not None:
            disposition = _upper(
                skipped.get("status") or skipped.get("disposition")
            )
            waived = skipped.get("waived") is True or disposition == "WAIVED"
            if waived:
                if not any(
                    _nonempty(skipped.get(field))
                    for field in (
                        "waived_by",
                        "accepted_by",
                        "authority",
                        "authority_ref",
                    )
                ):
                    errors.append(
                        f"required command {command_id} skipped waiver "
                        "requires an actor"
                    )
                if not any(
                    _nonempty(skipped.get(field))
                    for field in ("waiver_scope", "scope")
                ):
                    errors.append(
                        f"required command {command_id} skipped waiver "
                        "requires scope"
                    )
                continue
            if skipped.get("blocking") is False:
                errors.append(
                    f"required command {command_id} was skipped without "
                    "an approved waiver"
                )
            else:
                errors.append(
                    f"required command {command_id} was skipped and is blocking"
                )
            continue
        if matching:
            statuses = ", ".join(
                sorted({record[3] or "missing" for record in matching})
            )
            errors.append(
                f"required command {command_id} matching evidence is not "
                f"pass-like; got {statuses}"
            )
            continue
        errors.append(
            "required command has no matching evidence: "
            + (command_id or command)
        )
