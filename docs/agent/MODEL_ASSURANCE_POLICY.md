# Model Assurance Policy

This policy decides when an AI agent must use Strict Mode.

SAGE-Kit does not require a specific provider. Projects may replace or tighten
this policy in their own `docs/agent/MODEL_ASSURANCE_POLICY.md`.

## Default Policy

Use normal agent mode only when a versioned project or runtime classification
explicitly classifies the executing model as high-assurance for the task class.
The controller resolves that classification once at session entry and passes
its identifier and version to descendants.

Projects may add specific models or model classes when they have enough
evidence to trust them for the task class.

Strict Mode is required by default when:

- the model identity is unknown;
- no valid versioned classification approves the model for the task class;
- the model is small, routed, fine-tuned, tool-wrapped, or otherwise not
  explicitly approved for autonomous planning.

A descendant inherits the controller's resolved classification only while the
model identity, task class, risk boundary, and classification version remain
unchanged. Re-resolve instead of inheriting when any of them changes. Do not
repeat classification work for each descendant when those inputs are stable.

High-risk tasks that touch approval gates, shared contracts, production data,
release, or destructive actions require explicit controller or human
authorization. Projects may require Strict Mode for those tasks even when the
model is high-assurance.

## Controller Responsibility

The project or runtime policy classifies the model; the controller resolves and
propagates that result. A delegated agent must not decide for itself that it is
exempt from Strict Mode or alter the inherited classification.
