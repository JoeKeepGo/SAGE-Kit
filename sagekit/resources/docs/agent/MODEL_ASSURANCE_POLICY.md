# Model Assurance Policy

This policy decides when an AI agent must use Strict Mode.

SAGE-Kit does not require a specific provider. Projects may replace or tighten
this policy in their own `docs/agent/MODEL_ASSURANCE_POLICY.md`.

## Default Policy

Use normal agent mode only when the controller or human explicitly classifies
the executing model as high-assurance for the task.

The starter high-assurance families are:

- OpenAI ChatGPT models selected by the project owner or controller;
- Anthropic Claude models selected by the project owner or controller.

Projects may add other model families or specific models when they have enough
evidence to trust them for the task class.

Strict Mode is required by default when:

- the model family is unknown;
- the model is not in a high-assurance family;
- the model is small, routed, fine-tuned, tool-wrapped, or otherwise not
  explicitly approved for autonomous planning.

High-risk tasks that touch approval gates, shared contracts, production data,
release, or destructive actions require explicit controller or human
authorization. Projects may require Strict Mode for those tasks even when the
model family is high-assurance.

## Controller Responsibility

The controller or human classifies the model. A delegated agent must not decide
for itself that it is exempt from Strict Mode.
