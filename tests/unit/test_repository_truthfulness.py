from __future__ import annotations

import unittest
from pathlib import Path


class RepositoryTruthfulnessTests(unittest.TestCase):
    def test_nonexistent_sage_kit_domain_is_not_published(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        forbidden_domain = "sage-kit" + ".dev"
        text_suffixes = {
            ".json",
            ".md",
            ".py",
            ".toml",
            ".yaml",
            ".yml",
        }
        occurrences: list[str] = []

        excluded_parts = {
            ".git",
            ".sagekit",
            ".worktrees",
            "__pycache__",
            "build",
            "dist",
        }
        for path in repository.rglob("*"):
            relative = path.relative_to(repository)
            if any(part in excluded_parts for part in relative.parts):
                continue
            if path.is_file() and path.suffix.lower() in text_suffixes:
                if forbidden_domain in path.read_text(encoding="utf-8"):
                    occurrences.append(relative.as_posix())

        self.assertEqual([], occurrences)


if __name__ == "__main__":
    unittest.main()
