from __future__ import annotations

import unittest
from pathlib import Path


class PlanningDepthContractTests(unittest.TestCase):
    def test_canonical_contract_has_no_general_planning_count_or_file_ceiling(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        paths = (
            repository / "docs/agent/MILESTONE_PLANNING.md",
            repository / "docs/agent/WAVE_EXECUTION.md",
            repository / "skills/sage-kit/SKILL.md",
        )
        text = "\n".join(path.read_text(encoding="utf-8") for path in paths)
        forbidden = ("at most 8 project", "8-file ceiling", "maximum 8 milestones")
        for phrase in forbidden:
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, text.casefold())
        for required in (
            "dependency dag",
            "acceptance",
            "wave readiness",
            "reviewable phases",
        ):
            with self.subTest(required=required):
                self.assertIn(required, text.casefold())


if __name__ == "__main__":
    unittest.main()
