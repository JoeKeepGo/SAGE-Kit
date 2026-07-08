from __future__ import annotations

import re
import subprocess
from pathlib import Path

from .findings import Finding
from .modes import LEGACY_REQUIRED_DOCS, MODES, STANDARD_DOCS, recommended_docs_for_mode, required_docs_for_mode


REQUIRED_DOCS = LEGACY_REQUIRED_DOCS
RECOMMENDED_DOCS = STANDARD_DOCS

PERMISSION_MODES = [
    "READ_ONLY_REVIEW",
    "WRITE_AUTHORIZED",
    "CORRECTIVE_AUTHORIZED",
    "ENVIRONMENT_WRITE_AUTHORIZED",
    "SUBMIT_AUTHORIZED",
]

SOURCE_REPO_MARKERS = [
    "docs/SAGE_CORE.md",
    "skills/sage-kit/SKILL.md",
    "docs/PROJECT_PROFILE_TEMPLATE.md",
]

SOURCE_REQUIRED_FILES = [
    "pyproject.toml",
    "README.md",
    "README.zh-CN.md",
    "docs/SAGE_CORE.md",
    "docs/PROJECT_PROFILE_TEMPLATE.md",
    "docs/QUALITY_GATES_TEMPLATE.md",
    "docs/ACTIVE_CONTEXT_TEMPLATE.md",
    "docs/DOC_ROUTING_TEMPLATE.md",
    "docs/TECHNICAL_DESIGN_TEMPLATE.md",
    "docs/ENGINEERING_SYSTEM_TEMPLATE.md",
    "docs/APPROVAL_GATES_TEMPLATE.md",
    "docs/templates/PHASE_TEMPLATE.md",
    "docs/templates/MILESTONE_LEDGER_TEMPLATE.md",
    "docs/templates/MILESTONE_CLOSEOUT_TEMPLATE.md",
    "docs/templates/COMPLETION_REPORT_TEMPLATE.md",
    "docs/agent/GOVERNANCE_LEVELS.md",
    "docs/agent/SESSION_ORCHESTRATION.md",
    "docs/agent/CAPABILITY_ADAPTERS.md",
    "docs/profiles/task-dispatch/schemas/task.schema.json",
    "docs/profiles/task-dispatch/schemas/evidence.schema.json",
    "scripts/validate_task_dispatch.py",
    "skills/sage-kit/SKILL.md",
    "sagekit/__init__.py",
    "sagekit/__main__.py",
    "sagekit/cli.py",
    "sagekit/check.py",
    "sagekit/doctor.py",
    "sagekit/init.py",
    "sagekit/modes.py",
    "sagekit/findings.py",
    "sagekit/task_dispatch_validator.py",
    "tests/test_sagekit_check.py",
]

GITIGNORE_RUNTIME_PATTERNS = [
    ".worktrees/",
    "local/",
    ".sagekit/",
    ".runtime/",
    "docs/ACTIVE_CONTEXT.md",
    "docs/DOC_ROUTING.md",
    "docs/M[0-9]*/",
    "docs/runs/",
    "docs/task-records/",
]

FORBIDDEN_RUNTIME_STACK_PATHS = [
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "tsconfig.json",
    "*.ts",
    "*.tsx",
    "*.js",
    "*.jsx",
    "node_modules/**",
]

RESOURCE_REFERENCE_RE = re.compile(
    r"docs/(?:agent|templates|profiles)/[A-Za-z0-9_./-]+\.(?:md|yaml|json)"
)


def run_check(start: Path, gate_ready: bool = False, mode: str | None = None) -> list[Finding]:
    if mode is not None and mode not in MODES:
        raise ValueError(f"unknown SAGE-Kit mode: {mode}")
    root = detect_root(start)
    findings: list[Finding] = [
        Finding("PASS", "project-root", relpath(root, root), None, f"using {root}")
    ]
    if mode is not None:
        findings.append(Finding("PASS", "check-mode", None, None, f"mode: {mode}"))
    findings.extend(check_required_docs(root, required_docs_for_mode(mode)))
    findings.extend(check_recommended_docs(root, recommended_docs_for_mode(mode)))
    findings.extend(check_active_context(root))
    findings.extend(check_doc_routing(root))
    findings.extend(check_phase_docs(root))
    findings.extend(check_completion_reports(root))
    findings.extend(check_task_dispatch(root, gate_ready=gate_ready))
    return findings


def run_source_repo_check(start: Path) -> list[Finding]:
    root = detect_root(start)
    findings: list[Finding] = [
        Finding("PASS", "project-root", relpath(root, root), None, f"using {root}")
    ]
    if is_kit_source_repo(root):
        findings.append(
            Finding(
                "PASS",
                "source-repo",
                relpath(root, root / "docs/SAGE_CORE.md"),
                None,
                "SAGE-Kit source repository detected",
            )
        )
    else:
        findings.append(
            Finding(
                "FAIL",
                "source-repo",
                relpath(root, root),
                None,
                "target does not look like the SAGE-Kit source repository",
                "Use plain sagekit check for adopted projects, or run --source-repo from the SAGE-Kit repository.",
            )
        )
        return findings

    findings.extend(check_source_required_files(root))
    findings.extend(check_source_init_resources(root))
    findings.extend(check_source_resource_references(root))
    findings.extend(check_source_resource_mirrors(root))
    findings.extend(check_source_pyproject(root))
    findings.extend(check_source_gitignore(root))
    findings.extend(check_source_tracked_runtime(root))
    findings.extend(check_source_forbidden_runtime_stack(root))
    return findings


def is_kit_source_repo(root: Path) -> bool:
    return all((root / marker).exists() for marker in SOURCE_REPO_MARKERS)


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


def check_source_required_files(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for item in SOURCE_REQUIRED_FILES:
        path = root / item
        if not path.exists():
            findings.append(
                Finding("FAIL", "source-required-file", item, None, f"{item} missing")
            )
        elif path.is_file() and read_text(path).strip():
            findings.append(Finding("PASS", "source-required-file", item, None, f"{item} exists"))
        else:
            findings.append(
                Finding(
                    "FAIL",
                    "source-required-file",
                    item,
                    None,
                    f"{item} is empty or not a file",
                )
            )
    return findings


def check_source_init_resources(root: Path) -> list[Finding]:
    try:
        from .init import init_files_for_mode, package_resource_root
    except Exception as exc:
        return [
            Finding(
                "FAIL",
                "source-resource-map",
                "sagekit/init.py",
                None,
                f"could not load init resource mapping: {exc}",
            )
        ]

    source_root = package_resource_root()
    if not source_root.exists():
        return [
            Finding(
                "FAIL",
                "source-resource-map",
                relpath(root, source_root),
                None,
                "packaged resource root missing",
            )
        ]

    findings: list[Finding] = [
        Finding("PASS", "source-resource-map", relpath(root, source_root), None, "resource root exists")
    ]
    seen: set[str] = set()
    for item in init_files_for_mode("heavy", source_root):
        if not item.source or item.source in seen:
            continue
        seen.add(item.source)
        path = source_root / item.source
        display = relpath(root, path)
        if path.exists() and path.is_file() and read_text(path).strip():
            findings.append(Finding("PASS", "source-resource", display, None, f"{item.source} resolves"))
        else:
            findings.append(
                Finding(
                    "FAIL",
                    "source-resource",
                    display,
                    None,
                    f"{item.source} missing, empty, or not a file",
                )
            )
    return findings


def check_source_resource_references(root: Path) -> list[Finding]:
    try:
        from .init import package_resource_root
    except Exception as exc:
        return [
            Finding(
                "FAIL",
                "source-resource-reference",
                "sagekit/init.py",
                None,
                f"could not load packaged resource root: {exc}",
            )
        ]

    source_root = package_resource_root()
    docs_root = source_root / "docs"
    if not docs_root.exists():
        return [
            Finding(
                "FAIL",
                "source-resource-reference",
                relpath(root, docs_root),
                None,
                "packaged docs resource root missing",
            )
        ]

    references = collect_packaged_doc_references(docs_root)
    findings: list[Finding] = []
    for target, sources in sorted(references.items()):
        path = source_root / target
        display = relpath(root, path)
        source_summary = summarize_reference_sources(sources)
        if path.exists() and path.is_file() and read_text(path).strip():
            findings.append(
                Finding(
                    "PASS",
                    "source-resource-reference",
                    display,
                    None,
                    f"{target} referenced by {source_summary} resolves",
                )
            )
        else:
            findings.append(
                Finding(
                    "FAIL",
                    "source-resource-reference",
                    display,
                    None,
                    f"{target} referenced by {source_summary} is missing, empty, or not a file",
                    "Mirror the referenced SAGE-Kit doc under sagekit/resources/docs or remove the packaged reference.",
                )
            )
    return findings


def collect_packaged_doc_references(docs_root: Path) -> dict[str, set[str]]:
    references: dict[str, set[str]] = {}
    for path in sorted(docs_root.rglob("*")):
        if not path.is_file():
            continue
        text = read_text(path)
        source = path.relative_to(docs_root.parent).as_posix()
        for match in RESOURCE_REFERENCE_RE.findall(text):
            references.setdefault(match, set()).add(source)
    return references


def summarize_reference_sources(sources: set[str]) -> str:
    ordered = sorted(sources)
    if len(ordered) <= 3:
        return ", ".join(ordered)
    return ", ".join(ordered[:3]) + f", and {len(ordered) - 3} more"


def check_source_resource_mirrors(root: Path) -> list[Finding]:
    try:
        from .init import package_resource_root
    except Exception as exc:
        return [
            Finding(
                "FAIL",
                "source-resource-mirror",
                "sagekit/init.py",
                None,
                f"could not load packaged resource root: {exc}",
            )
        ]

    source_root = package_resource_root()
    docs_root = source_root / "docs"
    if not docs_root.exists():
        return [
            Finding(
                "FAIL",
                "source-resource-mirror",
                relpath(root, docs_root),
                None,
                "packaged docs resource root missing",
            )
        ]

    findings: list[Finding] = []
    for resource_path in sorted(path for path in docs_root.rglob("*") if path.is_file()):
        relative = resource_path.relative_to(source_root).as_posix()
        source_path = root / relative
        display = relpath(root, resource_path)
        if not source_path.exists() or not source_path.is_file():
            findings.append(
                Finding(
                    "FAIL",
                    "source-resource-mirror",
                    display,
                    None,
                    f"{relative} has no source document",
                    "Remove the orphan packaged resource or add the matching source document.",
                )
            )
            continue
        if read_text(resource_path) == read_text(source_path):
            findings.append(
                Finding(
                    "PASS",
                    "source-resource-mirror",
                    display,
                    None,
                    f"{relative} matches source document",
                )
            )
        else:
            findings.append(
                Finding(
                    "FAIL",
                    "source-resource-mirror",
                    display,
                    None,
                    f"{relative} differs from source document",
                    "Copy the updated source document into sagekit/resources before release.",
                )
            )
    return findings


def check_source_pyproject(root: Path) -> list[Finding]:
    path = root / "pyproject.toml"
    if not path.exists():
        return [Finding("FAIL", "source-pyproject", "pyproject.toml", None, "pyproject.toml missing")]
    text = read_text(path)
    checks = [
        (
            'requires-python = ">=3.10"',
            "source-python-policy",
            "Python >=3.10 policy is declared",
            "requires-python must declare Python >=3.10.",
        ),
        (
            "dependencies = []",
            "source-runtime-dependencies",
            "runtime dependency list is empty",
            "Keep the CLI runtime stdlib-only.",
        ),
        (
            'sagekit = "sagekit.cli:main"',
            "source-console-script",
            "console script maps sagekit to sagekit.cli:main",
            'Add [project.scripts] sagekit = "sagekit.cli:main".',
        ),
        (
            'version = {attr = "sagekit.__version__"}',
            "source-version",
            "package version is read from sagekit.__version__",
            "Keep a single version source in sagekit.__version__.",
        ),
        (
            'sagekit = ["resources/**/*"]',
            "source-package-data",
            "packaged resources are included",
            "Package sagekit/resources so init can copy bundled templates after installation.",
        ),
    ]
    findings: list[Finding] = []
    for token, rule, message, suggestion in checks:
        if token in text:
            findings.append(Finding("PASS", rule, "pyproject.toml", None, message))
        else:
            findings.append(Finding("FAIL", rule, "pyproject.toml", None, suggestion, suggestion))
    return findings


def check_source_gitignore(root: Path) -> list[Finding]:
    path = root / ".gitignore"
    if not path.exists():
        return [Finding("FAIL", "source-gitignore-runtime", ".gitignore", None, ".gitignore missing")]
    lines = {
        line.strip()
        for line in read_text(path).splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    missing = [pattern for pattern in GITIGNORE_RUNTIME_PATTERNS if pattern not in lines]
    if missing:
        return [
            Finding(
                "FAIL",
                "source-gitignore-runtime",
                ".gitignore",
                None,
                "missing runtime ignore patterns: " + ", ".join(missing),
                "Ignore local worktrees and generated project runtime state without ignoring templates.",
            )
        ]
    return [
        Finding(
            "PASS",
            "source-gitignore-runtime",
            ".gitignore",
            None,
            "runtime files are ignored while templates remain trackable",
        )
    ]


def is_runtime_state_path(path: str) -> bool:
    normalized = path.replace("\\", "/").strip("/")
    runtime_prefixes = (
        "docs/runs",
        "docs/task-records",
        "local",
        ".sagekit",
        ".runtime",
    )
    if normalized in {"docs/ACTIVE_CONTEXT.md", "docs/DOC_ROUTING.md"}:
        return True
    if any(normalized == prefix or normalized.startswith(f"{prefix}/") for prefix in runtime_prefixes):
        return True
    return re.match(r"^docs/M[0-9]+(/|$)", normalized) is not None


def check_source_tracked_runtime(root: Path) -> list[Finding]:
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=root,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        return [
            Finding(
                "WARN",
                "source-tracked-runtime",
                None,
                None,
                f"could not run git ls-files: {exc}",
                "Run git ls-files manually before committing.",
            )
        ]
    if result.returncode != 0:
        return [
            Finding(
                "FAIL",
                "source-tracked-runtime",
                None,
                None,
                result.stderr.decode("utf-8", errors="replace").strip() or "git ls-files failed",
            )
        ]
    tracked = [
        part.decode("utf-8", errors="replace")
        for part in result.stdout.split(b"\0")
        if part
    ]
    runtime_tracked = [path for path in tracked if is_runtime_state_path(path)]
    if runtime_tracked:
        return [
            Finding(
                "FAIL",
                "source-tracked-runtime",
                None,
                None,
                "runtime files are tracked: " + ", ".join(runtime_tracked),
                "Remove generated runtime state from version control.",
            )
        ]
    return [
        Finding(
            "PASS",
            "source-tracked-runtime",
            None,
            None,
            "no generated runtime project state is tracked",
        )
    ]


def check_source_forbidden_runtime_stack(root: Path) -> list[Finding]:
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z", "--", *FORBIDDEN_RUNTIME_STACK_PATHS],
            cwd=root,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        return [
            Finding(
                "WARN",
                "source-runtime-stack",
                None,
                None,
                f"could not run git ls-files: {exc}",
                "Confirm no Node or TypeScript runtime files were introduced.",
            )
        ]
    if result.returncode != 0:
        return [
            Finding(
                "FAIL",
                "source-runtime-stack",
                None,
                None,
                result.stderr.decode("utf-8", errors="replace").strip() or "git ls-files failed",
            )
        ]
    tracked = [
        part.decode("utf-8", errors="replace")
        for part in result.stdout.split(b"\0")
        if part
    ]
    if tracked:
        return [
            Finding(
                "FAIL",
                "source-runtime-stack",
                None,
                None,
                "Node or TypeScript runtime files are tracked: " + ", ".join(tracked),
                "Keep SAGE-Kit CLI runtime Python stdlib-only.",
            )
        ]
    return [
        Finding(
            "PASS",
            "source-runtime-stack",
            None,
            None,
            "no Node or TypeScript runtime files are tracked",
        )
    ]


def check_required_docs(root: Path, required_docs: list[str] | None = None) -> list[Finding]:
    findings: list[Finding] = []
    for item in REQUIRED_DOCS if required_docs is None else required_docs:
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


def check_recommended_docs(root: Path, recommended_docs: list[str] | None = None) -> list[Finding]:
    findings: list[Finding] = []
    for item in RECOMMENDED_DOCS if recommended_docs is None else recommended_docs:
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
    if any(token in lower for token in ["progress log", "done:", "today i", "session transcript"]):
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
