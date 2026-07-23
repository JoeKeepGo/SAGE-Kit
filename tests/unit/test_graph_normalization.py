from __future__ import annotations

import ast
import copy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import sagekit
from sagekit.execution_documents import (
    ApprovalGate,
    ExecutionContract,
    ExecutionProject,
    GovernanceProfile,
    MilestoneManifest,
    PhaseManifest,
    ProjectLock,
)
from sagekit.graph_contract import (
    GraphValidationIssue,
    GraphValidationResult,
    canonical_graph_digest,
    validate_graph_contract,
)
from sagekit.graph_normalization import (
    GraphAdmissionRequest,
    GraphAdmissionSignal,
    assess_graph_admission,
    normalize_packet_to_graph,
    normalize_spec_to_graph,
)
from sagekit.packet import (
    CompiledPacket,
    GENERATED_MARKER,
    V2_GENERATED_MARKER,
    _packet_payload_digest,
)
from sagekit.resource_policy import resolve_resource_policy
from sagekit.spec_sources import (
    _SemanticAttestation,
    _semantic_payload,
    DocumentClass,
    NormalizedSpec,
    SourceConfig,
    SourceProvenance,
    verify_normalized_spec_attestation,
)
from sagekit.workspace_binding import WorkspaceBinding


REPOSITORY = Path(__file__).resolve().parents[2]
MODULE = REPOSITORY / "sagekit/graph_normalization.py"
HEX_A = "a" * 64
HEX_B = "b" * 64
HEX_C = "c" * 64


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def request(
    *signals: GraphAdmissionSignal,
    governance: str = "Standard",
    autonomy: str = "turn-based",
    completion_verifier: str | None = None,
    gates: tuple[str, ...] = (),
) -> GraphAdmissionRequest:
    return GraphAdmissionRequest(
        governance_level=governance,
        autonomy_level=autonomy,
        signals=tuple(signals),
        completion_verifier=completion_verifier,
        requested_human_gates=gates,
    )


def phase(
    root: Path,
    phase_id: str,
    *,
    objective: str,
    depends_on: tuple[str, ...] = (),
    owner: str,
    permission: str,
    verifier: tuple[str, ...],
    runtime_exclusive: tuple[str, ...] = (),
) -> PhaseManifest:
    overrides = (
        {"runtime_exclusive": list(runtime_exclusive)}
        if runtime_exclusive
        else {}
    )
    semantic = {
        "id": phase_id,
        "objective": objective,
        "depends_on": depends_on,
        "owner": owner,
        "permission": permission,
        "verifier": verifier,
        "resource_overrides": overrides,
    }
    return PhaseManifest(
        path=root / f"docs/M42/phases/{phase_id}.json",
        schema_version=1,
        sagekit_contract="sagekit-execution-documents@2026.7.20.1",
        document_model="thin-execution-documents@v1",
        phase_id=phase_id,
        objective=objective,
        depends_on=depends_on,
        execution_profile="standard-phase@v1",
        permission_mode=permission,
        owner=owner,
        writable_paths=("sagekit",) if permission != "READ_ONLY_REVIEW" else (),
        read_only_references=("docs/authority.md",),
        forbidden_paths=("docs/ACTIVE_CONTEXT.md",),
        inherit_forbidden=True,
        acceptance_criteria=(f"{phase_id} accepted",),
        verification_commands=verifier,
        evidence_requirements=(f"{phase_id} evidence",),
        stop_conditions=("stop on authority conflict",),
        handoff_target="milestone owner",
        state="ready",
        resource_profile="conservative-host-v1",
        resource_profile_reason=None,
        resource_overrides=overrides,
        digest=digest(semantic),
    )


def normalized_spec(
    root: Path = Path("D:/repository-a"),
    *,
    phase_order: tuple[str, ...] = ("P1", "P2"),
    objective_suffix: str = "",
    semantic_digest: str | None = None,
    gate_id: str = "approval-write",
    additional_gate_ids: tuple[str, ...] = (),
) -> NormalizedSpec:
    all_phases = {
        "P1": phase(
            root,
            "P1",
            objective=f"Implement{objective_suffix}",
            owner="Coder",
            permission="WRITE_AUTHORIZED",
            verifier=("python -m unittest tests.unit.test_graph_normalization",),
            runtime_exclusive=("repo-writer",),
        ),
        "P2": phase(
            root,
            "P2",
            objective="Independent verification",
            depends_on=("P1",),
            owner="Final Review",
            permission="READ_ONLY_REVIEW",
            verifier=("python -m unittest tests.unit.test_graph_contract_validation",),
        ),
    }
    phases = {phase_id: all_phases[phase_id] for phase_id in phase_order}
    dag = {phase_id: all_phases[phase_id].depends_on for phase_id in phase_order}
    gates = tuple(
        ApprovalGate(
            id=item,
            applies_to=("P1",),
            status="approved",
            permission_mode="WRITE_AUTHORIZED",
            authority_reference="docs/authority.md",
        )
        for item in (gate_id, *additional_gate_ids)
    )
    milestone = MilestoneManifest(
        path=root / "docs/M42/MILESTONE_MANIFEST.json",
        schema_version=1,
        sagekit_contract="sagekit-execution-documents@2026.7.20.1",
        document_model="thin-execution-documents@v1",
        milestone_id="M42",
        objective="Graph normalization",
        capability_outcome="Pure normalized graph",
        authority_references=("docs/authority.md",),
        governance_profile="standard-milestone@v1",
        dependency_dag=dag,
        approval_gates=gates,
        phase_ids=("P1", "P2"),
        acceptance_criteria=("Graph validates",),
        invariants=("No runtime effects",),
        state="active",
        evidence_references=("tests/unit/test_graph_normalization.py",),
        digest=digest({"milestone": "M42", "gate": gate_id}),
    )
    phase_profile = GovernanceProfile(
        id="standard-phase@v1",
        generic_rules=(),
        policy={},
        digest=HEX_A,
    )
    milestone_profile = GovernanceProfile(
        id="standard-milestone@v1",
        generic_rules=(),
        policy={},
        digest=HEX_B,
    )
    lock = ProjectLock(
        path=root / "SAGE_PROJECT.json",
        schema_version=1,
        sagekit_contract="sagekit-execution-documents@2026.7.20.1",
        execution_document_model="thin-execution-documents@v1",
        effective_from="M42",
        legacy_documents="reference-only",
        profiles=("standard-milestone@v1", "standard-phase@v1"),
        overrides={},
        resource_contract="conservative-host-v1",
        digest=HEX_A,
    )
    contract = ExecutionContract(
        contract_id="sagekit-execution-documents@2026.7.20.1",
        execution_document_model="thin-execution-documents@v1",
        runtime_defaults={},
        overrideable_policy_keys=(),
        profiles={
            phase_profile.id: phase_profile,
            milestone_profile.id: milestone_profile,
        },
        resource_digests={},
        resource_contract="conservative-host-v1",
        digest=HEX_B,
    )
    project = ExecutionProject(root, lock, contract, milestone, phases)
    config = SourceConfig(
        path=root / "SAGEKIT_CONFIG.json",
        project_id="graph-normalization-project",
        adoption_profile="package-bound",
        execution_scope="active-only",
        active_context="docs/ACTIVE_CONTEXT.md",
        doc_routing="docs/DOC_ROUTING.md",
        package={
            "name": "sagekit",
            "version": "test",
            "digest": HEX_C,
        },
        sources={},
        profiles=(),
    )
    semantic_payload = _semantic_payload(project, {}, config)
    canonical_json = json.dumps(
        semantic_payload,
        sort_keys=True,
        separators=(",", ":"),
    )
    attested_digest = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
    semantic = semantic_digest or attested_digest
    return NormalizedSpec(
        project=project,
        semantic_digest=semantic,
        semantic_attestation=_SemanticAttestation(
            schema_id="sagekit-normalized-spec-semantic",
            version=1,
            canonical_json=canonical_json,
            digest=attested_digest,
        ),
        provenance=SourceProvenance(
            target_root=str(root),
            adapter="thin-v1",
            configured_source=str(root / "docs/M42"),
            canonical_path=str(root / "docs/M42"),
            legacy_fallback=False,
            authority="configured-active-source",
        ),
        waves={},
        document_class=DocumentClass.ACTIVE_SPEC,
        active_context=None,
    )


def workspace_binding(
    root: Path,
    *,
    permission: str,
    controller: str,
) -> WorkspaceBinding:
    binding = WorkspaceBinding(
        schema_version=1,
        repository_root=str(root),
        worktree_root=str(root),
        project_root=str(root),
        git_common_dir=None,
        branch=None,
        head=None,
        base_head=None,
        permission_mode=permission,
        controller=controller,
        allowed_paths=("sagekit",) if permission != "READ_ONLY_REVIEW" else (),
        read_only_paths=("docs",),
        forbidden_paths=("docs/ACTIVE_CONTEXT.md",),
        digest="",
    )
    return replace(binding, digest=binding.recompute_digest())


def compiled_packet(
    root: Path = Path("D:/packet-repository"),
    *,
    phase_id: str | None = "P1",
    depends_on: tuple[str, ...] = (),
    permission: str | None = None,
    owner: str | None = None,
    verification: object | None = None,
    exclusive_resources: tuple[str, ...] = ("repo-writer",),
) -> CompiledPacket:
    is_phase = phase_id is not None
    effective_permission = permission or (
        "WRITE_AUTHORIZED" if is_phase else "READ_ONLY_REVIEW"
    )
    effective_owner = owner or (
        "Coder" if is_phase else "milestone-orchestration-controller"
    )
    binding = workspace_binding(
        root,
        permission=effective_permission,
        controller=effective_owner,
    )
    resource = resolve_resource_policy(
        resource_contract_id="conservative-host-v1",
        resource_profile=("conservative-host-v1" if is_phase else None),
        overrides={"runtime_exclusive": list(exclusive_resources)},
        permission_mode=effective_permission,
        execution_profile=("standard-phase@v1" if is_phase else None),
        milestone_packet=not is_phase,
    )
    resolved_policy = {
        "profile_id": (
            "standard-phase@v1"
            if is_phase
            else "standard-milestone@v1"
        ),
        "profile_digest": HEX_A,
        "values": {"permission_mode": effective_permission},
        "sources": {"permission_mode": "phase-manifest" if is_phase else "runtime-default"},
    }
    resolved_policy_digest = digest(resolved_policy)
    semantic = HEX_C
    bindings = {
        "project_lock_sha256": HEX_A,
        "milestone_manifest_sha256": HEX_B,
        "phase_manifest_sha256": HEX_C if is_phase else None,
        "contract_sha256": HEX_A,
        "resolved_policy_sha256": resolved_policy_digest,
        "resource_contract_sha256": resource.contract_digest,
        "resolved_resource_policy_sha256": resource.digest,
        "workspace_binding_sha256": binding.digest,
        "normalized_spec_sha256": semantic,
        "profiles": {resolved_policy["profile_id"]: HEX_A},
    }
    if is_phase:
        scope = {
            "objective": "Implement packet unit",
            "milestone_state": "active",
            "state": "ready",
            "depends_on": list(depends_on),
            "wave_id": None,
            "permission_mode": effective_permission,
            "owner": effective_owner,
            "writable_paths": list(binding.allowed_paths),
            "read_only_references": list(binding.read_only_paths),
            "forbidden_paths": list(binding.forbidden_paths),
            "inherit_forbidden": True,
            "acceptance_criteria": ["packet graph validates"],
            "evidence_requirements": ["focused tests"],
            "handoff_target": "milestone owner",
            "approval_gates": [],
        }
        verification_value = (
            ["python -m unittest tests.unit.test_graph_normalization"]
            if verification is None
            else verification
        )
    else:
        scope = {
            "objective": "Coordinate M42",
            "capability_outcome": "Milestone complete",
            "state": "active",
            "phase_ids": ["P1", "P2"],
            "phase_states": {"P1": "ready", "P2": "planned"},
            "dependency_dag": {"P1": [], "P2": ["P1"]},
            "waves": {},
            "approval_gates": [],
            "acceptance_criteria": ["milestone accepted"],
            "invariants": ["no authority expansion"],
            "authority_references": ["docs/authority.md"],
            "evidence_references": [],
        }
        verification_value = (
            [{"phase_id": "P1", "commands": ["focused"]}]
            if verification is None
            else verification
        )
    payload = {
        "_generated_by": GENERATED_MARKER,
        "schema_version": 3,
        "kind": "sagekit-ephemeral-execution-packet",
        "document_model": "thin-execution-documents@v1",
        "sagekit_contract": "sagekit-execution-documents@2026.7.20.1",
        "compiler_version": "test",
        "mode": "standalone",
        "target": {"milestone_id": "M42", "phase_id": phase_id},
        "source_contract": {
            "model": "normalized-spec-v1",
            "semantic_sha256": semantic,
            "active_class": "ACTIVE_SPEC",
        },
        "bindings": bindings,
        "resolved_policy": resolved_policy,
        "resolved_resource_policy": resource.to_dict(),
        "workspace_binding": binding.to_dict(),
        "scope": scope,
        "verification": verification_value,
        "stop_conditions": ["stop on authority conflict"],
        "runtime_stop_handshake": {
            "required": True,
            "action": "stop-and-handoff",
            "triggers": ["missing-or-conflicting-authority"],
        },
        "generic_rules": [],
    }
    packet_digest = _packet_payload_digest(payload)
    payload["packet_sha256"] = packet_digest
    return CompiledPacket("standalone", payload, packet_digest)


class AdmissionTests(unittest.TestCase):
    def test_no_signal_never_admits_any_governance_level(self):
        for governance in ("Light", "Standard", "Heavy"):
            with self.subTest(governance=governance):
                decision = assess_graph_admission(
                    request(governance=governance),
                    candidate_node_count=2,
                    has_dependency=True,
                )
                self.assertEqual("NOT_ADMITTED", decision.status)
                self.assertIn(
                    "no-concrete-admission-signal", decision.reason_codes
                )

    def test_invalid_or_free_text_signal_is_invalid_request(self):
        invalid = GraphAdmissionRequest(
            governance_level="Standard",
            autonomy_level="turn-based",
            signals=("complex",),  # type: ignore[arg-type]
        )
        decision = assess_graph_admission(
            invalid,
            candidate_node_count=2,
            has_dependency=True,
        )
        self.assertEqual("INVALID_REQUEST", decision.status)
        self.assertEqual(("invalid-admission-signal",), decision.reason_codes)

    def test_governance_and_autonomy_use_contract_values(self):
        bad_governance = assess_graph_admission(
            request(GraphAdmissionSignal.STATE_BOUNDARY, governance="STANDARD")
        )
        bad_autonomy = assess_graph_admission(
            request(GraphAdmissionSignal.STATE_BOUNDARY, autonomy="proactive")
        )
        self.assertEqual("INVALID_REQUEST", bad_governance.status)
        self.assertIn("invalid-governance-level", bad_governance.reason_codes)
        self.assertEqual("INVALID_REQUEST", bad_autonomy.status)
        self.assertIn("invalid-autonomy-level", bad_autonomy.reason_codes)

    def test_single_node_collapses_without_separation(self):
        collapsible = assess_graph_admission(
            request(GraphAdmissionSignal.PARALLEL_JOIN),
            candidate_node_count=1,
            has_safe_parallel_join=False,
        )
        separated = assess_graph_admission(
            request(GraphAdmissionSignal.AUTHORITY_SEPARATION),
            candidate_node_count=1,
        )
        self.assertEqual("NOT_ADMITTED", collapsible.status)
        self.assertIn("single-node-collapsible", collapsible.reason_codes)
        self.assertEqual("ADMITTED", separated.status)

    def test_multi_node_needs_real_structure(self):
        collapsible = assess_graph_admission(
            request(GraphAdmissionSignal.SEPARATE_CONTEXT),
            candidate_node_count=2,
        )
        dependent = assess_graph_admission(
            request(GraphAdmissionSignal.SEPARATE_CONTEXT),
            candidate_node_count=2,
            has_dependency=True,
        )
        parallel = assess_graph_admission(
            request(GraphAdmissionSignal.PARALLEL_JOIN),
            candidate_node_count=2,
            has_safe_parallel_join=True,
        )
        self.assertEqual("NOT_ADMITTED", collapsible.status)
        self.assertEqual("ADMITTED", dependent.status)
        self.assertEqual("ADMITTED", parallel.status)


class SpecNormalizationTests(unittest.TestCase):
    def test_normalization_uses_verified_semantic_attestation(self):
        spec = normalized_spec()
        with patch(
            "sagekit.graph_normalization.verify_normalized_spec_attestation",
            wraps=verify_normalized_spec_attestation,
        ) as verifier:
            result = normalize_spec_to_graph(
                spec,
                request(GraphAdmissionSignal.SEPARATE_CONTEXT),
            )

        self.assertEqual("ADMITTED", result.decision.status)
        verifier.assert_called_once_with(spec)

    def test_forged_bare_semantic_digest_is_rejected(self):
        forged = replace(normalized_spec(), semantic_digest="0" * 64)

        result = normalize_spec_to_graph(
            forged,
            request(GraphAdmissionSignal.SEPARATE_CONTEXT),
        )

        self.assertEqual("INVALID_REQUEST", result.decision.status)
        self.assertIsNone(result.graph)
        self.assertIn(
            "invalid-semantic-attestation",
            result.decision.reason_codes,
        )

    def test_graph_fields_come_from_attested_payload_not_project_object(self):
        spec = normalized_spec()
        forged_phase = replace(spec.project.phases["P1"], owner="Forged Owner")
        forged_project = replace(
            spec.project,
            phases={
                **spec.project.phases,
                "P1": forged_phase,
            },
        )
        forged_spec = replace(spec, project=forged_project)

        result = normalize_spec_to_graph(
            forged_spec,
            request(GraphAdmissionSignal.SEPARATE_CONTEXT),
        )

        self.assertEqual("ADMITTED", result.decision.status)
        graph = result.graph
        self.assertEqual("Coder", graph["nodes"][0]["role"])
        self.assertIn(
            "graph-normalization-project",
            graph["source_authority"]["identity"],
        )
        self.assertNotIn("Forged Owner", json.dumps(graph))

    def test_graph_mapping_does_not_read_filesystem(self):
        spec = normalized_spec()
        with patch("pathlib.Path.open", side_effect=AssertionError("filesystem read")), patch(
            "pathlib.Path.read_text", side_effect=AssertionError("filesystem read")
        ), patch("builtins.open", side_effect=AssertionError("filesystem read")):
            result = normalize_spec_to_graph(
                spec,
                request(GraphAdmissionSignal.SEPARATE_CONTEXT),
            )

        self.assertEqual("ADMITTED", result.decision.status)

    def test_valid_spec_is_deterministic_and_validated(self):
        spec = normalized_spec()
        admission = request(
            GraphAdmissionSignal.SEPARATE_CONTEXT,
            completion_verifier="urn:test:milestone-complete",
            gates=("approval-write",),
        )
        first = normalize_spec_to_graph(spec, admission)
        second = normalize_spec_to_graph(spec, admission)
        self.assertEqual("ADMITTED", first.decision.status)
        self.assertEqual(first.graph, second.graph)
        self.assertEqual(first.semantic_digest, second.semantic_digest)
        self.assertIsNotNone(first.graph)
        validation = validate_graph_contract(first.graph)
        self.assertTrue(validation.valid, validation.to_json())
        self.assertEqual(
            canonical_graph_digest(first.graph), first.semantic_digest
        )
        self.assertEqual("Standard", first.graph["governance_level"])
        self.assertEqual("turn-based", first.graph["autonomy_level"])
        self.assertEqual(
            "urn:test:milestone-complete", first.graph["completion_verifier"]
        )

    def test_context_history_reference_and_unknown_class_are_rejected(self):
        for document_class in (
            DocumentClass.ACTIVE_CONTEXT,
            DocumentClass.ACCEPTED_HISTORY,
            DocumentClass.REFERENCE_ONLY,
            "UNKNOWN",
        ):
            with self.subTest(document_class=document_class):
                spec = normalized_spec()
                object.__setattr__(spec, "document_class", document_class)
                result = normalize_spec_to_graph(
                    spec, request(GraphAdmissionSignal.STATE_BOUNDARY)
                )
                self.assertEqual("INVALID_REQUEST", result.decision.status)
                self.assertIsNone(result.graph)
                self.assertIn(
                    "invalid-spec-document-class",
                    result.decision.reason_codes,
                )

    def test_missing_semantic_digest_or_authority_is_rejected(self):
        missing_digest = replace(normalized_spec(), semantic_digest="")
        missing_authority = replace(
            normalized_spec(),
            provenance=replace(normalized_spec().provenance, authority=""),
        )
        for spec in (missing_digest, missing_authority):
            with self.subTest(spec=spec):
                result = normalize_spec_to_graph(
                    spec, request(GraphAdmissionSignal.STATE_BOUNDARY)
                )
                self.assertEqual("INVALID_REQUEST", result.decision.status)
                self.assertIsNone(result.graph)

    def test_light_optionality_and_schema_resources_do_not_auto_admit(self):
        spec = normalized_spec()
        no_signal = normalize_spec_to_graph(
            spec, request(governance="Light")
        )
        admitted = normalize_spec_to_graph(
            spec,
            request(
                GraphAdmissionSignal.SEPARATE_CONTEXT,
                governance="Light",
            ),
        )
        self.assertEqual("NOT_ADMITTED", no_signal.decision.status)
        self.assertIsNone(no_signal.graph)
        self.assertEqual("ADMITTED", admitted.decision.status)
        self.assertIsNotNone(admitted.graph)

    def test_nodes_dependencies_resources_gates_and_join_are_stable(self):
        result = normalize_spec_to_graph(
            normalized_spec(phase_order=("P2", "P1")),
            request(
                GraphAdmissionSignal.SEPARATE_CONTEXT,
                gates=("approval-write",),
            ),
        )
        graph = result.graph
        self.assertIsNotNone(graph)
        self.assertEqual(["P1", "P2"], [node["id"] for node in graph["nodes"]])
        self.assertEqual([], graph["nodes"][0]["depends_on"])
        self.assertEqual(["P1"], graph["nodes"][1]["depends_on"])
        self.assertEqual("Coder", graph["nodes"][0]["role"])
        self.assertEqual("WRITE_AUTHORIZED", graph["nodes"][0]["permission"])
        self.assertEqual(["repo-writer"], graph["nodes"][0]["resources"])
        self.assertEqual("required", graph["nodes"][0]["classification"])
        self.assertEqual(["approval-write"], graph["human_gates"])
        self.assertEqual(
            {
                "id": "M42-implementation-complete",
                "requires": ["P1", "P2"],
                "policy": "all-required",
            },
            graph["joins"][0],
        )

    def test_order_and_relocation_do_not_change_payload_semantics(self):
        left = normalize_spec_to_graph(
            normalized_spec(
                Path("D:/one/repository"), phase_order=("P1", "P2")
            ),
            request(GraphAdmissionSignal.SEPARATE_CONTEXT),
        )
        right = normalize_spec_to_graph(
            normalized_spec(
                Path("E:/relocated/repository"), phase_order=("P2", "P1")
            ),
            request(GraphAdmissionSignal.SEPARATE_CONTEXT),
        )
        self.assertEqual(left.semantic_digest, right.semantic_digest)
        self.assertEqual(left.graph["nodes"], right.graph["nodes"])
        self.assertNotEqual(
            left.graph["source_authority"]["reference"],
            right.graph["source_authority"]["reference"],
        )

    def test_semantic_changes_change_graph_digest(self):
        baseline = normalize_spec_to_graph(
            normalized_spec(),
            request(GraphAdmissionSignal.SEPARATE_CONTEXT),
        )
        changed_objective = normalize_spec_to_graph(
            normalized_spec(objective_suffix=" changed"),
            request(GraphAdmissionSignal.SEPARATE_CONTEXT),
        )
        changed_gate = normalize_spec_to_graph(
            normalized_spec(gate_id="different-gate"),
            request(GraphAdmissionSignal.SEPARATE_CONTEXT),
        )
        changed_governance = normalize_spec_to_graph(
            normalized_spec(),
            request(
                GraphAdmissionSignal.SEPARATE_CONTEXT,
                governance="Heavy",
            ),
        )
        self.assertNotEqual(
            baseline.semantic_digest, changed_objective.semantic_digest
        )
        self.assertNotEqual(
            baseline.semantic_digest, changed_gate.semantic_digest
        )
        self.assertNotEqual(
            baseline.semantic_digest, changed_governance.semantic_digest
        )

    def test_no_nodes_are_invented_and_current_spec_has_no_optional_phases(self):
        result = normalize_spec_to_graph(
            normalized_spec(),
            request(GraphAdmissionSignal.SEPARATE_CONTEXT),
        )
        nodes = result.graph["nodes"]
        self.assertEqual({"P1", "P2"}, {node["id"] for node in nodes})
        self.assertTrue(
            all(node["classification"] == "required" for node in nodes)
        )
        lowered = json.dumps(result.graph).lower()
        for invented in ("reviewer", "corrective", "submit", "safety"):
            self.assertNotIn(invented, lowered)

    def test_unknown_requested_gate_cannot_be_opened(self):
        result = normalize_spec_to_graph(
            normalized_spec(),
            request(
                GraphAdmissionSignal.SEPARATE_CONTEXT,
                gates=("invented-gate",),
            ),
        )
        self.assertEqual("INVALID_REQUEST", result.decision.status)
        self.assertIsNone(result.graph)
        self.assertIn(
            "unknown-requested-human-gate", result.decision.reason_codes
        )

    def test_empty_gate_assertion_preserves_all_project_gates(self):
        result = normalize_spec_to_graph(
            normalized_spec(additional_gate_ids=("approval-submit",)),
            request(GraphAdmissionSignal.SEPARATE_CONTEXT),
        )

        self.assertEqual("ADMITTED", result.decision.status)
        self.assertEqual(
            ["approval-submit", "approval-write"],
            result.graph["human_gates"],
        )

    def test_malformed_attestation_returns_stable_error_without_raw_exception(self):
        spec = normalized_spec()
        malformed = replace(
            spec,
            semantic_attestation=replace(
                spec.semantic_attestation,
                canonical_json='{"project":',
            ),
        )

        result = normalize_spec_to_graph(
            malformed,
            request(GraphAdmissionSignal.SEPARATE_CONTEXT),
        )

        self.assertEqual("INVALID_REQUEST", result.decision.status)
        self.assertEqual(
            ("invalid-semantic-attestation",),
            result.decision.reason_codes,
        )
        self.assertIsNone(result.graph)
        self.assertIsNone(result.semantic_digest)

    def test_invalid_attestation_never_returns_partial_graph(self):
        spec = normalized_spec()
        invalid = replace(
            spec,
            semantic_attestation=replace(
                spec.semantic_attestation,
                digest="f" * 64,
            ),
        )

        result = normalize_spec_to_graph(
            invalid,
            request(GraphAdmissionSignal.SEPARATE_CONTEXT),
        )

        self.assertEqual("INVALID_REQUEST", result.decision.status)
        self.assertIsNone(result.graph)
        self.assertIsNone(result.semantic_digest)
        self.assertEqual((), result.issues)

    def test_unhashable_attested_permissions_fail_closed(self):
        spec = normalized_spec()
        for target, malformed_permission in (
            ("gate", []),
            ("phase", {}),
        ):
            with self.subTest(target=target):
                payload = verify_normalized_spec_attestation(spec)
                if target == "gate":
                    payload["milestone"]["approval_gates"][0][
                        "permission_mode"
                    ] = malformed_permission
                else:
                    payload["phases"]["P1"][
                        "permission_mode"
                    ] = malformed_permission
                canonical_json = json.dumps(
                    payload,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                attested_digest = hashlib.sha256(
                    canonical_json.encode("utf-8")
                ).hexdigest()
                malformed = replace(
                    spec,
                    semantic_digest=attested_digest,
                    semantic_attestation=_SemanticAttestation(
                        schema_id=spec.semantic_attestation.schema_id,
                        version=spec.semantic_attestation.version,
                        canonical_json=canonical_json,
                        digest=attested_digest,
                    ),
                )

                result = normalize_spec_to_graph(
                    malformed,
                    request(GraphAdmissionSignal.SEPARATE_CONTEXT),
                )

                self.assertEqual("INVALID_REQUEST", result.decision.status)
                self.assertEqual(
                    ("invalid-semantic-attestation",),
                    result.decision.reason_codes,
                )
                self.assertIsNone(result.graph)
                self.assertIsNone(result.semantic_digest)


class PacketNormalizationTests(unittest.TestCase):
    def test_phase_packet_maps_one_execution_unit(self):
        packet = compiled_packet()
        result = normalize_packet_to_graph(
            packet, request(GraphAdmissionSignal.AUTHORITY_SEPARATION)
        )
        self.assertEqual("ADMITTED", result.decision.status)
        graph = result.graph
        self.assertIsNotNone(graph)
        self.assertEqual(["P1"], [node["id"] for node in graph["nodes"]])
        node = graph["nodes"][0]
        self.assertEqual("Coder", node["role"])
        self.assertEqual("WRITE_AUTHORIZED", node["permission"])
        self.assertEqual([], node["depends_on"])
        self.assertEqual(["repo-writer"], node["resources"])
        self.assertTrue(node["verifier"].startswith("urn:sagekit:"))
        self.assertTrue(validate_graph_contract(graph).valid)

    def test_phase_packet_with_external_dependency_fails_closed(self):
        result = normalize_packet_to_graph(
            compiled_packet(depends_on=("P0",)),
            request(GraphAdmissionSignal.SEPARATE_CONTEXT),
        )
        self.assertEqual("INVALID_REQUEST", result.decision.status)
        self.assertIsNone(result.graph)
        self.assertIn(
            "insufficient-packet-authority", result.decision.reason_codes
        )

    def test_milestone_packet_is_one_read_only_controller(self):
        result = normalize_packet_to_graph(
            compiled_packet(phase_id=None),
            request(GraphAdmissionSignal.STATE_BOUNDARY),
        )
        self.assertEqual("ADMITTED", result.decision.status)
        graph = result.graph
        self.assertEqual(1, len(graph["nodes"]))
        node = graph["nodes"][0]
        self.assertEqual("M42", node["id"])
        self.assertEqual("milestone-orchestration-controller", node["role"])
        self.assertEqual("READ_ONLY_REVIEW", node["permission"])
        self.assertEqual([], node["depends_on"])
        self.assertNotIn("P1", json.dumps(graph))
        self.assertNotIn("P2", json.dumps(graph))

    def test_tampered_packet_and_plain_dict_are_rejected(self):
        packet = compiled_packet()
        packet.payload["scope"]["permission_mode"] = "SUBMIT_AUTHORIZED"
        tampered = normalize_packet_to_graph(
            packet, request(GraphAdmissionSignal.AUTHORITY_SEPARATION)
        )
        plain = normalize_packet_to_graph(
            copy.deepcopy(packet.payload),  # type: ignore[arg-type]
            request(GraphAdmissionSignal.AUTHORITY_SEPARATION),
        )
        self.assertEqual("INVALID_REQUEST", tampered.decision.status)
        self.assertIsNone(tampered.graph)
        self.assertIn("packet-digest-mismatch", tampered.decision.reason_codes)
        self.assertEqual("INVALID_REQUEST", plain.decision.status)
        self.assertIn("invalid-packet-type", plain.decision.reason_codes)

    def test_v1_and_v2_packets_cannot_masquerade_as_v3(self):
        for version, marker in (
            (1, "sagekit-packet-compile@v1"),
            (2, V2_GENERATED_MARKER),
        ):
            with self.subTest(version=version):
                current = compiled_packet()
                payload = copy.deepcopy(current.payload)
                payload["schema_version"] = version
                payload["_generated_by"] = marker
                payload["packet_sha256"] = _packet_payload_digest(payload)
                old = CompiledPacket(
                    payload["mode"], payload, payload["packet_sha256"]
                )
                result = normalize_packet_to_graph(
                    old, request(GraphAdmissionSignal.STATE_BOUNDARY)
                )
                self.assertEqual("INVALID_REQUEST", result.decision.status)
                self.assertIsNone(result.graph)
                self.assertIn(
                    "unsupported-packet-schema", result.decision.reason_codes
                )

    def test_insufficient_phase_authority_fails_closed(self):
        packet = compiled_packet()
        payload = copy.deepcopy(packet.payload)
        del payload["scope"]["owner"]
        payload["packet_sha256"] = _packet_payload_digest(payload)
        insufficient = CompiledPacket(
            payload["mode"], payload, payload["packet_sha256"]
        )
        result = normalize_packet_to_graph(
            insufficient, request(GraphAdmissionSignal.STATE_BOUNDARY)
        )
        self.assertEqual("INVALID_REQUEST", result.decision.status)
        self.assertIsNone(result.graph)
        self.assertIn(
            "insufficient-packet-authority", result.decision.reason_codes
        )

    def test_packet_relocation_does_not_change_graph_digest(self):
        left = normalize_packet_to_graph(
            compiled_packet(Path("D:/packet-one")),
            request(GraphAdmissionSignal.STATE_BOUNDARY),
        )
        right = normalize_packet_to_graph(
            compiled_packet(Path("E:/packet-two")),
            request(GraphAdmissionSignal.STATE_BOUNDARY),
        )
        self.assertNotEqual(
            compiled_packet(Path("D:/packet-one")).digest,
            compiled_packet(Path("E:/packet-two")).digest,
        )
        self.assertEqual(left.semantic_digest, right.semantic_digest)


class SafetyAndFailureTests(unittest.TestCase):
    def test_invalid_candidate_never_returns_partial_graph(self):
        invalid = GraphValidationResult(
            valid=False,
            issues=(
                GraphValidationIssue(
                    "$.nodes",
                    "forced-invalid",
                    "forced validator failure",
                ),
            ),
        )
        with patch(
            "sagekit.graph_normalization.validate_graph_contract",
            return_value=invalid,
        ), patch(
            "sagekit.graph_normalization.canonical_graph_digest"
        ) as canonical:
            result = normalize_spec_to_graph(
                normalized_spec(),
                request(GraphAdmissionSignal.SEPARATE_CONTEXT),
            )
        self.assertEqual("INVALID_REQUEST", result.decision.status)
        self.assertIsNone(result.graph)
        self.assertIsNone(result.semantic_digest)
        self.assertEqual(invalid.issues, result.issues)
        self.assertIn(
            "graph-contract-invalid", result.decision.reason_codes
        )
        canonical.assert_not_called()

    def test_inputs_are_not_mutated(self):
        spec = normalized_spec()
        packet = compiled_packet()
        spec_before = copy.deepcopy(spec)
        packet_before = copy.deepcopy(packet)
        normalize_spec_to_graph(
            spec, request(GraphAdmissionSignal.SEPARATE_CONTEXT)
        )
        normalize_packet_to_graph(
            packet, request(GraphAdmissionSignal.STATE_BOUNDARY)
        )
        self.assertEqual(spec_before, spec)
        self.assertEqual(packet_before, packet)

    def test_import_and_repeated_calls_have_no_filesystem_side_effects(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = (
                "from sagekit.graph_normalization import "
                "GraphAdmissionRequest, assess_graph_admission\n"
                "r=GraphAdmissionRequest('Light','turn-based',())\n"
                "assess_graph_admission(r)\n"
                "assess_graph_admission(r)\n"
            )
            completed = subprocess.run(
                [sys.executable, "-B", "-c", script],
                cwd=root,
                env={
                    "PYTHONPATH": str(REPOSITORY),
                    "PYTHONDONTWRITEBYTECODE": "1",
                },
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertEqual([], list(root.iterdir()))

    def test_no_public_export_cli_network_or_process_behavior(self):
        self.assertFalse(hasattr(sagekit, "normalize_spec_to_graph"))
        tree = ast.parse(MODULE.read_text(encoding="utf-8"))
        forbidden_imports = {
            "argparse",
            "click",
            "socket",
            "subprocess",
            "urllib",
            "requests",
        }
        imported = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imported.update(
            node.module.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        )
        self.assertTrue(forbidden_imports.isdisjoint(imported))


if __name__ == "__main__":
    unittest.main()
