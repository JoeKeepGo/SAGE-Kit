from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from sagekit.resource_governor import ResourceClass
from sagekit.workspace_binding import (
    WorkspaceIdentity,
    authorize_command,
    build_workspace_binding,
    discover_workspace,
    verify_workspace,
)


class WorkspaceBindingTests(unittest.TestCase):
    def identity(self, root: Path) -> WorkspaceIdentity:
        return WorkspaceIdentity(
            repository_root=str(root),
            worktree_root=str(root),
            project_root=str(root),
            git_common_dir=str(root / ".git"),
            branch="codex/feature",
            head="1" * 40,
        )

    def test_non_git_project_has_stable_canonical_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            nested = root / "child"
            nested.mkdir()
            identity = discover_workspace(root)
            self.assertEqual(str(root.resolve()), identity.repository_root)
            self.assertEqual(str(root.resolve()), identity.worktree_root)
            self.assertEqual(str(root.resolve()), identity.project_root)
            self.assertIsNone(identity.git_common_dir)
            self.assertIsNone(identity.branch)
            self.assertIsNone(identity.head)

    def test_binding_digest_covers_branch_head_permission_owner_and_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            binding = build_workspace_binding(
                self.identity(root),
                base_head="0" * 40,
                permission_mode="WRITE_AUTHORIZED",
                controller="root-controller",
                allowed_paths=("sagekit/resource_governor.py",),
            )
            changed = replace(binding, branch="codex/other")
            self.assertNotEqual(binding.digest, changed.recompute_digest())
            self.assertEqual(binding.digest, binding.recompute_digest())

    def test_wrong_repo_worktree_branch_or_head_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            current = self.identity(root)
            binding = build_workspace_binding(
                current,
                base_head=current.head,
                permission_mode="WRITE_AUTHORIZED",
                controller="root-controller",
                allowed_paths=("sagekit",),
            )
            variants = (
                replace(current, repository_root=str(root / "other")),
                replace(current, worktree_root=str(root / "other")),
                replace(current, branch="main"),
                replace(current, head="2" * 40),
            )
            for variant in variants:
                with self.subTest(variant=variant):
                    result = verify_workspace(binding, current=variant)
                    self.assertFalse(result.ok)
                    self.assertTrue(result.errors)

    def test_read_only_child_cannot_start_known_mutation_command(self) -> None:
        decision = authorize_command(
            ("git", "commit", "-m", "no"),
            resource_class=ResourceClass.REPO_READ,
            permission_mode="READ_ONLY_REVIEW",
            allowed_classes=(ResourceClass.REPO_READ,),
            descendant=True,
        )
        self.assertFalse(decision.ok)
        self.assertIn("mutation", decision.reason)

    def test_interpreter_and_git_global_options_cannot_hide_mutation(self) -> None:
        commands = (
            ("git", "-C", "repository", "commit", "-m", "no"),
            ("git", "-c", "core.hooksPath=NUL", "add", "file.txt"),
            ("python", "-B", "-m", "pip", "install", "package.whl"),
            ("python", "-I", "-B", "-m", "venv", "environment"),
        )
        for command in commands:
            with self.subTest(command=command):
                decision = authorize_command(
                    command,
                    resource_class=ResourceClass.REPO_READ,
                    permission_mode="READ_ONLY_REVIEW",
                    allowed_classes=(ResourceClass.REPO_READ,),
                    descendant=True,
                )
                self.assertFalse(decision.ok)
                self.assertIn("mutation", decision.reason)

    def test_branch_show_current_is_a_repo_read_not_an_index_mutation(self) -> None:
        decision = authorize_command(
            ("git", "branch", "--show-current"),
            resource_class=ResourceClass.REPO_READ,
            permission_mode="READ_ONLY_REVIEW",
            allowed_classes=(ResourceClass.REPO_READ,),
            descendant=False,
        )

        self.assertTrue(decision.ok, decision.reason)

    def test_descendant_cannot_escalate_resource_class_or_permission(self) -> None:
        decision = authorize_command(
            ("git", "status", "--short"),
            resource_class=ResourceClass.REPO_WRITE,
            permission_mode="READ_ONLY_REVIEW",
            allowed_classes=(ResourceClass.REPO_READ,),
            descendant=True,
        )
        self.assertFalse(decision.ok)
        self.assertIn("resource class", decision.reason)

    def test_binding_rejects_abbreviated_or_non_hex_object_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            for invalid in ("1234567", "G" * 40, "A" * 40):
                with self.subTest(invalid=invalid):
                    with self.assertRaisesRegex(ValueError, "full lowercase object ID"):
                        build_workspace_binding(
                            self.identity(root),
                            base_head=invalid,
                            permission_mode="WRITE_AUTHORIZED",
                            controller="root-controller",
                            allowed_paths=(),
                        )


if __name__ == "__main__":
    unittest.main()
