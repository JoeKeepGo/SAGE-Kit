# Execution Protocol Template

Use this document to define the contract between a control plane and an
execution boundary.

## Protocol Summary

Describe transport, versioning, authentication, correlation, and timeout rules.

## Capability Contract

| Capability | Meaning | Required For | Failure Behavior |
|---|---|---|---|
| `<capability>` | `<meaning>` | `<action>` | `<failure>` |

## Request Shape

```json
{
  "id": "<correlation id>",
  "action": "<action>",
  "payload": {}
}
```

## Success Shape

```json
{
  "id": "<correlation id>",
  "status": "ok",
  "result": {}
}
```

## Error Shape

```json
{
  "id": "<correlation id>",
  "status": "error",
  "error": {
    "code": "<code>",
    "message": "<safe message>"
  }
}
```

## Redaction Rules

- Do not return raw credentials, tokens, private keys, cookies, or sensitive
  local data.
- Error messages must be useful without exposing secrets.

## Tests

| Case | Expected Evidence |
|---|---|
| success | `<test>` |
| timeout | `<test>` |
| invalid request | `<test>` |
| capability mismatch | `<test>` |
| redaction | `<test>` |

