# Execution

Start from current authority, active SPEC, allowed surfaces, acceptance, and
project-native commands. Use the smallest bounded implementation loop that can
finish the task safely.

- Run focused checks for changed behavior.
- Parallelize only disjoint work; shared files and integration stay with one
  controller.
- Keep subagent boundaries explicit and inherited.
- Use native model planning, TDD, debugging, and review; do not load unrelated
  workflow bundles.
- Record evidence by reference instead of copying logs through every document.
- Do not run broad checks repeatedly. The final candidate receives one project
  CI run.

Continue correctives while findings converge and scope stays fixed. Two
consecutive approved rounds without progress on the same root cause stop.
Authority, security, destructive, credential, acceptance, merge, and release
decisions stop unless explicitly granted.
