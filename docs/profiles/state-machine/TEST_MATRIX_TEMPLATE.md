# Test Matrix Template

Use this matrix to assign test responsibility before implementation.

## Test Taxonomy

| Code | Responsibility |
|---|---|
| U | Unit or model tests. |
| C | Contract tests. |
| IR | Integration or replay tests. |
| UI | User-visible assertions. |
| G | Approval-gate or review checks. |
| FD | Fake or dry external-dependency tests. |

## Matrix

| transition_id | owner | write/event expectation | primary tests | replay expectation | visibility assertion | approval or fake-dry requirement |
|---|---|---|---|---|---|---|
| `<transition_id>` | `<owner>` | `<expectation>` | `<tests>` | `<replay>` | `<visibility>` | `<gate or fake-dry>` |

## Coverage Checklist

- Every transition ID appears once.
- Every row has at least one primary test responsibility.
- Every user-visible transition has a visibility assertion.
- Every real external dependency has fake or dry coverage.
- Approval gates remain closed unless explicitly opened.
