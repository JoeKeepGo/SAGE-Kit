import ntpath
import posixpath
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sagekit.milestone_scope import CloseoutDisposition, _classify_closeout
from sagekit.pathing import canonical_relative_path, is_within, relative_repo_path


class CanonicalContainmentTests(unittest.TestCase):
    def test_posix_symlinked_parent_alias_resolves_to_same_location(self):
        aliases = {
            "/alias/work/project": "/canonical/work/project",
            "/canonical/work/project/docs/M1": "/canonical/work/project/docs/M1",
        }

        with patch.object(
            posixpath,
            "realpath",
            side_effect=lambda value: aliases.get(value, value),
        ):
            relative = canonical_relative_path(
                "/alias/work/project",
                "/canonical/work/project/docs/M1",
                _path_module=posixpath,
            )

        self.assertEqual("docs/M1", relative)

    def test_distinct_lexical_aliases_for_same_location_are_inside(self):
        aliases = {
            ntpath.normcase(ntpath.normpath(r"C:\alias\project")):
                r"C:\Users\Build Agent\project",
            ntpath.normcase(ntpath.normpath(r"C:\full\project\docs\M1")):
                r"C:\Users\Build Agent\project\docs\M1",
        }

        def realpath(value):
            normalized = ntpath.normpath(value)
            return aliases.get(ntpath.normcase(normalized), normalized)

        with patch.object(ntpath, "realpath", side_effect=realpath):
            relative = canonical_relative_path(
                r"C:\alias\project",
                r"C:\full\project\docs\M1",
                _path_module=ntpath,
            )

        self.assertEqual("docs/M1", relative)

    def test_windows_case_and_separator_variants_are_inside(self):
        relative = canonical_relative_path(
            r"C:\Repo\Project",
            "c:/repo/project/docs/M1",
            _path_module=ntpath,
        )

        self.assertEqual("docs/M1", relative)

    def test_windows_short_and_full_path_api_results_are_equivalent(self):
        short_root = r"C:\Users\BUILDALIAS\project"
        full_root = r"C:\Users\Build Agent\project"

        def realpath(value):
            normalized = ntpath.normpath(value)
            folded = ntpath.normcase(normalized)
            short = ntpath.normcase(short_root)
            if folded == short:
                return full_root
            prefix = short + ntpath.sep
            if folded.startswith(prefix):
                return full_root + normalized[len(short_root):]
            return normalized

        with patch.object(ntpath, "realpath", side_effect=realpath):
            relative = canonical_relative_path(
                short_root,
                short_root + r"\docs\M1\closeout.md",
                _path_module=ntpath,
            )

        self.assertEqual("docs/M1/closeout.md", relative)

    def test_sibling_prefix_and_parent_are_outside(self):
        self.assertIsNone(
            canonical_relative_path(
                "/tmp/project",
                "/tmp/project-other/file",
            )
        )
        self.assertIsNone(
            canonical_relative_path(
                "/tmp/project",
                "/tmp/outside/file",
            )
        )

    def test_different_windows_volume_is_outside_without_exception(self):
        self.assertIsNone(
            canonical_relative_path(
                r"C:\repo",
                r"D:\repo\docs\M1",
                _path_module=ntpath,
            )
        )

    def test_nonexistent_descendant_under_root_is_inside(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = root / "not-created" / "child.json"

            self.assertEqual(
                "not-created/child.json",
                canonical_relative_path(root, candidate),
            )

    def test_nonexistent_descendant_through_escaping_symlink_ancestor_is_outside(self):
        aliases = {
            "/repo": "/repo",
            "/repo/link/missing.json": "/outside/missing.json",
        }

        with patch.object(
            posixpath,
            "realpath",
            side_effect=lambda value: aliases.get(value, value),
        ):
            relative = canonical_relative_path(
                "/repo",
                "/repo/link/missing.json",
                _path_module=posixpath,
            )

        self.assertIsNone(relative)

    def test_outside_error_does_not_leak_absolute_paths(self):
        with tempfile.TemporaryDirectory() as root_name, tempfile.TemporaryDirectory() as outside_name:
            root = Path(root_name)
            outside = Path(outside_name) / "authority.md"

            with self.assertRaises(ValueError) as raised:
                relative_repo_path(root, outside)

        message = str(raised.exception)
        self.assertNotIn(root_name, message)
        self.assertNotIn(outside_name, message)

    def test_closeout_display_does_not_use_uncanonicalized_relative_to(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            closeout = root / "docs/M1/MILESTONE_CLOSEOUT.md"
            closeout.parent.mkdir(parents=True)
            closeout.write_text("- Status: `BLOCKED`\n", encoding="utf-8")

            with patch.object(Path, "relative_to", side_effect=AssertionError):
                authority = _classify_closeout(root, closeout)

        self.assertEqual(CloseoutDisposition.NOT_ACCEPTED, authority.disposition)
        self.assertIn("docs/M1/MILESTONE_CLOSEOUT.md", authority.detail)

    def test_real_symlink_inside_and_escape_are_classified_canonically(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside_name:
            root = Path(directory)
            inside = root / "inside"
            inside.mkdir()
            inside_link = root / "inside-link"
            escape_link = root / "escape-link"
            try:
                inside_link.symlink_to(inside, target_is_directory=True)
                escape_link.symlink_to(Path(outside_name), target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            self.assertTrue(is_within(root, inside_link / "missing.json"))
            self.assertFalse(is_within(root, escape_link / "missing.json"))


if __name__ == "__main__":
    unittest.main()
