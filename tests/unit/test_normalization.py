from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sagekit.normalization import (
    NormalizationKind,
    apply_auto_normalization,
    classify_bytes,
    non_whitespace_digest,
    whitespace_preflight,
)


class MechanicalNormalizationTests(unittest.TestCase):
    def test_preflight_excludes_runtime_control_plane_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / ".sagekit/runtime/convergence-authority.json"
            target = root / "src/example.py"
            runtime.parent.mkdir(parents=True)
            target.parent.mkdir(parents=True)
            runtime.write_bytes(b'{"authority":"local"}')
            target.write_bytes(b"value")

            def git_bytes(_root: Path, *arguments: str) -> bytes:
                if arguments[:2] == ("diff", "--name-only"):
                    return b""
                if arguments[:2] == ("ls-files", "--others"):
                    return b".sagekit/runtime/convergence-authority.json\0src/example.py\0"
                if arguments == ("show", "HEAD:src/example.py"):
                    return b"value\n"
                raise AssertionError(f"unexpected Git call: {arguments}")

            with patch("sagekit.normalization._git_bytes", side_effect=git_bytes):
                report = whitespace_preflight(root)

        self.assertTrue(report.findings)
        self.assertEqual({"src/example.py"}, {item.path for item in report.findings})

    def test_safe_eof_and_trailing_whitespace_findings_are_auto_corrective(self) -> None:
        cases = (
            (b"value\n", b"value\n\n", NormalizationKind.EXTRA_BLANK_LINE_AT_EOF),
            (b"value\n", b"value", NormalizationKind.MISSING_FINAL_NEWLINE),
            (b"value\n", b"value \t\n", NormalizationKind.TRAILING_WHITESPACE),
        )
        for before, after, expected in cases:
            with self.subTest(expected=expected):
                findings = classify_bytes("src/example.py", before, after)
                selected = [item for item in findings if item.kind is expected]
                self.assertEqual(1, len(selected))
                self.assertTrue(selected[0].auto_eligible)

    def test_broad_line_ending_rewrite_is_warning_and_never_auto_fixed(self) -> None:
        findings = classify_bytes(
            "src/example.py", b"one\n two\nthree\n", b"one\r\n two\r\nthree\r\n"
        )
        self.assertEqual(
            (NormalizationKind.BROAD_LINE_ENDING_REWRITE,),
            tuple(item.kind for item in findings),
        )
        self.assertFalse(findings[0].auto_eligible)

    def test_non_whitespace_change_is_not_a_mechanical_corrective(self) -> None:
        findings = classify_bytes("src/example.py", b"one\n", b"two\n")
        self.assertIn(
            NormalizationKind.NON_WHITESPACE_CHANGE,
            {item.kind for item in findings},
        )
        self.assertFalse(any(item.auto_eligible for item in findings))

    def test_non_whitespace_change_suppresses_all_auto_findings_for_the_file(self) -> None:
        findings = classify_bytes("src/example.py", b"one\n", b"two \t")

        self.assertEqual(
            {
                NormalizationKind.NON_WHITESPACE_CHANGE,
                NormalizationKind.MISSING_FINAL_NEWLINE,
                NormalizationKind.TRAILING_WHITESPACE,
            },
            {item.kind for item in findings},
        )
        self.assertFalse(any(item.auto_eligible for item in findings))

    def test_content_token_whitespace_changes_are_not_auto_corrective(self) -> None:
        cases = (
            ("src/example.py", b'value = "a b"\n', b'value = "ab" \n'),
            ("config/settings.json", b'{"value": "a b"}\n', b'{"value": "ab"} \n'),
            ("docs/guide.md", b"a b\n", b"ab \n"),
        )

        for path, before, after in cases:
            with self.subTest(path=path):
                findings = classify_bytes(path, before, after)
                self.assertIn(
                    NormalizationKind.NON_WHITESPACE_CHANGE,
                    {item.kind for item in findings},
                )
                self.assertFalse(any(item.auto_eligible for item in findings))

    def test_non_whitespace_digest_preserves_content_token_whitespace(self) -> None:
        self.assertNotEqual(
            non_whitespace_digest(b'{"value": "a b"}\n'),
            non_whitespace_digest(b'{"value": "ab"}\n'),
        )

    def test_only_candidate_migration_files_allow_narrow_whitespace_corrections(self) -> None:
        frozen = classify_bytes(
            "docs/contracts/execution-documents/2026.7.19.3/phase.schema.json",
            b"{}\n",
            b"{}",
        )
        candidate = classify_bytes(
            "db/migrations/002.sql",
            b"select 2;\n",
            b"select 2;",
            migration_state="candidate",
        )
        self.assertFalse(next(item for item in frozen if item.kind is NormalizationKind.MISSING_FINAL_NEWLINE).auto_eligible)
        self.assertTrue(next(item for item in candidate if item.kind is NormalizationKind.MISSING_FINAL_NEWLINE).auto_eligible)
        semantic_change = classify_bytes(
            "db/migrations/002.sql",
            b"select 2;\n",
            b"select 3;\n",
            migration_state="candidate",
        )
        self.assertFalse(any(item.auto_eligible for item in semantic_change))
        for state in ("accepted", "applied", "hash-bound", None, "unrecognized"):
            with self.subTest(state=state):
                findings = classify_bytes(
                    "db/migrations/001.sql",
                    b"select 1;\n",
                    b"select 1;",
                    migration_state=state,
                )
                self.assertFalse(
                    next(
                        item
                        for item in findings
                        if item.kind is NormalizationKind.MISSING_FINAL_NEWLINE
                    ).auto_eligible
                )

    def test_narrow_fixer_changes_only_named_whitespace_and_preserves_semantic_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "src/example.py"
            untouched = root / "src/untouched.txt"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"alpha \t\nbeta")
            untouched.write_bytes(b"keep \n")
            findings = classify_bytes(
                "src/example.py", b"alpha\nbeta\n", target.read_bytes()
            )
            before_semantic = non_whitespace_digest(target.read_bytes())
            receipt = apply_auto_normalization(
                root,
                [item for item in findings if item.kind in {
                    NormalizationKind.TRAILING_WHITESPACE,
                    NormalizationKind.MISSING_FINAL_NEWLINE,
                }],
                writable_paths=("src/example.py",),
            )
            self.assertEqual(b"alpha\nbeta\n", target.read_bytes())
            self.assertEqual(b"keep \n", untouched.read_bytes())
            self.assertEqual(before_semantic, receipt.non_whitespace_sha256["src/example.py"])
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

    def test_fixer_rejects_non_whitespace_changes_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "src/example.py"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"value ")
            finding = next(
                item
                for item in classify_bytes("src/example.py", b"value\n", target.read_bytes())
                if item.kind is NormalizationKind.MISSING_FINAL_NEWLINE
            )

            with patch(
                "sagekit.normalization._normalize_selected", return_value=b"changed\n"
            ):
                with self.assertRaisesRegex(RuntimeError, "non-whitespace content"):
                    apply_auto_normalization(
                        root,
                        (finding,),
                        writable_paths=("src/example.py",),
                    )

            self.assertEqual(b"value ", target.read_bytes())

    def test_fixer_rejects_unlisted_or_stale_finding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "file.py"
            target.write_bytes(b"value")
            finding = next(
                item
                for item in classify_bytes("file.py", b"value\n", b"value")
                if item.kind is NormalizationKind.MISSING_FINAL_NEWLINE
            )
            with self.assertRaises(PermissionError):
                apply_auto_normalization(root, (finding,), writable_paths=())
            target.write_bytes(b"changed")
            with self.assertRaises(RuntimeError):
                apply_auto_normalization(root, (finding,), writable_paths=("file.py",))

    def test_markdown_hard_break_whitespace_is_not_auto_fixable(self) -> None:
        findings = classify_bytes("docs/guide.md", b"line  \n", b"line   \n")
        self.assertIn(
            NormalizationKind.NON_WHITESPACE_CHANGE,
            {item.kind for item in findings},
        )
        self.assertFalse(any(item.auto_eligible for item in findings))

    def test_multiline_literal_sensitive_content_is_not_auto_fixable(self) -> None:
        findings = classify_bytes("src/widget.py", b'\"\"\"alpha\\n\"\"\"\\n', b'\"\"\"alpha  \\n\"\"\"\\n')
        self.assertFalse(findings[0].auto_eligible)

    def test_templates_and_unknown_formats_are_not_auto_fixable(self) -> None:
        template = classify_bytes("templates/main.py", b"value\n", b"value\n\n")
        history = classify_bytes("history/state.yml", b"value\n", b"value\n\n")
        unknown = classify_bytes("resources/binary.bin", b"value\n", b"value \n")
        for findings in (template, history, unknown):
            self.assertTrue(findings)
            self.assertFalse(next(item.auto_eligible for item in findings))


if __name__ == "__main__":
    unittest.main()
