# Releases

SAGE-Kit releases are static governance artifacts.

Every release includes GitHub's source archive. A release may additionally
attach one static Skill bundle containing `skills/sage-kit/` and the referenced
`docs/` and `contracts/` snapshot, plus a checksum manifest. The bundle contains
no executable framework runtime and must not modify an Installed Skill
automatically.

Release verification checks repository integrity, required Skill metadata,
JSON readability when native tooling is available, host hook tests, and the
absence of forbidden executable-package surfaces. Product-specific tests remain
the responsibility of consumer projects.

Published tags are immutable. A release correction uses a new tag.
