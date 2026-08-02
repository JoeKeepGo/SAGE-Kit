# Execution Economy

The goal is trustworthy convergence with the least repeated work.

<a id="sage-loop-003"></a>
<a id="sage-loop-006"></a>
## Verification Admission

- During implementation, run only project-native focused checks for changed
  behavior.
- At a lane boundary, verify only affected contracts and integrations.
- Run broad project CI once when the final candidate is ready.
- Reuse attributable evidence while its inputs, scope, and relevant code are
  unchanged.
- When a corrective changes one boundary, invalidate and re-run only that
  boundary before the final CI decision.

No framework-side candidate freeze, repository hashing, package build, process
lease, verification counter, or checkpoint is required. Git commit identity,
the project diff, project test output, and CI receipts are sufficient factual
bindings when the project considers them sufficient.

<a id="sage-loop-010"></a>
## Review Economy

Reviewers report the complete bounded finding set in one pass. Ordinary
documentation consistency issues may be fixed directly when ownership is clear.
Only authority conflicts, false-green evidence, approval gates, security
boundaries, or failed required checks block acceptance.

A corrective receives one targeted re-review of the affected boundary. Full
review is repeated only when semantics, permissions, source authority, or a
cross-boundary contract changed.

<a id="sage-loop-008"></a>
## Convergence

Continue automatically while findings decrease or severity improves, the root
cause stays within the approved family, and scope does not expand. A next-layer
finding is not scope growth when it is direct evidence from the same fix.

Stop after two consecutive approved rounds with no progress on the same root
cause. Stop immediately for authority change, security decision, destructive
action, credential use, acceptance, or unapproved scope expansion.

<a id="sage-loop-012"></a>
<a id="sage-loop-013"></a>
## Evidence Reuse

Evidence states command or review, scope, relevant revision/diff, result, and
limitations. It may be referenced rather than copied into every phase document.
Historical evidence is not current evidence unless its inputs are unchanged and
the current authority permits reuse.

## Host Resource Courtesy

Avoid duplicate broad checks, concurrent package builds, unbounded polling, and
parallel commands that compete for the same repository or toolchain. Prefer
project-native timeouts and CI isolation. Environment cleanup failures unrelated
to product correctness are reported accurately rather than converted into a
product blocker.
