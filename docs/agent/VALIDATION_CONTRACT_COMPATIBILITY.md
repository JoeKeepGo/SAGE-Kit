# Validation Contract Compatibility

Task Dispatch contract selection happens before record validation:

```text
closed legacy history -> frozen v1 contract
active/new work        -> current v2 contract
ambiguous or mixed     -> fail closed
```

Closed accepted history is not batch-rewritten and is not represented as if it
had adopted a newer contract. Unversioned records qualify for implicit v1 only
when task and evidence are a matching closed/verified terminal pair.

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
version and policy identity for audit.

Closed history is validated pair-by-pair and then excluded from active duplicate,
lease, lock, and dispatch-board reconciliation. Active records remain strict.

Finding presentation is bounded, but validation is complete. Output distinguishes
displayed findings from exact total counts, preserves path/rule/message for each
sample, and bases process status on all findings.
