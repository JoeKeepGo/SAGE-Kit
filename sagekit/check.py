from __future__ import annotations

import re
from pathlib import Path

from .findings import Finding


REQUIRED_DOCS = [
    "docs/PROJECT_PROFILE.md",
    "docs/QUALITY_GATES.md",
    "docs/ACTIVE_CONTEXT.md",
    "docs/DOC_ROUTING.md",
]

RECOMMENDED_DOCS = [
    "docs/TECHNICAL_DESIGN.md",
    "docs/ENGINEERING_SYSTEM.md",
    "docs/APPROVAL_GATES.md",
    "docs/MILESTONE_ROADMAP.md",
]

PERMISSION_MODES = [
    "READ_ONLY_REVIEW",
    "WRITE_AUTHORIZED",
    "CORRECTIVE_AUTHORIZED",
    "ENVIRONMENT_WRITE_AUTHORIZED",
    "SUBMIT_AUTHORIZED",
]


def run_check(start: Path, gate_ready: bool = False) -> list[Finding]:
    root = detect_root(start)
    findings: list[Finding] = [
        Finding("PASS", "project-root", relpath(root, root), None, f"using {root}")
    ]
    findings.extend(check_required_docs(root))
    findings.extend(check_recommended_docs(root))
    findings.extend(check_active_context(root))
    findings.extend(check_doc_routing(root))
    findings.extend(check_phase_docs(root))
    findings.extend(check_completion_reports(root))
    findings.extend(check_task_dispatch(root, gate_ready=gate_ready))
    return findings


def detect_root(start: Path) -> Path:
    current = start.resolve()
    if current.is_file():
        current = current.parent
    for candidate in [current, *current.parents]:
        if (candidate / ".git").exists():
            return candidate
        if any((candidate / path).exists() for path in REQUIRED_DOCS):
            return candidate
    return current


def relpath(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def check_required_docs(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for item in REQUIRED_DOCS:
        path = root / item
        if not path.exists():
            findings.append(
                Finding(
                    "FAIL",
                    "required-docs",
                    item,
                    None,
                    f"{item} missing",
                    "Create this SAGE-Kit project document or run check from the intended project root.",
                )
            )
        elif path.is_file() and read_text(path).strip():
            findings.append(Finding("PASS", "required-docs", item, None, f"{item} exists"))
        else:
            findings.append(
                Finding(
                    "FAIL",
                    "required-docs",
                    item,
                    None,
                    f"{item} is empty or not a file",
                    "Fill the required document with current project governance facts.",
                )
            )
    return findings


def check_recommended_docs(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for item in RECOMMENDED_DOCS:
        path = root / item
        if path.exists():
            findings.append(Finding("PASS", "recommended-docs", item, None, f"{item} exists"))
        else:
            findings.append(
                Finding(
                    "WARN",
                    "recommended-docs",
                    item,
                    None,
                    f"{item} missing",
                    "Add it when the project needs standard SAGE-Kit governance depth.",
                )
            )
    return findings


def check_active_context(root: Path) -> list[Finding]:
    path = root / "docs/ACTIVE_CONTEXT.md"
    if not path.exists():
        return []
    text = read_text(path)
    findings: list[Finding] = []
    if text.strip():
        findings.append(Finding("PASS", "active-context", relpath(root, path), None, "not empty"))
    else:
        findings.append(
            Finding(
                "FAIL",
                "active-context",
                relpath(root, path),
                None,
                "ACTIVE_CONTEXT.md is empty",
                "Keep a compact current-state snapshot.",
            )
        )
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) > 200:
        findings.append(
            Finding(
                "WARN",
                "active-context",
                relpath(root, path),
                None,
                f"{len(lines)} non-empty lines; startup context may be too large",
                "Replace stale state with a compact summary instead of appending history.",
            )
        )
    else:
        findings.append(
            Finding("PASS", "active-context", relpath(root, path), None, "compact enough for startup context")
        )
    lower = text.lower()
    history_markers = ["session log", "chat transcript", "append-only", "conversation history"]
    if any(marker in lower for marker in history_markers):
        findings.append(
            Finding(
                "WARN",
                "active-context",
                relpath(root, path),
                None,
                "looks like append-only session history",
                "Keep only durable current-state facts.",
            )
        )
    return findings


def check_doc_routing(root: Path) -> list[Finding]:
    path = root / "docs/DOC_ROUTING.md"
    if not path.exists():
        return []
    text = read_text(path)
    lower = text.lower()
    findings: list[Finding] = []
    if any(token in lower for token in ["routing policy", "task routing", "read set", "read the"]):
        findings.append(Finding("PASS", "doc-routing", relpath(root, path), None, "contains routing policy"))
    else:
        findings.append(
            Finding(
                "FAIL",
                "doc-routing",
                relpath(root, path),
                None,
                "does not name a routing policy or task-type read set",
                "Describe which docs agents should read for planning, implementation, review, and closeout.",
            )
        )
    if any(token in lower for token in ["progress log", "done:", "today i", "changed files"]):
        findings.append(
            Finding(
                "WARN",
                "doc-routing",
                relpath(root, path),
                None,
                "looks like it may contain progress log material",
                "Keep progress in ledgers or completion reports, not DOC_ROUTING.md.",
            )
        )
    return findings


def check_phase_docs(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in sorted((root / "docs").glob("M*/[0-9][0-9]-*.md")):
        if "_TEMPLATE" in path.name:
            continue
        text = read_text(path)
        findings.extend(check_one_phase(root, path, text))
    return findings


def check_one_phase(root: Path, path: Path, text: str) -> list[Finding]:
    display = relpath(root, path)
    lower = text.lower()
    findings: list[Finding] = []
    if re.search(r"(^|\n)\s*#{1,3}\s*(goal|objective)\b", text, re.IGNORECASE) or re.search(
        r"\b(goal|objective)\s*:", text, re.IGNORECASE
    ):
        findings.append(Finding("PASS", "phase-goal", display, None, "goal or objective is named"))
    else:
        findings.append(Finding("FAIL", "phase-goal", display, None, "missing goal or objective"))

    if "governance level" in lower and re.search(r"\b(light|standard|heavy)\b", text, re.IGNORECASE):
        findings.append(Finding("PASS", "phase-governance", display, None, "governance level is named"))
    else:
        findings.append(
            Finding(
                "FAIL",
                "phase-governance",
                display,
                None,
                "missing governance level",
                "Name Light, Standard, or Heavy for this phase.",
            )
        )

    if "permission mode" in lower and any(mode.lower() in lower for mode in PERMISSION_MODES):
        findings.append(Finding("PASS", "phase-permission", display, None, "permission mode is named"))
    else:
        findings.append(
            Finding(
                "FAIL",
                "phase-permission",
                display,
                None,
                "missing permission mode",
                "Name the Authority Matrix permission mode for this phase.",
            )
        )

    if "allowed files" in lower:
        findings.append(Finding("PASS", "phase-boundary", display, None, "allowed files are named"))
    else:
        findings.append(
            Finding(
                "FAIL",
                "phase-boundary",
                display,
                None,
                "missing allowed files",
                "Name allowed, read-only, and forbidden files or explain that no writes are allowed.",
            )
        )
    if "forbidden files" in lower or re.search(r"\bforbidden\s*:\s*(none|n/a)", lower):
        findings.append(Finding("PASS", "phase-boundary", display, None, "forbidden files are named or explicit"))
    else:
        findings.append(
            Finding(
                "FAIL",
                "phase-boundary",
                display,
                None,
                "missing forbidden files",
                "Name forbidden files or state that none apply.",
            )
        )

    if has_evidence_or_na(text, "test"):
        findings.append(Finding("PASS", "phase-tests", display, None, "tests are named or explicitly N/A"))
    else:
        findings.append(
            Finding(
                "FAIL",
                "phase-tests",
                display,
                None,
                "missing tests or non-applicability reason",
                "Name exact test commands or state N/A with a concrete reason.",
            )
        )

    if has_evidence_or_na(text, "runtime smoke"):
        findings.append(
            Finding("PASS", "phase-runtime-smoke", display, None, "runtime smoke is named or explicitly N/A")
        )
    else:
        findings.append(
            Finding(
                "FAIL",
                "phase-runtime-smoke",
                display,
                None,
                "missing runtime smoke or non-applicability reason",
                "Name exact runtime smoke or state N/A with a concrete reason.",
            )
        )

    if "stop conditions" in lower or "stop if" in lower:
        findings.append(Finding("PASS", "phase-stop-conditions", display, None, "stop conditions are named"))
    else:
        findings.append(Finding("FAIL", "phase-stop-conditions", display, None, "missing stop conditions"))

    findings.extend(check_adapter_evidence(root, path, text))
    return findings


def has_evidence_or_na(text: str, topic: str) -> bool:
    section = topic_section(text, topic)
    if not section.strip():
        return False
    lower = section.lower()
    if re.search(r"\bn/?a\b.{0,80}\b(because|reason|not applicable|planning-only|planning only)\b", lower):
        return True
    command_markers = [
        "python ",
        "python -m",
        "pytest",
        "unittest",
        "npm test",
        "pnpm test",
        "go test",
        "cargo test",
        "curl ",
        "browser",
        "cli",
        "process",
        "smoke:",
        "tests:",
    ]
    return any(marker in lower for marker in command_markers)


def topic_section(text: str, topic: str) -> str:
    if topic == "runtime smoke":
        heading_patterns = [r"\bruntime\s+smoke\b"]
        line_patterns = [r"\bruntime\s+smoke\b"]
    else:
        heading_patterns = [r"\btest\s+plan\b", r"\btests?\b"]
        line_patterns = [r"\btests?\b"]

    lines = text.splitlines()
    section: list[str] = []
    active = False
    for line in lines:
        heading = re.match(r"^\s*(#{1,6})\s+(.+?)\s*$", line)
        if heading:
            title = heading.group(2).strip().lower()
            if active:
                break
            if any(re.search(pattern, title) for pattern in heading_patterns):
                active = True
                section.append(line)
            continue
        if active:
            section.append(line)

    if section:
        return "\n".join(section)

    return "\n".join(
        line for line in lines if any(re.search(pattern, line, re.IGNORECASE) for pattern in line_patterns)
    )


def check_completion_reports(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    docs = root / "docs"
    if not docs.exists():
        return findings
    for path in sorted(docs.glob("M*/*COMPLETION*.md")) + sorted(docs.glob("M*/*completion*.md")):
        if "_TEMPLATE" in path.name:
            continue
        text = read_text(path)
        findings.extend(check_one_completion_report(root, path, text))
    return findings


def check_one_completion_report(root: Path, path: Path, text: str) -> list[Finding]:
    display = relpath(root, path)
    lower = text.lower()
    required = {
        "completion-files-changed": "files changed",
        "completion-tests": "tests run",
        "completion-runtime-smoke": "runtime smoke",
        "completion-skipped-checks": "skipped checks",
        "completion-approval-gates": "approval gates",
    }
    findings: list[Finding] = []
    for rule, phrase in required.items():
        if phrase in lower:
            findings.append(Finding("PASS", rule, display, None, f"{phrase} is named"))
        else:
            findings.append(Finding("FAIL", rule, display, None, f"missing {phrase}"))
    if "remaining gaps" in lower or "next action" in lower or "handoff" in lower:
        findings.append(Finding("PASS", "completion-next-action", display, None, "remaining gaps or next action named"))
    else:
        findings.append(
            Finding("FAIL", "completion-next-action", display, None, "missing remaining gaps or next action")
        )
    findings.extend(check_adapter_evidence(root, path, text))
    return findings


def check_adapter_evidence(root: Path, path: Path, text: str) -> list[Finding]:
    lower = text.lower()
    if "adapter" not in lower and "capability" not in lower:
        return []
    if "_template" in path.name.lower():
        return []
    display = relpath(root, path)
    required = [
        ("adapter-authorization", ["authorization level", "metadata-only", "read-only", "write-inside-boundary"]),
        ("adapter-boundary", ["boundary served", "sage-kit boundary", "allowed files"]),
        ("adapter-evidence", ["evidence"]),
        ("adapter-fallback", ["fallback"]),
    ]
    findings: list[Finding] = []
    for rule, tokens in required:
        if any(token in lower for token in tokens):
            findings.append(Finding("PASS", rule, display, None, f"{rule} recorded"))
        else:
            findings.append(Finding("FAIL", rule, display, None, f"missing {rule.replace('-', ' ')}"))
    return findings


def check_task_dispatch(root: Path, gate_ready: bool = False) -> list[Finding]:
    findings: list[Finding] = []
    docs = root / "docs"
    if not docs.exists():
        return findings
    for task_path in sorted(docs.glob("M*/dispatch/**/task.yaml")):
        evidence_path = task_path.with_name("evidence.yaml")
        display = relpath(root, task_path)
        if not evidence_path.exists():
            findings.append(
                Finding(
                    "FAIL",
                    "task-dispatch",
                    display,
                    None,
                    "task.yaml is present but evidence.yaml is missing",
                )
            )
            continue
        findings.extend(validate_task_dispatch_pair(root, task_path, evidence_path, gate_ready))
    return findings


def validate_task_dispatch_pair(
    root: Path, task_path: Path, evidence_path: Path, gate_ready: bool
) -> list[Finding]:
    try:
        from .task_dispatch_validator import ValidationError, load_record, validate_records
    except Exception as exc:
        return [
            Finding(
                "FAIL",
                "task-dispatch",
                relpath(root, task_path),
                None,
                f"could not load Task Dispatch validator: {exc}",
            )
        ]

    try:
        task = load_record(task_path)
        evidence = load_record(evidence_path)
        if not isinstance(task, dict):
            raise ValidationError(f"task record must be a mapping: {task_path}")
        if not isinstance(evidence, dict):
            raise ValidationError(f"evidence record must be a mapping: {evidence_path}")
        schema_dir = default_schema_dir(root)
        errors = validate_records(task, evidence, schema_dir, gate_ready=gate_ready)
    except ValidationError as exc:
        errors = [str(exc)]

    if errors:
        return [
            Finding(
                "FAIL",
                "task-dispatch",
                relpath(root, task_path),
                None,
                error,
                "Fix task.yaml/evidence.yaml or run the standalone validator for detailed context.",
            )
            for error in errors
        ]
    return [
        Finding(
            "PASS",
            "task-dispatch",
            relpath(root, task_path),
            None,
            "Task Dispatch validator passed",
        )
    ]


def default_schema_dir(root: Path) -> Path | None:
    candidates = [
        root / "docs/profiles/task-dispatch/schemas",
        Path(__file__).resolve().parents[1] / "docs/profiles/task-dispatch/schemas",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None
