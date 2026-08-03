# Execution

Start from current authority, active SPEC, allowed surfaces, acceptance, and
project-native commands. Use the smallest bounded implementation loop that can
finish the task safely.

- Run focused checks for changed behavior.
- Parallelize disjoint work. A shared toolchain is serial only while mutable
  state is shared; integration, push, and merge stay with one controller.
- Keep subagent boundaries explicit and inherited.
- Use native model planning, TDD, debugging, and review; do not load unrelated
  workflow bundles.
- Record evidence by reference instead of copying logs through every document.
- Do not run broad checks repeatedly. Each unchanged final candidate receives
  project CI only when required; a corrective successor may run it again.

Continue correctives without new approval while findings decrease and scope
stays fixed. Two consecutive no-progress rounds on the same root cause return
`BLOCKED`.
Authority, security, destructive, credential, acceptance, merge, and release
decisions stop unless explicitly granted.
