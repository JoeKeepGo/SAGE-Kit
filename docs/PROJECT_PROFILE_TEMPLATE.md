# Project Profile Template

Use this file to define the durable product and project boundary. Replace every
placeholder before implementation work depends on this profile.

## Product Summary

Describe what the product does, who it serves, and the primary value it
provides.

## Target Users

| User | Need |
|---|---|
| `<user group>` | `<need>` |

## Problems

| ID | Problem |
|---|---|
| `P-001` | `<problem>` |

## Goals

| ID | Goal | Success Signal |
|---|---|---|
| `G-001` | `<goal>` | `<observable signal>` |

## Non-Goals

| ID | Non-Goal | Reason |
|---|---|---|
| `NG-001` | `<excluded scope>` | `<reason>` |

## Constraints

| ID | Constraint | Impact |
|---|---|---|
| `C-001` | `<business, platform, compliance, support, timeline, operational, or technical constraint>` | `<impact>` |

## Product Requirements

| ID | Requirement | Acceptance |
|---|---|---|
| `REQ-001` | `<requirement>` | `<acceptance evidence>` |

## Security And Privacy Boundaries

- User-facing responses must not expose server-only secrets. For projects with
  a browser UI, browser-facing responses must be redacted.
- Logs and reports must redact credentials, tokens, private keys, and sensitive
  local data.
- Production data access requires an approval gate.

## Runtime And Data Ownership

Describe which component owns durable state, temporary state, external calls,
user-facing status, and exports. If any category does not apply, record `N/A`
with a reason.

## Project-Specific Vocabulary

| Term | Meaning |
|---|---|
| `<term>` | `<definition>` |

## Banned Or Deprecated Terms

List words that must not appear in product surfaces or new architecture docs.
