from __future__ import annotations

import unittest

from sagekit.resource_policy import ResourcePolicyError, resolve_resource_policy


class ResourcePolicyTests(unittest.TestCase):
    def test_missing_legacy_fields_resolve_to_conservative_default_without_failure(self) -> None:
        resolved = resolve_resource_policy(
            resource_contract_id=None,
            resource_profile=None,
            overrides=None,
            permission_mode="READ_ONLY_REVIEW",
            execution_profile=None,
            milestone_packet=False,
        )
        self.assertEqual("conservative-host-v1", resolved.profile_id)
        self.assertTrue(resolved.compatibility_defaulted)
        self.assertEqual(1, resolved.host_limits["cpu-heavy"])
        self.assertEqual(1, resolved.host_limits["package-build"])
        self.assertEqual("root-only", resolved.verification_controller)
        self.assertEqual("MANAGED", resolved.containment_policy["minimum_level"])
        self.assertEqual(1, resolved.writer_limit)

    def test_runtime_exclusive_override_only_adds_specific_resources(self) -> None:
        resolved = resolve_resource_policy(
            resource_contract_id="conservative-host-v1",
            resource_profile="conservative-host-v1",
            overrides={"runtime_exclusive": ["database:test-state", "port:4173"]},
            permission_mode="WRITE_AUTHORIZED",
            execution_profile="standard-phase@v1",
            milestone_packet=False,
        )
        self.assertEqual(
            ("database:test-state", "port:4173"), resolved.exclusive_resources
        )
        self.assertFalse(resolved.compatibility_defaulted)

    def test_unknown_profile_override_and_capacity_expansion_fail_closed(self) -> None:
        cases = (
            {"resource_contract_id": "unknown-v1"},
            {"resource_profile": "unknown-v1"},
            {"overrides": {"unknown": []}},
            {"overrides": {"active_agent_limit": 4}},
            {"overrides": {"allowed_resource_classes": ["repo-read", "repo-write", "submit-exclusive"]}},
        )
        for delta in cases:
            arguments = {
                "resource_contract_id": "conservative-host-v1",
                "resource_profile": "conservative-host-v1",
                "overrides": {},
                "permission_mode": "READ_ONLY_REVIEW",
                "execution_profile": "standard-phase@v1",
                "milestone_packet": False,
            }
            arguments.update(delta)
            with self.subTest(delta=delta), self.assertRaises(ResourcePolicyError):
                resolve_resource_policy(**arguments)

    def test_milestone_packet_is_reasoning_only(self) -> None:
        resolved = resolve_resource_policy(
            resource_contract_id="conservative-host-v1",
            resource_profile=None,
            overrides=None,
            permission_mode="READ_ONLY_REVIEW",
            execution_profile=None,
            milestone_packet=True,
        )
        self.assertEqual(("reasoning-only",), resolved.allowed_resource_classes)
        self.assertEqual(1, resolved.active_agent_limit)

    def test_light_standard_and_heavy_limits_preserve_development_parallelism(self) -> None:
        expectations = {
            "light-phase@v1": (1, 1),
            "standard-phase@v1": (3, 1),
            "heavy-phase@v1": (5, 2),
        }
        for profile, expected in expectations.items():
            with self.subTest(profile=profile):
                resolved = resolve_resource_policy(
                    resource_contract_id="conservative-host-v1",
                    resource_profile="conservative-host-v1",
                    overrides=None,
                    permission_mode="WRITE_AUTHORIZED",
                    execution_profile=profile,
                    milestone_packet=False,
                )
                self.assertEqual(expected, (resolved.active_agent_limit, resolved.writer_limit))
                self.assertEqual(1, resolved.host_limits["cpu-heavy"])
                self.assertEqual(1, resolved.host_limits["package-build"])
                self.assertEqual(1, resolved.worktree_limits["repo-write"])


if __name__ == "__main__":
    unittest.main()
