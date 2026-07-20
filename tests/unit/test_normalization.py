from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sagekit.normalization import (
    NormalizationKind,
    apply_auto_normalization,
    classify_bytes,
    non_whitespace_digest,
)


class MechanicalNormalizationTests(unittest.TestCase):
    def test_safe_eof_and_trailing_whitespace_findings_are_auto_corrective(self) -> None:
        cases = (
            (b"value\n", b"value\n\n", NormalizationKind.EXTRA_BLANK_LINE_AT_EOF),
            (b"value\n", b"value", NormalizationKind.MISSING_FINAL_NEWLINE),
            (b"value\n", b"value \t\n", NormalizationKind.TRAILING_WHITESPACE),
        )
        for before, after, expected in cases:
            with self.subTest(expected=expected):
                findings = classify_bytes("src/example.txt", before, after)
                selected = [item for item in findings if item.kind is expected]
                self.assertEqual(1, len(selected))
                self.assertTrue(selected[0].auto_eligible)

    def test_broad_line_ending_rewrite_is_warning_and_never_auto_fixed(self) -> None:
        findings = classify_bytes(
            "src/example.txt", b"one\n two\nthree\n", b"one\r\n two\r\nthree\r\n"
        )
        self.assertEqual(
            (NormalizationKind.BROAD_LINE_ENDING_REWRITE,),
            tuple(item.kind for item in findings),
        )
        self.assertFalse(findings[0].auto_eligible)

    def test_non_whitespace_change_is_not_a_mechanical_corrective(self) -> None:
        findings = classify_bytes("src/example.txt", b"one\n", b"two\n")
        self.assertIn(
            NormalizationKind.NON_WHITESPACE_CHANGE,
            {item.kind for item in findings},
        )
        self.assertFalse(any(item.auto_eligible for item in findings))

    def test_frozen_and_applied_migration_files_fail_closed_without_auto_edit(self) -> None:
        frozen = classify_bytes(
            "docs/contracts/execution-documents/2026.7.19.3/phase.schema.json",
            b"{}\n",
            b"{}",
        )
        migration = classify_bytes(
            "db/migrations/001.sql",
            b"select 1;\n",
            b"select 1;",
            migration_state="applied",
        )
        candidate = classify_bytes(
            "db/migrations/002.sql",
            b"select 2;\n",
            b"select 2;",
            migration_state="candidate",
        )
        self.assertFalse(next(item for item in frozen if item.kind is NormalizationKind.MISSING_FINAL_NEWLINE).auto_eligible)
        self.assertFalse(next(item for item in migration if item.kind is NormalizationKind.MISSING_FINAL_NEWLINE).auto_eligible)
        self.assertTrue(next(item for item in candidate if item.kind is NormalizationKind.MISSING_FINAL_NEWLINE).auto_eligible)

    def test_narrow_fixer_changes_only_named_whitespace_and_preserves_semantic_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "src/example.txt"
            untouched = root / "src/untouched.txt"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"alpha \t\nbeta")
            untouched.write_bytes(b"keep \n")
            findings = classify_bytes(
                "src/example.txt", b"alpha\nbeta\n", target.read_bytes()
            )
            before_semantic = non_whitespace_digest(target.read_bytes())
            receipt = apply_auto_normalization(
                root,
                [item for item in findings if item.kind in {
                    NormalizationKind.TRAILING_WHITESPACE,
                    NormalizationKind.MISSING_FINAL_NEWLINE,
                }],
                writable_paths=("src/example.txt",),
            )
            self.assertEqual(b"alpha\nbeta\n", target.read_bytes())
            self.assertEqual(b"keep \n", untouched.read_bytes())
            self.assertEqual(before_semantic, receipt.non_whitespace_sha256["src/example.txt"])
            self.assertTrue(receipt.successor_required)
            self.assertEqual(
                (
                    "git diff --check",
                    "non-whitespace digest",
                    "file-related focused tests",
                    "targeted re-review",
                ),
                receipt.required_verification,
            )

    def test_fixer_rejects_unlisted_or_stale_finding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "file.txt"
            target.write_bytes(b"value")
            finding = next(
                item
                for item in classify_bytes("file.txt", b"value\n", b"value")
                if item.kind is NormalizationKind.MISSING_FINAL_NEWLINE
            )
            with self.assertRaises(PermissionError):
                apply_auto_normalization(root, (finding,), writable_paths=())
            target.write_bytes(b"changed")
            with self.assertRaises(RuntimeError):
                apply_auto_normalization(root, (finding,), writable_paths=("file.txt",))


if __name__ == "__main__":
    unittest.main()
