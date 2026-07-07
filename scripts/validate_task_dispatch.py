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
LEVEL_STATUSES = {"PENDING", "PASS", "FAIL", "BLOCKED", "WAIVED", "N/A"}
TASK_DONE_STATUSES = {"VERIFIED", "CLOSED"}
EVIDENCE_DONE_STATUSES = {"VERIFIED"}
PASSLIKE = {"PASS", "N/A", "WAIVED"}
ACTIVE_RUN_STATUSES = {"RUNNING", "ACTIVE", "IN_PROGRESS"}
ACTIVE_LOCK_STATUSES = {"ACTIVE", "HELD"}


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
        if char == separator and quote is None:
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
        if char == ":" and quote is None:
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

        pair = split_key_value(item_text)
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


def validate_schema_dir(schema_dir: Path | None, errors: list[str]) -> None:
    if schema_dir is None:
        return
    for filename in ["task.schema.json", "evidence.schema.json"]:
        path = schema_dir / filename
        if not path.exists():
            errors.append(f"schema file missing: {path}")
            continue
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"schema file is not valid JSON: {path}: {exc}")


def validate_runs(label: str, runs: list[Any], errors: list[str]) -> None:
    for index, raw_run in enumerate(runs):
        run = require_mapping(f"{label}.runs[{index}]", raw_run, errors)
        if not run:
            continue
        for field in ["id", "attempt", "status"]:
            if not is_nonempty(run.get(field)):
                errors.append(f"{label}.runs[{index}].{field} is required")
        if upper(run.get("status")) in ACTIVE_RUN_STATUSES:
            lease = require_mapping(f"{label}.runs[{index}].lease", run.get("lease"), errors)
            for field in ["resource", "owner", "status"]:
                if not is_nonempty(lease.get(field)):
                    errors.append(f"{label}.runs[{index}].lease.{field} is required for active runs")
            if not (is_nonempty(lease.get("expires_at")) or is_nonempty(lease.get("release_rule"))):
                errors.append(
                    f"{label}.runs[{index}].lease requires expires_at or release_rule for active runs"
                )


def validate_locks(locks: list[Any], errors: list[str]) -> None:
    active_resources: set[str] = set()
    for index, raw_lock in enumerate(locks):
        lock = require_mapping(f"task.resources.locks[{index}]", raw_lock, errors)
        if not lock:
            continue
        resource = str(lock.get("resource") or "").strip()
        status = upper(lock.get("status"))
        if not resource:
            errors.append(f"task.resources.locks[{index}].resource is required")
        if status in ACTIVE_LOCK_STATUSES:
            for field in ["owner", "mode"]:
                if not is_nonempty(lock.get(field)):
                    errors.append(f"task.resources.locks[{index}].{field} is required for active locks")
            if not (is_nonempty(lock.get("expires_at")) or is_nonempty(lock.get("release_rule"))):
                errors.append(
                    f"task.resources.locks[{index}] requires expires_at or release_rule for active locks"
                )
            if resource in active_resources:
                errors.append(f"duplicate active resource lock: {resource}")
            active_resources.add(resource)


def validate_surface_evidence(
    changed_surface: list[Any],
    artifacts: dict[str, Any],
    verified: bool,
    errors: list[str],
) -> None:
    if not verified:
        return
    normalized = {str(item).strip().lower() for item in changed_surface}
    checks = [
        ({"api", "http", "service"}, "api"),
        ({"database", "db", "sql", "migration"}, "sql"),
        ({"ui", "frontend", "browser"}, "browser"),
        ({"release", "deploy", "package"}, "release"),
    ]
    for names, artifact_key in checks:
        if normalized.intersection(names) and not as_list(artifacts.get(artifact_key)):
            errors.append(
                f"verified evidence for surface {sorted(names)[0]} requires artifacts.{artifact_key}"
            )


def validate_records(
    task: dict[str, Any],
    evidence: dict[str, Any],
    schema_dir: Path | None,
    gate_ready: bool = False,
) -> list[str]:
    errors: list[str] = []
    validate_schema_dir(schema_dir, errors)

    for field in [
        "id",
        "type",
        "title",
        "priority",
        "status",
        "scope",
        "verification",
        "dependencies",
        "resources",
        "runs",
        "closure",
    ]:
        if field not in task:
            errors.append(f"task.{field} is required")

    for field in ["task_id", "changed_surface", "runtime_shape", "levels", "artifacts", "runs", "blockers", "conclusion"]:
        if field not in evidence:
            errors.append(f"evidence.{field} is required")

    task_id = str(task.get("id") or "").strip()
    evidence_task_id = str(evidence.get("task_id") or "").strip()
    if task_id and not re.fullmatch(r"TASK-[A-Za-z0-9._-]+", task_id):
        errors.append("task.id must match TASK-<id>")
    if task_id and evidence_task_id and task_id != evidence_task_id:
        errors.append(f"task.id ({task_id}) does not match evidence.task_id ({evidence_task_id})")

    if upper(task.get("type")) not in TASK_TYPES:
        errors.append(f"task.type must be one of: {', '.join(sorted(TASK_TYPES))}")
    if upper(task.get("priority")) not in PRIORITIES:
        errors.append(f"task.priority must be one of: {', '.join(sorted(PRIORITIES))}")
    if upper(task.get("status")) not in TASK_STATUSES:
        errors.append(f"task.status must be one of: {', '.join(sorted(TASK_STATUSES))}")

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
    for field in ["allowed_files", "read_only_files", "forbidden_files", "non_goals", "stop_conditions"]:
        if field in scope:
            require_list(f"task.scope.{field}", scope.get(field), errors)

    verification = require_mapping("task.verification", task.get("verification"), errors)
    required_levels = [str(level).strip() for level in as_list(verification.get("required_levels"))]
    if not required_levels:
        errors.append("task.verification.required_levels must name at least one level")
    for level in required_levels:
        if level not in LEVELS:
            errors.append(f"invalid required evidence level: {level}")

    dependencies = require_mapping("task.dependencies", task.get("dependencies"), errors)
    for field in ["requires", "blocks"]:
        values = require_list(f"task.dependencies.{field}", dependencies.get(field), errors)
        if task_id and task_id in values:
            errors.append(f"task.dependencies.{field} must not reference the task itself")

    resources = require_mapping("task.resources", task.get("resources"), errors)
    validate_locks(require_list("task.resources.locks", resources.get("locks"), errors), errors)
    validate_runs("task", require_list("task.runs", task.get("runs"), errors), errors)

    levels = require_mapping("evidence.levels", evidence.get("levels"), errors)
    artifacts = require_mapping("evidence.artifacts", evidence.get("artifacts"), errors)
    conclusion = require_mapping("evidence.conclusion", evidence.get("conclusion"), errors)
    blockers = require_list("evidence.blockers", evidence.get("blockers"), errors)

    for level in LEVELS:
        level_record = require_mapping(f"evidence.levels.{level}", levels.get(level), errors)
        if "status" not in level_record:
            errors.append(f"evidence.levels.{level}.status is required")
        elif upper(level_record.get("status")) not in LEVEL_STATUSES:
            errors.append(
                f"evidence.levels.{level}.status must be one of: {', '.join(sorted(LEVEL_STATUSES))}"
            )
    for level in required_levels:
        if level not in levels:
            errors.append(f"required level missing from evidence: {level}")

    for field in ["commands", "files_changed", "api", "sql", "browser", "logs", "screenshots", "release", "ids"]:
        require_list(f"evidence.artifacts.{field}", artifacts.get(field), errors)

    validate_runs("evidence", require_list("evidence.runs", evidence.get("runs"), errors), errors)

    if upper(conclusion.get("status")) not in EVIDENCE_STATUSES:
        errors.append(f"evidence.conclusion.status must be one of: {', '.join(sorted(EVIDENCE_STATUSES))}")

    if gate_ready:
        if upper(task.get("status")) not in TASK_DONE_STATUSES:
            errors.append("gate-ready validation requires task.status to be VERIFIED or CLOSED")
        if upper(conclusion.get("status")) not in EVIDENCE_DONE_STATUSES:
            errors.append("gate-ready validation requires evidence.conclusion.status to be VERIFIED")
        if blockers:
            errors.append("gate-ready validation requires evidence.blockers to be empty")

    verified = (
        upper(task.get("status")) in TASK_DONE_STATUSES
        or upper(conclusion.get("status")) in EVIDENCE_DONE_STATUSES
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

    changed_surface = require_list("evidence.changed_surface", evidence.get("changed_surface"), errors)
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
