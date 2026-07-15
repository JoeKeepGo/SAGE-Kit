#!/usr/bin/env python3
"""Validate SAGE-Kit Task Dispatch task/evidence records.

The validator intentionally has no required third-party dependencies. If
PyYAML is installed, it is used. Otherwise a small YAML subset parser handles
the profile templates and ordinary record files that use mappings, lists,
quoted strings, scalars, booleans, and nulls.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


LEVELS = ["L0", "L1", "L2", "L3", "L4"]
TASK_TYPES = {"BUG", "SPEC", "CHORE", "REVIEW", "INTEGRATION", "RELEASE"}
PRIORITIES = {"P0", "P1", "P2", "P3"}
TASK_STATUSES = {
    "NEW",
    "TRIAGED",
    "READY",
    "IN_PROGRESS",
    "READY_FOR_REVIEW",
    "VERIFIED",
    "PARTIAL",
    "BLOCKED",
    "CLOSED",
}
EVIDENCE_STATUSES = {
    "PENDING",
    "VERIFIED",
    "PARTIAL",
    "ENV_BLOCKED",
    "CONTRACT_BLOCKED",
    "WORKER_BLOCKED",
    "PM_BLOCKED",
}
BLOCKED_EVIDENCE_STATUSES = {
    "ENV_BLOCKED",
    "CONTRACT_BLOCKED",
    "WORKER_BLOCKED",
    "PM_BLOCKED",
}
LEVEL_STATUSES = {"PENDING", "PASS", "FAIL", "BLOCKED", "WAIVED", "N/A"}
TASK_DONE_STATUSES = {"VERIFIED", "CLOSED"}
EVIDENCE_DONE_STATUSES = {"VERIFIED"}
PASSLIKE = {"PASS", "N/A", "WAIVED"}
REVIEW_RESULTS = {
    "PENDING",
    "ACCEPTABLE",
    "ACCEPTABLE_WITH_CONCERNS",
    "NEEDS_CORRECTION",
    "BLOCKED",
    "N/A",
}
ACCEPTABLE_REVIEW_RESULTS = {"ACCEPTABLE", "ACCEPTABLE_WITH_CONCERNS"}
ACTIVE_RUN_STATUSES = {"RUNNING"}
ACTIVE_LOCK_STATUSES = {"ACTIVE", "HELD"}
RUN_STATUSES = {"PENDING", "RUNNING", "PASSED", "FAILED", "BLOCKED", "ABORTED"}
TERMINAL_RUN_STATUSES = {"PASSED", "FAILED", "BLOCKED", "ABORTED"}
LEASE_STATUSES = {"ACTIVE", "HELD", "RELEASED", "EXPIRED"}
RELEASED_LEASE_STATUSES = {"RELEASED", "EXPIRED"}
LOCK_STATUSES = {"ACTIVE", "HELD", "RELEASED", "EXPIRED"}
RESOURCE_MODES = {"EXCLUSIVE", "SHARED"}


class ValidationError(Exception):
    pass


def strip_comment(line: str) -> str:
    quote: str | None = None
    escaped = False
    for index, char in enumerate(line):
        if escaped:
            escaped = False
            continue
        if char == "\\" and quote == '"':
            escaped = True
            continue
        if char in {"'", '"'}:
            if quote is None:
                quote = char
            elif quote == char:
                quote = None
            continue
        if char == "#" and quote is None:
            if index == 0 or line[index - 1].isspace():
                return line[:index].rstrip()
    return line.rstrip()


def split_unquoted(text: str, separator: str) -> list[str]:
    parts: list[str] = []
    quote: str | None = None
    escaped = False
    flow_depth = 0
    start = 0
    for index, char in enumerate(text):
        if escaped:
            escaped = False
            continue
        if char == "\\" and quote == '"':
            escaped = True
            continue
        if char in {"'", '"'}:
            if quote is None:
                quote = char
            elif quote == char:
                quote = None
            continue
        if quote is None and char in "[{":
            flow_depth += 1
            continue
        if quote is None and char in "]}":
            flow_depth = max(0, flow_depth - 1)
            continue
        if char == separator and quote is None and flow_depth == 0:
            parts.append(text[start:index].strip())
            start = index + 1
    parts.append(text[start:].strip())
    return parts


def split_key_value(text: str) -> tuple[str, str] | None:
    quote: str | None = None
    escaped = False
    for index, char in enumerate(text):
        if escaped:
            escaped = False
            continue
        if char == "\\" and quote == '"':
            escaped = True
            continue
        if char in {"'", '"'}:
            if quote is None:
                quote = char
            elif quote == char:
                quote = None
            continue
        if (
            char == ":"
            and quote is None
            and (index + 1 == len(text) or text[index + 1].isspace())
        ):
            return text[:index].strip(), text[index + 1 :].strip()
    return None


def parse_scalar(text: str) -> Any:
    text = text.strip()
    if text == "":
        return ""
    if text in {"null", "Null", "NULL", "~"}:
        return None
    if text in {"true", "True", "TRUE"}:
        return True
    if text in {"false", "False", "FALSE"}:
        return False
    if (text.startswith('"') and text.endswith('"')) or (
        text.startswith("'") and text.endswith("'")
    ):
        return text[1:-1]
    if text.startswith("[") and text.endswith("]"):
        inside = text[1:-1].strip()
        if not inside:
            return []
        return [parse_scalar(part) for part in split_unquoted(inside, ",")]
    if text.startswith("{") and text.endswith("}"):
        inside = text[1:-1].strip()
        if not inside:
            return {}
        result: dict[str, Any] = {}
        for part in split_unquoted(inside, ","):
            pair = split_key_value(part)
            if pair is None:
                raise ValidationError(f"expected key/value in flow mapping near: {part}")
            raw_key, raw_value = pair
            key = parse_scalar(raw_key)
            if not isinstance(key, str) or not key.strip():
                raise ValidationError(f"invalid flow mapping key near: {part}")
            if key in result:
                raise ValidationError(f"duplicate flow mapping key: {key}")
            result[key] = parse_scalar(raw_value)
        return result
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    if re.fullmatch(r"-?\d+\.\d+", text):
        return float(text)
    return text


def preprocess_yaml(text: str) -> list[tuple[int, str]]:
    lines: list[tuple[int, str]] = []
    for raw in text.splitlines():
        if not raw.strip():
            continue
        stripped = strip_comment(raw)
        if not stripped.strip():
            continue
        if stripped.lstrip().startswith("---"):
            continue
        indent = len(stripped) - len(stripped.lstrip(" "))
        lines.append((indent, stripped.strip()))
    return lines


def parse_yaml_subset(text: str) -> Any:
    lines = preprocess_yaml(text)
    if not lines:
        return {}
    result, index = parse_block(lines, 0, lines[0][0])
    if index != len(lines):
        raise ValidationError(f"could not parse YAML near: {lines[index][1]}")
    return result


def parse_block(lines: list[tuple[int, str]], index: int, indent: int) -> tuple[Any, int]:
    if index >= len(lines):
        return {}, index
    current_indent, content = lines[index]
    if current_indent != indent:
        raise ValidationError(f"unexpected indentation near: {content}")
    if content.startswith("- "):
        return parse_sequence(lines, index, indent)
    return parse_mapping(lines, index, indent)


def parse_mapping(lines: list[tuple[int, str]], index: int, indent: int) -> tuple[dict[str, Any], int]:
    result: dict[str, Any] = {}
    while index < len(lines):
        current_indent, content = lines[index]
        if current_indent < indent:
            break
        if current_indent > indent:
            raise ValidationError(f"unexpected nested value near: {content}")
        if content.startswith("- "):
            break
        pair = split_key_value(content)
        if pair is None:
            raise ValidationError(f"expected key/value near: {content}")
        key, value = pair
        if not key:
            raise ValidationError(f"empty key near: {content}")
        if value == "":
            index += 1
            if index < len(lines) and lines[index][0] > indent:
                child, index = parse_block(lines, index, lines[index][0])
                result[key] = child
            else:
                result[key] = {}
        else:
            result[key] = parse_scalar(value)
            index += 1
    return result, index


def parse_sequence(lines: list[tuple[int, str]], index: int, indent: int) -> tuple[list[Any], int]:
    result: list[Any] = []
    while index < len(lines):
        current_indent, content = lines[index]
        if current_indent < indent:
            break
        if current_indent > indent:
            raise ValidationError(f"unexpected nested list value near: {content}")
        if not content.startswith("- "):
            break
        item_text = content[2:].strip()
        if item_text == "":
            index += 1
            if index < len(lines) and lines[index][0] > indent:
                child, index = parse_block(lines, index, lines[index][0])
            else:
                child = None
            result.append(child)
            continue

        pair = None if item_text.startswith(("{", "[")) else split_key_value(item_text)
        if pair is None:
            item = parse_scalar(item_text)
            index += 1
        else:
            key, value = pair
            item = {key: parse_scalar(value) if value else {}}
            index += 1
            if value == "" and index < len(lines) and lines[index][0] > indent:
                child, index = parse_block(lines, index, lines[index][0])
                item[key] = child
        if index < len(lines) and lines[index][0] > indent:
            child, index = parse_block(lines, index, lines[index][0])
            if isinstance(item, dict) and isinstance(child, dict):
                item.update(child)
            else:
                raise ValidationError(f"unexpected nested value after list item: {item_text}")
        result.append(item)
    return result, index


def load_record(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        loaded = yaml.safe_load(text)
        return loaded if loaded is not None else {}
    except ImportError:
        pass
    except Exception as exc:
        raise ValidationError(f"{path}: YAML parse failed: {exc}") from exc

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return parse_yaml_subset(text)


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def is_nonempty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip()) and value.strip().lower() not in {"n/a", "none", "null"}
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def upper(value: Any) -> str:
    return str(value or "").strip().upper()


def require_mapping(name: str, value: Any, errors: list[str]) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    errors.append(f"{name} must be a mapping")
    return {}


def require_list(name: str, value: Any, errors: list[str]) -> list[Any]:
    if isinstance(value, list):
        return value
    errors.append(f"{name} must be a list")
    return []


def validate_string_list(name: str, value: Any, errors: list[str]) -> list[Any]:
    values = require_list(name, value, errors)
    for index, item in enumerate(values):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{name} element {index} must be a non-empty string")
    return values


def command_record(
    name: str, value: Any, errors: list[str]
) -> tuple[str, str, str, str] | None:
    if isinstance(value, str):
        command = " ".join(value.split())
        if not command:
            errors.append(f"{name} element must be a non-empty command string")
            return None
        return "", command, "", ""
    if not isinstance(value, dict):
        errors.append(f"{name} element must be a command string or mapping")
        return None
    id_field = "id" if name == "task.verification.required_commands" else "command_id"
    record_id = value.get(id_field)
    if not isinstance(record_id, str) or not record_id.strip():
        errors.append(f"{name} element mapping requires a non-empty {id_field}")
        record_id = ""
    command_value = value.get("command", value.get("cmd"))
    if not isinstance(command_value, str) or not command_value.strip():
        errors.append(f"{name} element mapping requires a non-empty command")
        return None
    source_value = value.get("source")
    if not isinstance(source_value, str) or not source_value.strip():
        errors.append(f"{name} element mapping requires a non-empty source")
        source_value = ""
    status = upper(value.get("status")) if id_field == "command_id" else ""
    if id_field == "command_id" and status not in {"PASS", "FAIL", "BLOCKED"}:
        errors.append(f"{name} element status must be PASS, FAIL, or BLOCKED")
    return (
        str(record_id).strip(),
        " ".join(command_value.split()),
        " ".join(str(source_value).split()).casefold(),
        status,
    )


def validate_command_list(
    name: str, value: Any, errors: list[str]
) -> list[tuple[str, str, str, str]]:
    records: list[tuple[str, str, str, str]] = []
    record_ids: set[str] = set()
    for item in require_list(name, value, errors):
        record = command_record(name, item, errors)
        if record is not None:
            if record[0] and record[0] in record_ids:
                errors.append(f"{name} contains duplicate command id: {record[0]}")
            record_ids.add(record[0])
            records.append(record)
    return records


def schema_type_matches(value: Any, expected: str) -> bool:
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


def resolve_local_schema_ref(root_schema: dict[str, Any], reference: str) -> Any:
    if not reference.startswith("#/"):
        return None
    current: Any = root_schema
    for token in reference[2:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict) or token not in current:
            return None
        current = current[token]
    return current


def validate_schema_value(
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
        resolved = resolve_local_schema_ref(root_schema, reference)
        if resolved is None:
            errors.append(f"{name} uses unsupported or unresolved schema reference: {reference}")
            return
        validate_schema_value(value, resolved, name, root_schema, errors)
        return

    for branch in schema.get("allOf", []):
        validate_schema_value(value, branch, name, root_schema, errors)
    for keyword, exact_count in [("anyOf", False), ("oneOf", True)]:
        branches = schema.get(keyword)
        if isinstance(branches, list):
            matches = 0
            for branch in branches:
                branch_errors: list[str] = []
                validate_schema_value(value, branch, name, root_schema, branch_errors)
                if not branch_errors:
                    matches += 1
            if (exact_count and matches != 1) or (not exact_count and matches == 0):
                errors.append(f"{name} must satisfy {keyword} schema constraint")
    negated = schema.get("not")
    if isinstance(negated, dict):
        negated_errors: list[str] = []
        validate_schema_value(value, negated, name, root_schema, negated_errors)
        if not negated_errors:
            errors.append(f"{name} must not satisfy prohibited schema constraint")
    condition = schema.get("if")
    if isinstance(condition, dict):
        condition_errors: list[str] = []
        validate_schema_value(value, condition, name, root_schema, condition_errors)
        branch = schema.get("then") if not condition_errors else schema.get("else")
        if isinstance(branch, dict):
            validate_schema_value(value, branch, name, root_schema, errors)

    expected_types = schema.get("type")
    if isinstance(expected_types, str):
        expected_types = [expected_types]
    if isinstance(expected_types, list) and not any(
        isinstance(expected, str) and schema_type_matches(value, expected)
        for expected in expected_types
    ):
        errors.append(f"{name} must match schema type: {' or '.join(map(str, expected_types))}")
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
                validate_schema_value(item, item_schema, f"{name}[{index}]", root_schema, errors)
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
                    validate_schema_value(
                        value[field], field_schema, f"{name}.{field}", root_schema, errors
                    )


def validate_schema_dir(
    schema_dir: Path | None,
    task: dict[str, Any],
    evidence: dict[str, Any],
    errors: list[str],
) -> None:
    if schema_dir is None:
        return
    for label, filename, record in [
        ("task", "task.schema.json", task),
        ("evidence", "evidence.schema.json", evidence),
    ]:
        path = schema_dir / filename
        if not path.exists():
            errors.append(f"schema file missing: {path}")
            continue
        try:
            schema = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"schema file is not valid JSON: {path}: {exc}")
            continue
        if not isinstance(schema, dict):
            errors.append(f"schema file must contain a JSON object: {path}")
            continue
        validate_schema_value(record, schema, label, schema, errors)


def resource_use_flag(run: dict[str, Any], inferred: bool, name: str, errors: list[str]) -> bool:
    aliases = ["uses_shared_resource", "uses_scarce_resource", "shared_resource", "scarce_resource"]
    present = [field for field in aliases if field in run]
    if not present:
        return inferred
    field = present[0]
    value = run[field]
    if not isinstance(value, bool):
        errors.append(f"{name}.{field} must be a boolean")
        return inferred
    return value


def validate_runs(
    label: str,
    runs: list[Any],
    errors: list[str],
    infer_from_active_lock: bool = False,
) -> None:
    run_ids: set[str] = set()
    for index, raw_run in enumerate(runs):
        name = f"{label}.runs[{index}]"
        run = require_mapping(name, raw_run, errors)
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
        status = upper(run.get("status"))
        if status not in RUN_STATUSES:
            errors.append(f"{name}.status must be one of: {', '.join(sorted(RUN_STATUSES))}")

        raw_lease = run.get("lease")
        has_lease = isinstance(raw_lease, dict) and bool(raw_lease)
        uses_resource = resource_use_flag(run, has_lease or infer_from_active_lock, name, errors)
        if not uses_resource and has_lease:
            errors.append(f"{name} declares no shared resource but contains a lease")

        lease: dict[str, Any] = {}
        if uses_resource and status in ACTIVE_RUN_STATUSES:
            lease = require_mapping(f"{name}.lease", raw_lease, errors)
        elif raw_lease is not None:
            lease = require_mapping(f"{name}.lease", raw_lease, errors)

        if lease:
            for field in ["resource", "owner", "mode", "status"]:
                if not is_nonempty(lease.get(field)):
                    errors.append(f"{name}.lease.{field} is required")
            lease_status = upper(lease.get("status"))
            lease_mode = upper(lease.get("mode"))
            if lease_status not in LEASE_STATUSES:
                errors.append(f"{name}.lease.status must be one of: {', '.join(sorted(LEASE_STATUSES))}")
            if lease_mode not in RESOURCE_MODES:
                errors.append(f"{name}.lease.mode must be one of: {', '.join(sorted(RESOURCE_MODES))}")
            if lease_status in ACTIVE_LOCK_STATUSES and not (
                is_nonempty(lease.get("expires_at")) or is_nonempty(lease.get("release_rule"))
            ):
                errors.append(
                    f"{name}.lease requires expires_at or release_rule while active"
                )
            if status in ACTIVE_RUN_STATUSES and lease_status in RELEASED_LEASE_STATUSES:
                errors.append(f"{name} active run contradicts its released lease")
            if status in TERMINAL_RUN_STATUSES and lease_status in ACTIVE_LOCK_STATUSES:
                errors.append(f"{name} terminal run cannot retain an active lease")


def validate_locks(locks: list[Any], errors: list[str]) -> list[dict[str, Any]]:
    active_resources: set[str] = set()
    active_locks: list[dict[str, Any]] = []
    for index, raw_lock in enumerate(locks):
        name = f"task.resources.locks[{index}]"
        lock = require_mapping(name, raw_lock, errors)
        if not lock:
            continue
        resource = str(lock.get("resource") or "").strip()
        status = upper(lock.get("status"))
        if not resource:
            errors.append(f"{name}.resource is required")
        if status not in LOCK_STATUSES:
            errors.append(f"{name}.status must be one of: {', '.join(sorted(LOCK_STATUSES))}")
        mode = upper(lock.get("mode"))
        if mode not in RESOURCE_MODES:
            errors.append(f"{name}.mode must be one of: {', '.join(sorted(RESOURCE_MODES))}")
        if "carried" in lock and not isinstance(lock.get("carried"), bool):
            errors.append(f"{name}.carried must be a boolean")
        if lock.get("carried") is True and not is_nonempty(lock.get("carried_from")):
            errors.append(f"{name}.carried_from is required for carried locks")
        if status in ACTIVE_LOCK_STATUSES:
            for field in ["owner", "mode"]:
                if not is_nonempty(lock.get(field)):
                    errors.append(f"{name}.{field} is required for active locks")
            if not (is_nonempty(lock.get("expires_at")) or is_nonempty(lock.get("release_rule"))):
                errors.append(f"{name} requires expires_at or release_rule for active locks")
            resource_key = resource.casefold()
            if resource_key in active_resources:
                errors.append(f"duplicate active resource lock: {resource}")
            active_resources.add(resource_key)
            active_locks.append(lock)
    return active_locks


def changed_surface_categories(value: Any) -> set[str]:
    surface = str(value).strip().replace("\\", "/").casefold()
    if not surface:
        return set()
    aliases = {
        "api": {"api", "http", "service"},
        "sql": {"database", "db", "sql", "migration"},
        "browser": {"ui", "frontend", "browser"},
        "release": {"release", "deploy", "package"},
    }
    if "/" not in surface:
        return {category for category, names in aliases.items() if surface in names}
    if surface.startswith("docs/") or surface.endswith((".md", ".rst", ".txt")):
        return set()
    segments = {segment for segment in surface.split("/") if segment}
    categories: set[str] = set()
    if segments.intersection({"api", "apis", "routes", "endpoints", "openapi"}):
        categories.add("api")
    if segments.intersection({"db", "database", "sql", "migration", "migrations"}):
        categories.add("sql")
    if segments.intersection({"ui", "frontend", "web", "browser", "components", "pages"}):
        categories.add("browser")
    if segments.intersection({"release", "releases", "deploy", "deployment", "packaging"}):
        categories.add("release")
    return categories


def validate_surface_evidence(
    changed_surface: list[Any],
    artifacts: dict[str, Any],
    verified: bool,
    errors: list[str],
) -> None:
    if not verified:
        return
    categories: set[str] = set()
    for item in changed_surface:
        categories.update(changed_surface_categories(item))
    for artifact_key in ["api", "sql", "browser", "release"]:
        if artifact_key in categories and not as_list(artifacts.get(artifact_key)):
            errors.append(
                f"verified evidence for surface {artifact_key} requires artifacts.{artifact_key}"
            )


def validate_records(
    task: dict[str, Any],
    evidence: dict[str, Any],
    schema_dir: Path | None,
    gate_ready: bool = False,
) -> list[str]:
    errors: list[str] = []
    validate_schema_dir(schema_dir, task, evidence, errors)

    task_required = [
        "id",
        "type",
        "title",
        "priority",
        "status",
        "lifecycle",
        "scope",
        "verification",
        "dependencies",
        "resources",
        "runs",
        "closure",
    ]
    for field in task_required:
        if field not in task:
            errors.append(f"task.{field} is required")

    evidence_required = [
        "task_id",
        "phase",
        "changed_surface",
        "runtime_shape",
        "levels",
        "artifacts",
        "skipped_checks",
        "runs",
        "blockers",
        "conclusion",
    ]
    for field in evidence_required:
        if field not in evidence:
            errors.append(f"evidence.{field} is required")

    task_id = str(task.get("id") or "").strip()
    evidence_task_id = str(evidence.get("task_id") or "").strip()
    if not task_id:
        errors.append("task.id must be a non-empty task id")
    elif not re.fullmatch(r"TASK-[A-Za-z0-9._-]+", task_id):
        errors.append("task.id must match TASK-<id>")
    if not evidence_task_id:
        errors.append("evidence.task_id must be a non-empty task id")
    elif not re.fullmatch(r"TASK-[A-Za-z0-9._-]+", evidence_task_id):
        errors.append("evidence.task_id must match TASK-<id>")
    if task_id and evidence_task_id and task_id != evidence_task_id:
        errors.append(f"task.id ({task_id}) does not match evidence.task_id ({evidence_task_id})")

    if not is_nonempty(task.get("title")):
        errors.append("task.title must be a non-empty string")
    if upper(task.get("type")) not in TASK_TYPES:
        errors.append(f"task.type must be one of: {', '.join(sorted(TASK_TYPES))}")
    if upper(task.get("priority")) not in PRIORITIES:
        errors.append(f"task.priority must be one of: {', '.join(sorted(PRIORITIES))}")
    if upper(task.get("status")) not in TASK_STATUSES:
        errors.append(f"task.status must be one of: {', '.join(sorted(TASK_STATUSES))}")

    lifecycle = require_mapping("task.lifecycle", task.get("lifecycle"), errors)
    for field in ["phase", "review_result", "next_action"]:
        if field not in lifecycle:
            errors.append(f"task.lifecycle.{field} is required")
    for field in ["phase", "next_action"]:
        if not is_nonempty(lifecycle.get(field)):
            errors.append(f"task.lifecycle.{field} must be a non-empty string")
    if upper(lifecycle.get("review_result")) not in REVIEW_RESULTS:
        errors.append(
            f"task.lifecycle.review_result must be one of: {', '.join(sorted(REVIEW_RESULTS))}"
        )

    scope = require_mapping("task.scope", task.get("scope"), errors)
    for field in [
        "objective",
        "allowed_files",
        "read_only_files",
        "forbidden_files",
        "non_goals",
        "stop_conditions",
    ]:
        if field not in scope:
            errors.append(f"task.scope.{field} is required")
    if not is_nonempty(scope.get("objective")):
        errors.append("task.scope.objective must be a non-empty string")
    for field in [
        "allowed_files",
        "read_only_files",
        "forbidden_files",
        "non_goals",
        "stop_conditions",
    ]:
        if field in scope:
            validate_string_list(f"task.scope.{field}", scope.get(field), errors)

    verification = require_mapping("task.verification", task.get("verification"), errors)
    for field in ["required_levels", "evidence_file", "mock_allowed"]:
        if field not in verification:
            errors.append(f"task.verification.{field} is required")
    required_level_values = require_list(
        "task.verification.required_levels", verification.get("required_levels"), errors
    )
    required_levels: list[str] = []
    for index, level in enumerate(required_level_values):
        if not isinstance(level, str) or not level.strip():
            errors.append(
                f"task.verification.required_levels element {index} must be a non-empty string"
            )
            continue
        required_levels.append(level.strip())
    if not required_levels:
        errors.append("task.verification.required_levels must name at least one level")
    for level in required_levels:
        if level not in LEVELS:
            errors.append(f"invalid required evidence level: {level}")
    if not is_nonempty(verification.get("evidence_file")):
        errors.append("task.verification.evidence_file must be a non-empty string")
    if not isinstance(verification.get("mock_allowed"), bool):
        errors.append("task.verification.mock_allowed must be a boolean")
    required_commands = validate_command_list(
        "task.verification.required_commands",
        verification.get("required_commands", []),
        errors,
    )

    dependencies = require_mapping("task.dependencies", task.get("dependencies"), errors)
    for field in ["requires", "blocks"]:
        if field not in dependencies:
            errors.append(f"task.dependencies.{field} is required")
        values = validate_string_list(
            f"task.dependencies.{field}", dependencies.get(field), errors
        )
        if task_id and task_id in values:
            errors.append(f"task.dependencies.{field} must not reference the task itself")

    resources = require_mapping("task.resources", task.get("resources"), errors)
    if "locks" not in resources:
        errors.append("task.resources.locks is required")
    locks = require_list("task.resources.locks", resources.get("locks"), errors)
    active_locks = validate_locks(locks, errors)
    task_runs = require_list("task.runs", task.get("runs"), errors)
    validate_runs("task", task_runs, errors, infer_from_active_lock=bool(active_locks))

    levels = require_mapping("evidence.levels", evidence.get("levels"), errors)
    artifacts = require_mapping("evidence.artifacts", evidence.get("artifacts"), errors)
    conclusion = require_mapping("evidence.conclusion", evidence.get("conclusion"), errors)
    task_authority = task.get("authority") if isinstance(task.get("authority"), dict) else {}
    evidence_authority = (
        evidence.get("authority") if isinstance(evidence.get("authority"), dict) else {}
    )
    blockers = require_list("evidence.blockers", evidence.get("blockers"), errors)
    changed_surface = validate_string_list(
        "evidence.changed_surface", evidence.get("changed_surface"), errors
    )
    if not is_nonempty(evidence.get("phase")):
        errors.append("evidence.phase must be a non-empty string")
    if not is_nonempty(evidence.get("runtime_shape")):
        errors.append("evidence.runtime_shape must be a non-empty string")

    level_commands: list[tuple[str, str, str, str]] = []
    for level in LEVELS:
        if level not in levels:
            errors.append(f"evidence.levels.{level} is required")
        level_record = require_mapping(f"evidence.levels.{level}", levels.get(level), errors)
        if "status" not in level_record:
            errors.append(f"evidence.levels.{level}.status is required")
        elif upper(level_record.get("status")) not in LEVEL_STATUSES:
            errors.append(
                f"evidence.levels.{level}.status must be one of: {', '.join(sorted(LEVEL_STATUSES))}"
            )
        if "evidence" in level_record:
            validate_string_list(
                f"evidence.levels.{level}.evidence", level_record.get("evidence"), errors
            )
        if "commands" in level_record:
            level_commands.extend(
                validate_command_list(
                    f"evidence.levels.{level}.commands", level_record.get("commands"), errors
                )
            )
    for level in required_levels:
        if level not in levels:
            errors.append(f"required level missing from evidence: {level}")

    artifact_fields = [
        "commands",
        "files_changed",
        "api",
        "sql",
        "browser",
        "logs",
        "screenshots",
        "release",
        "ids",
    ]
    for field in artifact_fields:
        if field not in artifacts:
            errors.append(f"evidence.artifacts.{field} is required")
    artifact_commands = validate_command_list(
        "evidence.artifacts.commands", artifacts.get("commands"), errors
    )
    validate_string_list(
        "evidence.artifacts.files_changed", artifacts.get("files_changed"), errors
    )
    for field in ["api", "sql", "browser", "logs", "screenshots", "release", "ids"]:
        require_list(f"evidence.artifacts.{field}", artifacts.get(field), errors)

    skipped_checks = require_list("evidence.skipped_checks", evidence.get("skipped_checks"), errors)
    skipped_by_id: dict[str, dict[str, Any]] = {}
    for index, raw_skip in enumerate(skipped_checks):
        name = f"evidence.skipped_checks[{index}]"
        skipped = require_mapping(name, raw_skip, errors)
        if not skipped:
            continue
        for field in ["id", "check", "reason", "owner", "follow_up"]:
            if not is_nonempty(skipped.get(field)):
                errors.append(f"{name}.{field} is required")
        skip_id = str(skipped.get("id") or "").strip()
        if skip_id in skipped_by_id:
            errors.append(f"evidence.skipped_checks contains duplicate id: {skip_id}")
        elif skip_id:
            skipped_by_id[skip_id] = skipped

    evidence_runs = require_list("evidence.runs", evidence.get("runs"), errors)
    validate_runs(
        "evidence", evidence_runs, errors, infer_from_active_lock=bool(active_locks)
    )

    for field in [
        "status",
        "highest_level",
        "review_result",
        "mock_used",
        "accepted_fallback",
        "next_action",
    ]:
        if field not in conclusion:
            errors.append(f"evidence.conclusion.{field} is required")
    if upper(conclusion.get("status")) not in EVIDENCE_STATUSES:
        errors.append(f"evidence.conclusion.status must be one of: {', '.join(sorted(EVIDENCE_STATUSES))}")
    for field in ["mock_used", "accepted_fallback"]:
        if not isinstance(conclusion.get(field), bool):
            errors.append(f"evidence.conclusion.{field} must be a boolean")
    if not is_nonempty(conclusion.get("next_action")):
        errors.append("evidence.conclusion.next_action must be a non-empty string")
    if upper(conclusion.get("review_result")) not in REVIEW_RESULTS:
        errors.append(
            f"evidence.conclusion.review_result must be one of: {', '.join(sorted(REVIEW_RESULTS))}"
        )

    closure = require_mapping("task.closure", task.get("closure"), errors)
    task_status = upper(task.get("status"))
    evidence_status = upper(conclusion.get("status"))
    task_terminal = task_status in TASK_DONE_STATUSES
    evidence_terminal = evidence_status in EVIDENCE_DONE_STATUSES
    expected_evidence_statuses = {
        "NEW": {"PENDING"},
        "TRIAGED": {"PENDING"},
        "READY": {"PENDING"},
        "IN_PROGRESS": {"PENDING"},
        "READY_FOR_REVIEW": {"PENDING"},
        "VERIFIED": {"VERIFIED"},
        "CLOSED": {"VERIFIED"},
        "PARTIAL": {"PARTIAL"},
        "BLOCKED": BLOCKED_EVIDENCE_STATUSES,
    }
    if task_status in expected_evidence_statuses and evidence_status not in expected_evidence_statuses[task_status]:
        expected = ", ".join(sorted(expected_evidence_statuses[task_status]))
        errors.append(
            f"task.status {task_status} requires evidence.conclusion.status to be one of: {expected}"
        )
    reconciled_fields = [
        *[
            (
                f"task.authority.{field}",
                task_authority.get(field),
                f"evidence.authority.{field}",
                evidence_authority.get(field),
            )
            for field in ["source", "grant", "scope"]
        ],
        ("task.lifecycle.phase", lifecycle.get("phase"), "evidence.phase", evidence.get("phase")),
        (
            "task.lifecycle.review_result",
            upper(lifecycle.get("review_result")),
            "evidence.conclusion.review_result",
            upper(conclusion.get("review_result")),
        ),
        (
            "task.lifecycle.next_action",
            lifecycle.get("next_action"),
            "evidence.conclusion.next_action",
            conclusion.get("next_action"),
        ),
    ]
    for left_name, left_value, right_name, right_value in reconciled_fields:
        if str(left_value or "").strip() != str(right_value or "").strip():
            errors.append(f"{left_name} must match {right_name}")
    if task_terminal:
        for field in ["accepted_by", "accepted_at", "review_result", "evidence_ref"]:
            if not is_nonempty(closure.get(field)):
                errors.append(f"task.closure.{field} is required for VERIFIED or CLOSED tasks")
        if upper(closure.get("review_result")) not in ACCEPTABLE_REVIEW_RESULTS:
            errors.append("task.closure.review_result must be acceptable for VERIFIED or CLOSED tasks")
        if upper(lifecycle.get("review_result")) not in ACCEPTABLE_REVIEW_RESULTS:
            errors.append("terminal task requires an acceptable lifecycle review_result")
    if task_status == "CLOSED" and not is_nonempty(closure.get("closed_at")):
        errors.append("task.closure.closed_at is required for CLOSED tasks")
    if evidence_terminal:
        highest_level = upper(conclusion.get("highest_level"))
        if highest_level not in LEVELS:
            errors.append("evidence.conclusion.highest_level must name L0-L4 when VERIFIED")
        if blockers:
            errors.append("verified evidence cannot retain blockers")

    def active_run_ids(runs: list[Any]) -> set[str]:
        return {
            str(run.get("id") or "").strip()
            for run in runs
            if isinstance(run, dict) and upper(run.get("status")) in ACTIVE_RUN_STATUSES
        }

    task_active_runs = active_run_ids(task_runs)
    evidence_active_runs = active_run_ids(evidence_runs)
    task_run_statuses = {
        str(run.get("id") or "").strip(): upper(run.get("status"))
        for run in task_runs
        if isinstance(run, dict)
    }
    evidence_run_statuses = {
        str(run.get("id") or "").strip(): upper(run.get("status"))
        for run in evidence_runs
        if isinstance(run, dict)
    }
    task_run_ids = set(task_run_statuses)
    evidence_run_ids = set(evidence_run_statuses)
    execution_truth_required = (
        gate_ready
        or task_terminal
        or evidence_terminal
        or bool(task_active_runs or evidence_active_runs)
        or task_status in {"IN_PROGRESS", "READY_FOR_REVIEW", "PARTIAL", "BLOCKED"}
        or evidence_status != "PENDING"
    )
    if execution_truth_required:
        for run_id in sorted(task_run_ids - evidence_run_ids):
            errors.append(f"task run {run_id} is missing from evidence.runs")
        for run_id in sorted(evidence_run_ids - task_run_ids):
            errors.append(f"evidence run {run_id} is missing from task.runs")
    unaccounted_active_locks = [
        lock
        for lock in active_locks
        if not (lock.get("carried") is True and is_nonempty(lock.get("carried_from")))
    ]
    for run_id in sorted(task_run_ids & evidence_run_ids):
        task_run_status = task_run_statuses[run_id]
        evidence_run_status = evidence_run_statuses[run_id]
        if (
            task_run_status in RUN_STATUSES
            and evidence_run_status in RUN_STATUSES
            and task_run_status != evidence_run_status
        ):
            errors.append(
                f"task/evidence run {run_id} status mismatch: "
                f"task {task_run_status} != evidence {evidence_run_status}"
            )
    if task_terminal and (task_active_runs or evidence_active_runs):
        errors.append("terminal task cannot retain active runs")
    if task_terminal and unaccounted_active_locks:
        errors.append("terminal task cannot retain unaccounted active locks")

    if gate_ready:
        if task_status not in TASK_DONE_STATUSES:
            errors.append("gate-ready validation requires task.status to be VERIFIED or CLOSED")
        if evidence_status not in EVIDENCE_DONE_STATUSES:
            errors.append("gate-ready validation requires evidence.conclusion.status to be VERIFIED")
        if blockers:
            errors.append("gate-ready validation requires evidence.blockers to be empty")
        if task_active_runs or evidence_active_runs:
            errors.append("gate-ready validation cannot retain an active run")
        if unaccounted_active_locks:
            errors.append("gate-ready validation cannot retain an unaccounted active lock")

    verified = (
        task_terminal
        or evidence_terminal
        or gate_ready
    )
    if verified:
        for level in required_levels:
            level_record = require_mapping(f"evidence.levels.{level}", levels.get(level), errors)
            status = upper(level_record.get("status"))
            if status not in PASSLIKE:
                errors.append(f"verified task requires {level} to be PASS, N/A, or WAIVED; got {status or 'missing'}")
            if status == "PASS":
                if not (
                    is_nonempty(level_record.get("evidence"))
                    or is_nonempty(level_record.get("commands"))
                    or as_list(artifacts.get("commands"))
                ):
                    errors.append(f"{level} is PASS but has no evidence or commands")
            if status in {"N/A", "WAIVED"} and not is_nonempty(level_record.get("reason")):
                errors.append(f"{level} is {status} but has no reason")
            if status == "WAIVED":
                for field in ["waived_by", "waiver_scope"]:
                    if not is_nonempty(level_record.get(field)):
                        errors.append(f"{level} is WAIVED but has no {field}")

        available_commands = artifact_commands + level_commands
        for command_id, command, source, _ in required_commands:
            matching_records = [
                record
                for record in available_commands
                if record[0] == command_id and record[1] == command and record[2] == source
            ]
            if any(record[3] == "PASS" for record in matching_records):
                continue
            skipped = skipped_by_id.get(command_id) if command_id else None
            if skipped is not None:
                disposition = upper(skipped.get("status") or skipped.get("disposition"))
                waived = skipped.get("waived") is True or disposition == "WAIVED"
                if waived:
                    actor = any(
                        is_nonempty(skipped.get(field))
                        for field in ["waived_by", "accepted_by", "authority", "authority_ref"]
                    )
                    scope_value = any(
                        is_nonempty(skipped.get(field))
                        for field in ["waiver_scope", "scope"]
                    )
                    if not actor:
                        errors.append(f"required command {command_id} skipped waiver requires an actor")
                    if not scope_value:
                        errors.append(f"required command {command_id} skipped waiver requires scope")
                    continue
                if skipped.get("blocking") is False:
                    errors.append(f"required command {command_id} was skipped without an approved waiver")
                else:
                    errors.append(f"required command {command_id} was skipped and is blocking")
                continue
            if matching_records:
                statuses = ", ".join(sorted({record[3] or "missing" for record in matching_records}))
                errors.append(
                    f"required command {command_id} matching evidence is not pass-like; got {statuses}"
                )
                continue
            command_label = command_id or command
            errors.append(f"required command has no matching evidence: {command_label}")

    mock_used = bool(conclusion.get("mock_used"))
    mock_allowed = bool(verification.get("mock_allowed"))
    accepted_fallback = bool(conclusion.get("accepted_fallback"))
    if verified and mock_used and not mock_allowed and not accepted_fallback:
        errors.append("verified task used mock fallback without mock_allowed or accepted_fallback")
    if accepted_fallback and not is_nonempty(conclusion.get("accepted_fallback_reason")):
        errors.append("accepted_fallback requires accepted_fallback_reason")
    if accepted_fallback:
        for field in ["accepted_fallback_by", "accepted_fallback_scope"]:
            if not is_nonempty(conclusion.get(field)):
                errors.append(f"accepted_fallback requires {field}")
    if mock_used:
        mock_requirements = [
            (
                "rationale",
                ["mock_rationale", "accepted_fallback_reason", "rationale"],
            ),
            ("scope", ["mock_scope", "accepted_fallback_scope"]),
            ("follow-up", ["mock_follow_up", "follow_up", "next_action"]),
            (
                "accepted-by/authority metadata",
                [
                    "mock_accepted_by",
                    "mock_acceptance_actor",
                    "accepted_fallback_by",
                    "accepted_by",
                    "authority",
                ],
            ),
        ]
        for description, fields in mock_requirements:
            if not any(is_nonempty(conclusion.get(field)) for field in fields):
                errors.append(f"mock_used requires {description}")

    validate_surface_evidence(changed_surface, artifacts, verified, errors)

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate SAGE-Kit Task Dispatch records.")
    parser.add_argument("--task", required=True, type=Path, help="Path to task.yaml")
    parser.add_argument("--evidence", required=True, type=Path, help="Path to evidence.yaml")
    parser.add_argument("--schema-dir", type=Path, help="Optional directory containing profile schemas")
    parser.add_argument(
        "--gate-ready",
        action="store_true",
        help="Require verified task/evidence status, passlike required levels, and no blockers.",
    )
    args = parser.parse_args()

    try:
        if not args.task.exists():
            raise ValidationError(f"task file missing: {args.task}")
        if not args.evidence.exists():
            raise ValidationError(f"evidence file missing: {args.evidence}")

        task = load_record(args.task)
        evidence = load_record(args.evidence)
        if not isinstance(task, dict):
            raise ValidationError(f"task record must be a mapping: {args.task}")
        if not isinstance(evidence, dict):
            raise ValidationError(f"evidence record must be a mapping: {args.evidence}")

        errors = validate_records(task, evidence, args.schema_dir, args.gate_ready)
        if errors:
            print("Task Dispatch validation failed:", file=sys.stderr)
            for error in errors:
                print(f"- {error}", file=sys.stderr)
            return 1
        print("Task Dispatch validation passed.")
        return 0
    except ValidationError as exc:
        print(f"Task Dispatch validation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
