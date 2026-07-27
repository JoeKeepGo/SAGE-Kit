# Stage 7 Architecture Checkpoint

## 1. Executive Verdict

**Verdict: `STAGE_7_READY_FOR_ACCEPTANCE`.**

This is a recorder-only architecture checkpoint for the frozen Stage 7 runtime
adapter integration at `d2c89c59b32ec00c5140d6de34f9deed3666778d` on
`codex/rebuild-stage7-runtime-adapters`. It records the canonical adapter and
host contracts, the Codex, Claude Code, Kimi, and OpenCode profiles, thin
`SKILL` routing, four closed review findings, and the focused static
verification surface already present in that lineage.

It is not a new review, product acceptance, merge approval, release approval,
or publication approval. Stage 8 has not started.

## 2. Frozen Baseline And Recorder Scope

| Item | Frozen value |
|---|---|
| Worktree | `D:\Projects\SPEC Framework\.worktrees\rebuild-stage7-checkpoint` |
| Checkpoint branch | `codex/rebuild-stage7-architecture-checkpoint` |
| Final product branch | `codex/rebuild-stage7-runtime-adapters` |
| Final product HEAD | `d2c89c59b32ec00c5140d6de34f9deed3666778d` |
| Required checkpoint parent | `d2c89c59b32ec00c5140d6de34f9deed3666778d` |
| Parent subject | `test: align Kimi adapter assertions` |
| Checkpoint change | This report only |
| Write allowlist | `docs/design/rebuild/STAGE_7_ARCHITECTURE_CHECKPOINT.md` |
| Recorder authority | Record frozen evidence; do not perform a new review |

The checkpoint adds no consumer behavior and does not modify an Installed
Skill, CLI, runtime, scheduler, host implementation, or product test. It does
not add a CLI. The only permitted write is this record.

## 3. Canonical Adapter And Host Boundary

`docs/agent/CAPABILITY_ADAPTERS.md` is the canonical adapter boundary. It owns
the ordered `Detect`, `Authorize`, `Bound`, `Invoke`, `Capture`, `Map`, and
`Fallback` lifecycle; adapter output is evidence only and cannot create
authority, widen scope, pass a gate, or establish acceptance. Runtime-specific
discovery and invocation mechanics remain in the selected profile.

`docs/agent/HOST_RESOURCE_GOVERNANCE.md` is the canonical host boundary. Root
alone supervises a managed host operation and binds its authority, workspace,
file surface, resource class, timeout, evidence, and stop condition. Profiles
report actual containment as `HARD`, `MANAGED`, or `SOFT`; neither a profile nor
a successful command can overstate the host mechanism. The broader bypass
guarantee remains `SOFT` whenever direct agents, shells, plugins, or children
can escape the managed path.

The Stage 7 product update consolidated both canonical documents and their
byte-identical packaged mirrors. The profiles point to those owners rather than
redefining authority, completion, containment, or resource semantics.

## 4. Runtime Profiles And SKILL Routing

| Profile | Recorded Stage 7 boundary |
|---|---|
| Codex | A minimal additive profile uses model-native execution after Root resolves the packet. The Superpowers prohibition is scoped to a Codex runtime running a GPT-5.6-family model; native `spawn_agent` is the subagent path, and policy-disabled Superpowers is not a capability gap or fallback trigger. |
| Claude Code | The profile names canonical owners, preserves controller ownership of verification, and distinguishes its read-only reviewer tool surface from the Coder's `SOFT` packet file and command instructions. A matching structured-edit serial-file hook may be `MANAGED`; Bash inspection and other packet boundaries remain `SOFT`. |
| Kimi | Runtime features are discovered at use time. `disable-model-invocation: true` is `HARD` only for a verified Kimi Code CLI deployment that honors it; Kimi Work and unverified deployments make no such claim. The profile does not establish a delegation default or depth limit. |
| OpenCode | Discovery, permission configuration, and subagent behavior are version-dependent. Effective normal-path permissions may be `MANAGED` for that path; absent, unverifiable, or bypassable configuration is `SOFT`, never `HARD`. |

The repository `skills/sage-kit/SKILL.md` is a thin activation and routing layer,
not a second governance contract. It routes host-specific invocation only when
that host is active: Codex to `references/codex.md`, Claude Code to
`references/claude.md`, Kimi Work or supported Kimi Code to
`references/kimi-runtime.md`, and OpenCode to `references/opencode.md`. It
continues to route adapter lifecycle and runtime-policy semantics to the
canonical documents, and keeps Installed Skill status separate from project
authority.

## 5. Historical Review Findings And Closed Evidence

This section records the four historical Stage 7 corrective findings. It does
not perform or add a review.

| Historical finding | Closure evidence | Status |
|---|---|---|
| The thin repository `SKILL` did not route a host session to the corresponding runtime profile, leaving host-specific invocation guidance embedded or undiscoverable. | `36883d3` reduced `SKILL.md` to activation and narrow routing, retained canonical owner pointers, and added explicit Codex, Claude Code, Kimi, and OpenCode profile routes. Static assertions require complete root routing and keep host policy out of the thin entrypoint. | `CLOSED` |
| The Codex profile overstated the model-policy scope and offered external `codex exec` as a fallback, which could make a policy-disabled adapter look like a capability gap. | `f5fc963` scopes the prohibition to any GPT-5.6-family Codex runtime, states model-native verification, removes the external CLI fallback, and requires capability selection through the canonical lifecycle. | `CLOSED` |
| The Kimi profile claimed `HARD` invocation control and a delegation depth default without a verified installed runtime and deployment. | `f5fc963` limits the `HARD` claim to a verified Kimi Code CLI deployment that honors the frontmatter, makes unverified Kimi behavior non-enforcing, and removes the invented delegation default/depth limit. `d2c89c5` aligns the corresponding assertions. | `CLOSED` |
| The Claude Coder description and hook discussion overstated packet file and command enforcement. | `8991e6e` records Coder packet limits as `SOFT` instructions, limits `MANAGED` status to a matching structured-edit serial-file control, and keeps Bash inspection `SOFT`; the read-only reviewer surface and controller-owned verification remain distinct. | `CLOSED` |

## 6. Focused Verification Evidence

The frozen Stage 7 lineage contains focused static repository-contract coverage
in `tests/test_sagekit_check.py` and `tests/test_thin_documentation.py`. The
coverage checks canonical source and packaged-mirror alignment, required
adapter/host pointers, complete four-profile routing, narrow profile assertions,
and the corrected Codex, Claude, Kimi, and OpenCode containment statements.

The negative static assertions are repository development-contract tests only.
They protect the repository's documentation and routing invariants, including
the absence of unsupported enforcement, CLI, or routing claims. They are not
loaded or executed during ordinary Skill or consumer use, do not create a
consumer runtime dependency, and do not become a daily Skill execution path.

This recorder did not run product tests, those static tests, a full suite,
package build, install check, runtime smoke, scheduler, executor, or CLI
command. It ran only the document and one-file change-boundary checks described
below and does not claim a new product-test pass.

## 7. Checkpoint Verification And Remaining Boundary

This recorder verifies Markdown structure, the exact one-file allowlist, and
`git diff --check`. It does not run a product test, review, Stage 8 work, full
suite, package build, install check, runtime smoke, scheduler, executor, or
CLI command.

`STAGE_7_READY_FOR_ACCEPTANCE` means the frozen architecture, canonical
ownership boundary, runtime-profile routing, closed historical findings, and
focused static verification surface are ready to be presented to the
responsible acceptance authority. It does not record acceptance, authorize
merge, authorize release or publication, modify consumer behavior, grant
runtime authority, or claim full-suite, build, package, downstream, runtime,
or cross-platform coverage.

Stage 8 has not started. The next action is an external Stage 7 acceptance
decision.
