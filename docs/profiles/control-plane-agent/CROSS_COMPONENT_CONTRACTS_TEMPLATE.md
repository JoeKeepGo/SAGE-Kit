# Cross-Component Contracts Template

Use this document to track contracts that cross component, repository, process,
or runtime boundaries.

## Contracts

| Contract | Owner | Consumers | Version | Compatibility Rule | Tests |
|---|---|---|---|---|---|
| `<contract>` | `<owner>` | `<consumers>` | `<version>` | `<rule>` | `<tests>` |

## Change Rules

- Contract owner changes the contract first.
- Consumers update only after the owner-side contract is documented and tested.
- Breaking changes require a migration or explicit coordinated release.
- Unknown fields must not be guessed into success.

## Review Checklist

- Owner and consumers are named.
- Request and response shapes are documented.
- Error behavior is explicit.
- Compatibility behavior is explicit.
- Tests exist on owner and consumer sides where applicable.

