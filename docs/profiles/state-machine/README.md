# State-Machine Profile

Use this profile when the project is primarily governed by explicit state
transitions, durable events, replayable decisions, or workflow orchestration.

## Adds To Core

- State transition table.
- Transition index.
- Test matrix.
- Replay and integration expectations.
- Event-before-snapshot rules.
- UI visibility for user-facing transitions.

## Required Documents

| File | Purpose |
|---|---|
| `docs/STATE_TRANSITION_TABLE.md` | Source of truth for accepted transitions. |
| `docs/STATE_TRANSITION_INDEX.md` | Lookup index for transition IDs. |
| `docs/TEST_MATRIX.md` | Test responsibility by transition. |

Template sources:

- `docs/profiles/state-machine/STATE_TRANSITION_TABLE_TEMPLATE.md`
- `docs/profiles/state-machine/STATE_TRANSITION_INDEX_TEMPLATE.md`
- `docs/profiles/state-machine/TEST_MATRIX_TEMPLATE.md`

## Transition Standard

Every transition should define:

```text
transition_id:
source:
from_state:
condition:
input:
action:
writes:
event:
next_state:
visibility:
tests:
approval_gate:
```

## Acceptance Rules

- Every accepted transition has a stable ID.
- Every state mutation writes an event or explicit audit record.
- Replay can explain how durable state was reached.
- User-visible state changes have visibility assertions.
- External dependencies use fake or dry tests by default.
- Real external effects require approval gates.
