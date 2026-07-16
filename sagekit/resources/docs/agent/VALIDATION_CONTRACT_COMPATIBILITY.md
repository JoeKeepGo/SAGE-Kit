# Validation Contract Compatibility

Task Dispatch contract selection happens before record validation:

```text
explicit matching v2 metadata                         -> current v2 contract
terminal task/evidence + trusted accepted closeout
  + milestone outside the active set                  -> frozen v1 contract
active/new work, ambiguous or mixed authority         -> fail closed
```

Repository scope resolution is separate from record selection. The resolver
uses structured `Current milestone` or `Active milestone` fields from
`docs/ACTIVE_CONTEXT.md` and structured `Status` or `Outcome` values from a
milestone closeout. A closeout filename, prose containing `accepted`, or
terminal task state alone is not authority. `VERIFIED` alone never proves
legacy scope.

Authority precedence is explicit validation metadata, explicit active milestone
authority, trusted accepted closeout authority, then inferred terminal state.
Inferred state can satisfy the terminal-record requirement but cannot authorize
v1 by itself. Active plus accepted authority, unknown closeout formats, and
other conflicting, incomplete, ambiguous or mixed authority fail closed.

Closed legacy history includes both `CLOSED + VERIFIED` and
`VERIFIED + VERIFIED` terminal pairs when the container is trusted immutable
accepted history. Explicit v1 metadata has the same terminal task/evidence and
immutable-scope requirements. Closed accepted history is not batch-rewritten or
represented as if it had adopted a newer contract.

Active and new work must explicitly declare matching v2 metadata:

```yaml
validation_contract:
  version: 2
  policy_id: sagekit-task-dispatch-v2
  policy_sha256: a 64-character lowercase digest of the packaged v2 policy
  scope: active
```

Task and evidence must select the same version. Policy ID, digest, and scope must
match the packaged policy. Tampering fails. After v2 is selected, a v2 failure
must not fall back to v1.

Frozen policies and schemas are packaged under `sagekit/resources/contracts/`.
The v1 policy records the exact historical commit and source paths from which
its immutable schemas were frozen, and binds their canonical JSON SHA-256
digests. Hermetic tests compare packaged resources and policy against
independent fixed digest constants; they never execute `git show` or require a
full repository history at test runtime. The selector emits the selected
version, policy identity, and scope authority for audit. Frozen v1 schemas and
policy digests are not widened for records that still fail their selected
contract.

Closed history is validated pair-by-pair and then excluded from active duplicate,
lease, lock, and dispatch-board reconciliation. Active records remain strict.
Ambiguous, mixed, and current records remain in conservative reconciliation.

Current milestone phases receive the latest phase checks. Immutable accepted
historical phases retain basic integrity checks but do not retroactively receive
new format requirements; one aggregated compatibility finding names the
milestone and closeout authority. Ambiguous scope produces one blocking
milestone finding instead of a cascade of derived field failures. Agents must
not rewrite accepted historical documents merely to satisfy a newer format.

The Skill provides guidance only. The CLI/validator owns contract and milestone
scope selection and must not accept a Skill claim as validation authority.

Finding presentation is bounded, but validation is complete. Output distinguishes
displayed findings from exact total counts, preserves path/rule/message for each
sample, and bases process status on all findings.
