# Validation Contract Compatibility

Task Dispatch contract version and execution document model are independent:

| Dimension | Values |
|---|---|
| Task Dispatch validation contract | v0, v1, v2 |
| Execution document model | `legacy-markdown`, `thin-v1` |

`thin-v1` is not Task Dispatch v3. Accepted historical Task Dispatch records
and legacy phase documents retain their frozen routing. Active legacy
milestones use the legacy phase checker. Active thin milestones require a valid
`SAGE_PROJECT.json`, `MILESTONE_MANIFEST.json`, and phase manifests. Mixed,
missing, or conflicting document-model authority must not fall back, and an
explicit v2 record failure still remains a v2 failure.

Task Dispatch contract selection happens before record validation:

```text
explicit matching v2 metadata                         -> current v2 contract
explicit matching v1 metadata + immutable scope       -> frozen v1 contract
explicit matching v0 metadata + immutable scope       -> frozen v0 contract
terminal task/evidence + resolved accepted legacy
  container scope                                     -> manifest-selected v0 or v1
active/new work, ambiguous or mixed authority         -> fail closed
```

Repository scope resolution is separate from record selection. The resolver
uses structured `Current milestone` or `Active milestone` fields from
the configured active-context path (legacy default:
`docs/ACTIVE_CONTEXT.md`) and structured `Status` or `Outcome` values from a
milestone closeout. A closeout is audit evidence only: a closeout filename,
prose containing `accepted`, or terminal task state alone is not authority.
`VERIFIED` alone never proves legacy scope.

An explicit Validation Scope Manifest is required to authorize immutable
history. Existing projects that cannot express historical scope with newer
active-set fields use a Validation Scope Manifest. `sagekit.check_project` reads
`docs/SAGE_VALIDATION_SCOPE.json`, or an invocation may supply an external file
via `scope_manifest_path`. The JSON format is defined by
`docs/templates/SAGE_VALIDATION_SCOPE_TEMPLATE.json`. It explicitly lists
active containers and accepted legacy containers by stable ID and normalized
target-relative path. Every legacy entry selects exactly one frozen
`contract_version` (0 or 1). Approval provenance, baseline HEAD, and a canonical
manifest digest make the authority auditable. Ranges, globs, path traversal,
aliases, duplicate paths, and implicit membership are rejected.

The manifest is migration acceptance authority, not normal runtime state. New
projects and ordinary v2 projects normally do not need one, and host-owned
bootstrap creation of minimal versioned project config does not create it. A harness manifest supplied by the
harness entrypoint replaces, rather than merges with, a project-local manifest.
For current scope, container authority precedence is harness manifest,
project-local manifest, structured active context, then conservative
current/ambiguous fallback. Closeout alone is audit evidence only; it can expose
real conflicts but cannot authorize immutable history.

An accepted manifest entry may authorize history with an accepted, ambiguous,
or missing old closeout. An explicit non-accepted closeout additionally
requires an exact `supersedes` path identifying that closeout inside the
declared container; unrelated, missing, or target-external paths fail closed.
Manifest acceptance that overlaps real structured active authority also fails
closed. Unlisted containers never become legacy. The manifest cannot turn a
nonterminal record into v0/v1 or downgrade an explicit v2 record.

Record authority precedence is explicit matching v2 metadata, explicit
matching v1/v0 metadata, then implicit selection from resolved container scope.
Container resolution considers explicit active milestone authority and manifest
migration acceptance. A trusted accepted closeout and terminal state are audit
evidence; inferred state can satisfy the terminal-record requirement but cannot
authorize v0/v1 or immutable history by itself. Active plus accepted authority,
unknown closeout formats, and other conflicting, incomplete, ambiguous or mixed
authority fail closed.

Closed legacy history includes both `CLOSED + VERIFIED` and
`VERIFIED + VERIFIED` terminal pairs when the container is trusted immutable
accepted history by an explicit Validation Scope Manifest. The manifest selects
v0 for the early public record shape and v1 for the later hardened legacy
shape; the validator never tries one version and falls back to another.
Explicit v0/v1 metadata has the same terminal task/evidence and immutable-scope
requirements. Closed accepted history is not batch-rewritten or represented as
if it had adopted a newer contract.

Focused compatibility regressions must prove that closeout-only history remains
blocked and that only an explicit Validation Scope Manifest can authorize an
immutable legacy container.

Active and new work must explicitly declare matching v2 metadata:

```yaml
validation_contract:
  version: 2
  policy_id: sagekit-task-dispatch-v2
  policy_sha256: a 64-character lowercase digest of the packaged v2 policy
  scope: active
```

Task and evidence must select the same version. Policy ID, digest, and scope must
match the packaged policy. Tampering fails. After any version is selected, a
failure must not fall back or trigger validation under another contract.

Frozen policies, schemas, rule policies, and validator semantics are packaged
under `sagekit/resources/contracts/`. Versioned validator sidecars record
historical source commits and paths and bind canonical policy, schema, rules,
and frozen-engine SHA-256 digests. A frozen schema artifact does not imply that
the historical runtime executed it against records: v0 checked schema presence
and valid JSON while its Python rules validated records; the hardened v1
baseline executed both its recursive schema checks and Python rules. The
released v1 policy bytes and policy digest remain unchanged, so existing
explicit v1 metadata stays valid. v0 is a semantic snapshot of the first public
Task Dispatch contract; only non-validating schema metadata was normalized.
Hermetic tests do not execute `git show` or require full repository history.
The selector emits the selected version, policy identity/digest, container
path, and authority. Frozen contracts are not widened for records that fail
their selected version.

Adopted-project discovery is bounded to paired
`docs/**/dispatch/**/{task,evidence}.yaml` records. The container is the nearest
ancestor immediately before the single `dispatch` segment. Templates, profiles,
`_TEMPLATE` paths, nested `dispatch` paths, and target-external symlinks are not
accepted as records. Generic non-milestone containers participate in Task
Dispatch validation but are not treated as milestone phase directories.

Closed history is validated pair-by-pair and then excluded from active duplicate,
lease, lock, and dispatch-board reconciliation. Active records remain strict.
Ambiguous, mixed, and current records remain in conservative reconciliation.

Current milestone phases receive the latest phase checks. Immutable accepted
historical phases retain basic integrity checks but do not retroactively receive
new format requirements; one aggregated compatibility finding names the
milestone and closeout authority. Ambiguous scope produces one blocking
milestone finding instead of a cascade of derived field failures. Agents must
not rewrite accepted historical documents merely to satisfy a newer format.

`sagekit.validate_task_and_evidence_records(...)` validates one task/evidence
pair. `sagekit.check_project(...)` validates project and gate state, including
active/history scope and an optional external scope manifest. The Skill provides guidance only. The harness validator and host controller own
contract and milestone scope selection and must not accept a Skill claim as
validation authority.
Agents must not use a manifest to conceal current failures or rewrite accepted
history to resemble newer formats.

Finding presentation is bounded, but validation is complete. Output distinguishes
displayed findings from exact total counts, preserves path/rule/message for each
sample, and bases process status on all findings.
