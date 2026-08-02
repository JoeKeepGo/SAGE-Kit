# Host Resource Guidance

SAGE-Kit does not manage host processes or resources. Controllers use the host
and project's native capabilities responsibly:

- do not run duplicate broad checks;
- serialize commands that compete for the same build or repository state;
- use project-native timeouts and cancellation;
- terminate owned descendants when a command is cancelled;
- keep temporary outputs outside tracked product paths;
- report containment, cleanup, timeout, and resource limitations honestly.

Procedural instructions are not operating-system enforcement. Security-critical
containment must be provided by the host or project infrastructure.
