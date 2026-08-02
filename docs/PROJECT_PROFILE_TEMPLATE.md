# Project Profile Template

Use this file to define the durable project boundary. Replace every
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

These are project-owned prompts, not SAGE-Kit requirements. Record only rules
selected by project authority:

- threat model or safety boundary, if any;
- browser/data/redaction rules, if any;
- production or credential approval gates, if any.

Host safety and non-exposure of credentials remain universal; SAGE-Kit does not
invent product security, privacy, browser, or data requirements.

## Runtime And Data Ownership

Describe which component owns durable state, temporary state, external calls,
user-facing status, and exports. If any category does not apply, record `N/A`
with a reason.

## Project-Specific Vocabulary

| Term | Meaning |
|---|---|
| `<term>` | `<definition>` |
