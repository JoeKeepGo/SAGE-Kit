# Model Assurance Policy

This optional policy records when a project explicitly selects Strict Mode.

SAGE-Kit does not require a specific provider. Projects may replace or tighten
this policy in their own `docs/agent/MODEL_ASSURANCE_POLICY.md`.

## Default Policy

Unknown or unclassified model identity does not automatically enable Strict
Mode. Use the normal Light/Standard/Heavy control matrix unless current project
authority or a human explicitly requires Strict Mode, or identifies a concrete
combination of low assurance and high-risk work that requires it.

Examples of concrete triggers include an observed inability to preserve exact
path/permission bounds while handling production data, destructive actions,
release authority, or safety-critical contracts. Strict Mode narrows execution;
it never grants permission or substitutes for the applicable human gate.

## Controller Responsibility

The project or human authority selects the trigger and boundary. The controller
propagates that explicit decision; an agent does not invent a classification or
enable Strict solely because identity metadata is missing.
