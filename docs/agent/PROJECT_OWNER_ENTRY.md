# Project Owner Entry

Project Owner Entry is the lightweight SPEC-Kit path for a person who knows the
goal, business need, or user problem but may not know how to describe software
architecture or implementation work yet.

It turns an idea into planning inputs. It must not produce an executable
roadmap directly.

## Use When

- the project starts from a non-technical idea;
- the user can describe desired outcomes but not code structure;
- the project needs a safe first SPEC-Kit bootstrap without overwhelming the
  project owner;
- a current roadmap looks too small, too broad, or too module-shaped.

Do not use this path for a narrow implementation task that already has an
accepted phase document.

## Intake Questions

Start with five questions:

1. What do you want to build or change?
2. Who will use it?
3. What problem does it solve right now?
4. What can a user do when it succeeds?
5. What are you most worried about?

Ask follow-up questions only when one of these answers is too vague to produce
acceptance criteria, non-goals, risk notes, or a first capability map.

## Output Sequence

Project Owner Entry produces drafts in this order:

1. project owner intake;
2. simplified project profile draft;
3. capability map;
4. draft milestone candidates;
5. milestone granularity audit;
6. first executable milestone entry gate only after the audit passes.

The intake, profile draft, capability map, draft candidates, and audit are
planning material. They are not authorization to start implementation.

## Capability Map Before Roadmap

Before creating an executable milestone roadmap, map the project into
capabilities:

- user-facing capabilities;
- operator or administrator capabilities;
- data and state capabilities;
- integration capabilities;
- runtime, deployment, or recovery capabilities;
- observability, security, and support capabilities.

Milestones are derived from this map. A milestone that spans several capability
areas is probably an epic and must be split.

## Project Owner Responsibilities

The project owner decides:

- whether the goal and user outcome are correct;
- which risks are acceptable;
- which non-goals remain out of scope;
- whether user-visible evidence proves the desired outcome.

The project owner should not be asked to accept implementation claims without
tests, runtime smoke, review evidence, or visible product evidence.

## Granularity Guardrail

Project Owner Entry must not produce an executable roadmap directly. It produces
candidate capabilities and draft milestones. Milestone Granularity Gate must
split any milestone that cannot be independently reviewed, verified, and
bounded.

Red flags:

- total milestone count is much smaller than the capability map;
- a milestone covers multiple user workflows, runtimes, or ownership domains;
- a milestone mixes design, implementation, integration, review, and release;
- a milestone cannot name one observable acceptance result;
- a milestone needs broad files or unknown file ownership;
- a milestone cannot name tests or runtime evidence.

## Task Dispatch Decision

Do not enable Task Dispatch Profile by default for Project Owner Entry.

Recommend Task Dispatch only when the candidate milestone has many worker tasks,
resource contention, repeated attempts, cross-surface integration, or a high
risk of unverifiable completion claims.
