# State Transition Table Template

Use this table as the source of truth for accepted transitions.

## Transition Groups

### `<group name>`

```text
transition_id: <group.transition.name>
source: <diagram, spec, or requirement>
from_state: <state>
condition: <condition>
input: <input data>
action: <action performed>
writes: <durable writes or no mutation>
event: <event or audit record>
next_state: <state>
visibility: <UI, API, log, export, or none>
tests: <unit, contract, integration, replay, UI, or approval checks>
approval_gate: <none or gate name>
```

## Validation Checklist

- No duplicate transition IDs.
- No transition has implicit writes.
- No user-visible transition lacks visibility evidence.
- No external dependency lacks fake or dry coverage.
- No real mutation bypasses approval gates.
