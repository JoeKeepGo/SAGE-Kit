# Wave Plan Template

Use this template inside a phase document when the phase can benefit from safe
parallel execution.

```markdown
## Wave Plan

### Wave 0 - Controller Setup

- Phase doc:
- Integration owner:
- Shared files:
- Closed approval gates:

### Wave 1 - Parallel Read-Only Lanes

| Lane | Objective | Read Set | Output |
|---|---|---|---|
| `<lane>` | `<objective>` | `<files>` | `<packet>` |

### Wave 2 - Serial Freeze

- Contracts frozen:
- File ownership:
- Test plan:
- Runtime smoke:

### Wave 3 - Parallel Writable Lanes

| Lane | Objective | Allowed Files | Forbidden Files | Tests |
|---|---|---|---|---|
| `<lane>` | `<objective>` | `<files>` | `<files>` | `<commands>` |

### Wave 4 - Parallel Validation Lanes

Validation lanes may run local, fake, dry, fixture, static, or isolated checks.
Real runtime smoke belongs in Wave 5 unless explicitly assigned with exclusive
runtime ownership.

| Lane | Objective | Read Set | Commands |
|---|---|---|---|
| `<lane>` | `<objective>` | `<files>` | `<commands>` |

### Wave 5 - Serial Integration

- Controller diff review:
- Final tests:
- Runtime smoke:
- Ledger update:
- Memory maintenance:
- Handoff:
```
