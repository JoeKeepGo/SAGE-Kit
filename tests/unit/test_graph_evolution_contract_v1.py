import copy
import hashlib
import json
import subprocess
import unittest
from pathlib import Path

from sagekit.graph_contract import canonical_graph_digest
from sagekit.graph_evolution_contract import (
    GRAPH_EVOLUTION_OPERATIONS,
    STAGE5_LINEAGE_CONTRACT_SHA256,
    GraphEvolutionContractError,
    canonical_graph_evolution_digest,
    validate_decision_chain,
    validate_graph_evolution_acceptance,
    validate_graph_evolution_document,
    validate_graph_evolution_error,
    validate_graph_evolution_outcome,
    validate_graph_evolution_preauthorization,
    validate_graph_evolution_proposal,
    validate_graph_evolution_request,
    validate_graph_evolution_result,
)


REPOSITORY = Path(__file__).resolve().parents[2]
CANONICAL = REPOSITORY / "docs/contracts/graph-evolution/v1"
PACKAGED = REPOSITORY / "sagekit/resources/contracts/graph-evolution/v1"
RESOURCE_NAMES = (
    "contract.json",
    "request.schema.json",
    "preauthorization.schema.json",
    "proposal.schema.json",
    "acceptance.schema.json",
    "result.schema.json",
    "error.schema.json",
)
OPERATIONS = {
    "ADD_CORRECTIVE",
    "ADD_VERIFICATION",
    "ADD_INVESTIGATION",
    "SPLIT_PENDING",
    "DISABLE_OPTIONAL_PENDING",
    "NO_CHANGE",
}
CHANGE_CLASSES = {"C0", "C1", "C2", "C3"}
PERMISSIONS = {
    "READ_ONLY_REVIEW",
    "WRITE_AUTHORIZED",
    "CORRECTIVE_AUTHORIZED",
    "ENVIRONMENT_WRITE_AUTHORIZED",
    "SUBMIT_AUTHORIZED",
}
FORBIDDEN_PROPERTIES = {
    "prompt",
    "private_reasoning",
    "reasoning",
    "chain_of_thought",
    "transcript",
    "chat_transcript",
    "tool_transcript",
    "stdout",
    "stderr",
    "environment",
    "environment_dump",
    "credential",
    "credentials",
    "secret",
    "secrets",
    "command",
    "callback",
    "payload",
    "runtime_event",
    "state_write",
    "lease",
    "lock",
    "scheduler",
    "database",
}
DOMAINS = {
    "request": b"sagekit-graph-evolution-request-v1\0",
    "preauthorization": b"sagekit-graph-evolution-preauthorization-v1\0",
    "proposal": b"sagekit-graph-evolution-proposal-v1\0",
    "acceptance": b"sagekit-graph-evolution-acceptance-v1\0",
    "result": b"sagekit-graph-evolution-result-v1\0",
    "error": b"sagekit-graph-evolution-error-v1\0",
}


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_resource_sha256(path):
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def canonical_bytes(value):
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def walk(value):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def minimal_graph(generation=8):
    return {
        "schema_id": "urn:sagekit:graph-contract:v1:graph",
        "schema_version": 1,
        "graph_id": "graph/spec",
        "generation": generation,
        "source_authority": {
            "identity": "pm/rebuild",
            "reference": "authority/stage6",
        },
        "governance_level": "Heavy",
        "autonomy_level": "turn-based",
        "human_gates": ["acceptance"],
        "nodes": [
            {
                "id": "node/verify",
                "role": "Verifier",
                "depends_on": [],
                "permission": "READ_ONLY_REVIEW",
                "verifier": "verifier/focused",
                "output_contract": "urn:sagekit:graph-contract:v1:node-result",
                "resources": [],
                "classification": "required",
            }
        ],
        "joins": [],
    }


def evolution_parent_graph():
    graph = minimal_graph(7)
    graph["completion_verifier"] = "verifier/completion"
    graph["human_gates"] = ["gate/acceptance"]
    graph["nodes"] = [
        {
            "id": "node/controller",
            "role": "Controller",
            "depends_on": [],
            "permission": "WRITE_AUTHORIZED",
            "verifier": "verifier/controller",
            "output_contract": "urn:sagekit:graph-contract:v1:node-result",
            "resources": [],
            "classification": "required",
        },
        {
            "id": "node/verify",
            "role": "Verifier",
            "depends_on": [],
            "permission": "READ_ONLY_REVIEW",
            "verifier": "verifier/focused",
            "output_contract": "urn:sagekit:graph-contract:v1:node-result",
            "resources": [],
            "classification": "required",
        },
        {
            "id": "node/split",
            "role": "Implementer",
            "depends_on": [],
            "permission": "WRITE_AUTHORIZED",
            "verifier": "verifier/split",
            "output_contract": "urn:sagekit:graph-contract:v1:node-result",
            "resources": ["scope/original"],
            "classification": "required",
        },
        {
            "id": "node/optional",
            "role": "Investigator",
            "depends_on": [],
            "permission": "READ_ONLY_REVIEW",
            "verifier": "verifier/investigation",
            "output_contract": "urn:sagekit:graph-contract:v1:node-result",
            "resources": [],
            "classification": "optional",
        },
    ]
    graph["joins"] = [
        {
            "id": "gate/acceptance",
            "requires": ["node/controller", "node/verify"],
            "policy": "manual-gate",
        }
    ]
    return graph


def authority():
    return {
        "authority_id": "pm/rebuild",
        "authority_role": "PROJECT_MANAGER",
        "authority_ref": "authority/stage6",
    }


def proposer():
    return {
        "node_id": "node/controller",
        "role": "Controller",
        "permission": "WRITE_AUTHORIZED",
    }


def request(operation="ADD_VERIFICATION"):
    return {
        "schema_id": "urn:sagekit:graph-evolution:v1:request",
        "schema_version": 1,
        "request_id": "request/verify-001",
        "operation": operation,
        "graph_id": "graph/spec",
        "parent_generation": 7,
        "parent_graph_digest": "a" * 64,
        "authority": authority(),
        "proposer": proposer(),
        "node_id": "node/verify",
        "change_class": "C1",
        "reason_code": "VERIFICATION_GAP",
        "evidence_refs": ["evidence/stage5/failure-001"],
        "decision_refs": ["decision/review-001"],
        "affected_paths": ["sagekit/graph_contract.py"],
        "stage5_lineage_digest": "b" * 64,
    }


def preauthorization():
    return {
        "schema_id": "urn:sagekit:graph-evolution:v1:preauthorization",
        "schema_version": 1,
        "preauthorization_id": "preauth/stage6-001",
        "graph_id": "graph/spec",
        "parent_generation": 7,
        "parent_graph_digest": "a" * 64,
        "authority": authority(),
        "allowed_operations": [
            "ADD_CORRECTIVE",
            "ADD_VERIFICATION",
            "ADD_INVESTIGATION",
            "SPLIT_PENDING",
            "DISABLE_OPTIONAL_PENDING",
            "NO_CHANGE",
        ],
        "allowed_change_classes": ["C0", "C1"],
        "allowed_node_ids": ["node/controller", "node/verify"],
        "allowed_roles": ["Controller", "Verifier"],
        "allowed_permissions": [
            "READ_ONLY_REVIEW",
            "WRITE_AUTHORIZED",
            "CORRECTIVE_AUTHORIZED",
        ],
        "allowed_paths": ["sagekit/**", "tests/unit/**"],
        "generation_budget": {
            "max_target_generation": 10,
            "remaining_generations": 3,
        },
        "operation_budgets": {
            "ADD_CORRECTIVE": 2,
            "ADD_VERIFICATION": 2,
            "ADD_INVESTIGATION": 1,
            "SPLIT_PENDING": 1,
            "DISABLE_OPTIONAL_PENDING": 1,
            "NO_CHANGE": 3,
        },
        "evaluator": {
            "node_id": "node/verify",
            "role": "Verifier",
            "permission": "READ_ONLY_REVIEW",
            "authority_ref": "authority/evaluator",
            "independent": True,
        },
        "stop_conditions": [
            "BUDGET_EXHAUSTED",
            "NO_PROGRESS",
            "EVALUATOR_REJECTED",
            "AUTHORITY_CHANGED",
            "CONTRACT_CHANGED",
            "PERMISSION_EXPANSION",
            "GATE_OR_VERIFIER_REMOVAL",
        ],
    }


def proposal(operation="ADD_VERIFICATION"):
    value = request(operation)
    value["schema_id"] = "urn:sagekit:graph-evolution:v1:proposal"
    value["proposal_id"] = "proposal/verify-001"
    value["request_digest"] = canonical_graph_evolution_digest(
        "request", request(operation)
    )
    value["preauthorization_digest"] = canonical_graph_evolution_digest(
        "preauthorization", preauthorization()
    )
    if operation == "NO_CHANGE":
        return value
    target_graph = minimal_graph()
    value.update(
        {
            "target_generation": 8,
            "target_graph": target_graph,
            "target_graph_digest": canonical_graph_digest(target_graph),
        }
    )
    return value


def acceptance(decision="ACCEPTED", operation="ADD_VERIFICATION"):
    return {
        "schema_id": "urn:sagekit:graph-evolution:v1:acceptance",
        "schema_version": 1,
        "acceptance_id": "acceptance/verify-001",
        "proposal_digest": canonical_graph_evolution_digest(
            "proposal", proposal(operation)
        ),
        "preauthorization_digest": canonical_graph_evolution_digest(
            "preauthorization", preauthorization()
        ),
        "decision": decision,
        "authority": authority(),
        "evaluator": {
            "node_id": "node/verify",
            "role": "Verifier",
            "decision": "APPROVE" if decision == "ACCEPTED" else "REJECT",
            "decision_ref": "decision/evaluator-001",
        },
        "reason_code": (
            "WITHIN_PREAUTHORIZATION"
            if decision == "ACCEPTED"
            else "EVALUATOR_REJECTED"
        ),
        "decision_refs": ["decision/pm-001"],
    }


def result(operation="ADD_VERIFICATION", outcome="ACCEPTED"):
    value = {
        "schema_id": "urn:sagekit:graph-evolution:v1:result",
        "schema_version": 1,
        "request_digest": canonical_graph_evolution_digest(
            "request", request(operation)
        ),
        "preauthorization_digest": canonical_graph_evolution_digest(
            "preauthorization", preauthorization()
        ),
        "proposal_digest": canonical_graph_evolution_digest(
            "proposal", proposal(operation)
        ),
        "acceptance_digest": canonical_graph_evolution_digest(
            "acceptance", acceptance("ACCEPTED", operation)
        ),
        "operation": operation,
        "outcome": outcome,
        "graph_id": "graph/spec",
        "parent_generation": 7,
        "parent_graph_digest": "a" * 64,
        "message_code": (
            "NO_CHANGE_ACCEPTED"
            if operation == "NO_CHANGE"
            else "EVOLUTION_ACCEPTED"
        ),
    }
    if operation != "NO_CHANGE" and outcome == "ACCEPTED":
        graph = minimal_graph()
        value["target_generation"] = 8
        value["target_graph_digest"] = canonical_graph_digest(graph)
    return value


def error():
    return {
        "schema_id": "urn:sagekit:graph-evolution:v1:error",
        "schema_version": 1,
        "error_code": "INPUT_INVALID",
        "message_code": "STRICT_DOCUMENT_REQUIRED",
        "document_kind": "proposal",
        "issues": [
            {
                "location": "$.operation",
                "issue_code": "INVALID_OPERATION",
            }
        ],
    }


def operation_chain(operation="ADD_VERIFICATION", decision="ACCEPTED"):
    parent = evolution_parent_graph()
    parent_digest = canonical_graph_digest(parent)
    subjects = {
        "ADD_CORRECTIVE": "node/corrective",
        "ADD_VERIFICATION": "node/new-verify",
        "ADD_INVESTIGATION": "node/investigate",
        "SPLIT_PENDING": "node/split",
        "DISABLE_OPTIONAL_PENDING": "node/optional",
        "NO_CHANGE": "node/verify",
    }
    reasons = {
        "ADD_CORRECTIVE": "OBSERVED_FAILURE",
        "ADD_VERIFICATION": "VERIFICATION_GAP",
        "ADD_INVESTIGATION": "BLOCKING_UNCERTAINTY",
        "SPLIT_PENDING": "NODE_TOO_BROAD",
        "DISABLE_OPTIONAL_PENDING": "OPTIONAL_NODE_NO_LONGER_DECISIVE",
        "NO_CHANGE": "EXISTING_GRAPH_SUFFICIENT",
    }
    req = request(operation)
    req.update(
        {
            "node_id": subjects[operation],
            "reason_code": reasons[operation],
            "parent_graph_digest": parent_digest,
        }
    )
    if operation == "ADD_CORRECTIVE":
        req["finding_ref"] = "finding/review-001"
        req["root_cause_ref"] = "root-cause/review-001"
    if operation in {"SPLIT_PENDING", "DISABLE_OPTIONAL_PENDING"}:
        req["subject_status"] = "PENDING"

    preauth = preauthorization()
    preauth["parent_graph_digest"] = parent_digest
    preauth["allowed_node_ids"] = [
        "node/controller",
        "node/verify",
        "node/split",
        "node/optional",
        "node/corrective",
        "node/new-verify",
        "node/investigate",
        "node/split-part",
    ]
    preauth["allowed_roles"] = [
        "Controller",
        "Verifier",
        "Corrector",
        "Investigator",
        "Implementer",
    ]

    prop = copy.deepcopy(req)
    prop["schema_id"] = "urn:sagekit:graph-evolution:v1:proposal"
    prop["proposal_id"] = f"proposal/{operation.lower()}"
    prop["request_digest"] = canonical_graph_evolution_digest("request", req)
    prop["preauthorization_digest"] = canonical_graph_evolution_digest(
        "preauthorization", preauth
    )
    if operation != "NO_CHANGE":
        target = copy.deepcopy(parent)
        target["generation"] = 8
        if operation == "ADD_CORRECTIVE":
            target["nodes"].append(
                {
                    "id": "node/corrective",
                    "role": "Corrector",
                    "depends_on": [],
                    "permission": "CORRECTIVE_AUTHORIZED",
                    "verifier": "verifier/corrective",
                    "output_contract": "urn:sagekit:graph-contract:v1:node-result",
                    "resources": [],
                    "classification": "required",
                }
            )
        elif operation == "ADD_VERIFICATION":
            target["nodes"].append(
                {
                    "id": "node/new-verify",
                    "role": "Verifier",
                    "depends_on": [],
                    "permission": "READ_ONLY_REVIEW",
                    "verifier": "verifier/new-focused",
                    "output_contract": "urn:sagekit:graph-contract:v1:node-result",
                    "resources": [],
                    "classification": "required",
                }
            )
        elif operation == "ADD_INVESTIGATION":
            target["nodes"].append(
                {
                    "id": "node/investigate",
                    "role": "Investigator",
                    "depends_on": [],
                    "permission": "READ_ONLY_REVIEW",
                    "verifier": "verifier/investigation",
                    "output_contract": "urn:sagekit:graph-contract:v1:node-result",
                    "resources": [],
                    "classification": "optional",
                }
            )
        elif operation == "SPLIT_PENDING":
            target["nodes"].append(
                {
                    "id": "node/split-part",
                    "role": "Implementer",
                    "depends_on": ["node/split"],
                    "permission": "WRITE_AUTHORIZED",
                    "verifier": "verifier/split",
                    "output_contract": "urn:sagekit:graph-contract:v1:node-result",
                    "resources": ["scope/split-part"],
                    "classification": "required",
                }
            )
        else:
            target["nodes"] = [
                node for node in target["nodes"] if node["id"] != "node/optional"
            ]
        prop["target_generation"] = 8
        prop["target_graph"] = target
        prop["target_graph_digest"] = canonical_graph_digest(target)

    accept = {
        "schema_id": "urn:sagekit:graph-evolution:v1:acceptance",
        "schema_version": 1,
        "acceptance_id": f"acceptance/{operation.lower()}",
        "proposal_digest": canonical_graph_evolution_digest("proposal", prop),
        "preauthorization_digest": canonical_graph_evolution_digest(
            "preauthorization", preauth
        ),
        "decision": decision,
        "authority": authority(),
        "evaluator": {
            "node_id": "node/verify",
            "role": "Verifier",
            "decision": "APPROVE" if decision == "ACCEPTED" else "REJECT",
            "decision_ref": "decision/evaluator-001",
        },
        "reason_code": (
            "WITHIN_PREAUTHORIZATION"
            if decision == "ACCEPTED"
            else "EVALUATOR_REJECTED"
        ),
        "decision_refs": ["decision/pm-001"],
    }
    outcome = (
        "REJECTED"
        if decision == "REJECTED"
        else "NO_CHANGE"
        if operation == "NO_CHANGE"
        else "ACCEPTED"
    )
    res = {
        "schema_id": "urn:sagekit:graph-evolution:v1:result",
        "schema_version": 1,
        "request_digest": canonical_graph_evolution_digest("request", req),
        "preauthorization_digest": canonical_graph_evolution_digest(
            "preauthorization", preauth
        ),
        "proposal_digest": canonical_graph_evolution_digest("proposal", prop),
        "acceptance_digest": canonical_graph_evolution_digest(
            "acceptance", accept
        ),
        "operation": operation,
        "outcome": outcome,
        "graph_id": parent["graph_id"],
        "parent_generation": parent["generation"],
        "parent_graph_digest": parent_digest,
        "message_code": (
            "EVOLUTION_REJECTED"
            if outcome == "REJECTED"
            else "NO_CHANGE_ACCEPTED"
            if outcome == "NO_CHANGE"
            else "EVOLUTION_ACCEPTED"
        ),
    }
    if outcome == "ACCEPTED":
        res["target_generation"] = prop["target_generation"]
        res["target_graph_digest"] = prop["target_graph_digest"]
    return req, preauth, prop, accept, res, parent


def rebind_chain(chain):
    req, preauth, prop, accept, res, parent = chain
    parent_digest = canonical_graph_digest(parent)
    for document in (req, preauth, prop, res):
        document["parent_graph_digest"] = parent_digest
    prop["request_digest"] = canonical_graph_evolution_digest("request", req)
    prop["preauthorization_digest"] = canonical_graph_evolution_digest(
        "preauthorization", preauth
    )
    if "target_graph" in prop:
        prop["target_graph_digest"] = canonical_graph_digest(prop["target_graph"])
    accept["proposal_digest"] = canonical_graph_evolution_digest("proposal", prop)
    accept["preauthorization_digest"] = canonical_graph_evolution_digest(
        "preauthorization", preauth
    )
    res["request_digest"] = canonical_graph_evolution_digest("request", req)
    res["preauthorization_digest"] = canonical_graph_evolution_digest(
        "preauthorization", preauth
    )
    res["proposal_digest"] = canonical_graph_evolution_digest("proposal", prop)
    res["acceptance_digest"] = canonical_graph_evolution_digest(
        "acceptance", accept
    )
    if res["outcome"] == "ACCEPTED":
        res["target_graph_digest"] = prop["target_graph_digest"]
    return chain


def powershell_test_json(schema_path, value):
    command = (
        "$json = [Console]::In.ReadToEnd(); "
        f"$json | Test-Json -SchemaFile '{schema_path}' "
        "-ErrorAction SilentlyContinue"
    )
    completed = subprocess.run(
        ["pwsh", "-NoProfile", "-Command", command],
        input=json.dumps(value, ensure_ascii=False),
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )
    return completed.returncode == 0 and completed.stdout.strip().endswith("True")


class GraphEvolutionContractV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = load_json(CANONICAL / "contract.json")
        cls.schemas = {
            name.removesuffix(".schema.json"): load_json(CANONICAL / name)
            for name in RESOURCE_NAMES
            if name.endswith(".schema.json")
        }

    def test_exact_resource_manifest_and_byte_identical_packaged_mirrors(self):
        self.assertEqual(set(RESOURCE_NAMES), {path.name for path in CANONICAL.iterdir()})
        self.assertEqual(set(RESOURCE_NAMES), {path.name for path in PACKAGED.iterdir()})
        self.assertEqual(
            set(RESOURCE_NAMES) - {"contract.json"},
            {entry["resource"] for entry in self.manifest["resources"].values()},
        )
        for name in RESOURCE_NAMES:
            canonical = CANONICAL / name
            packaged = PACKAGED / name
            self.assertEqual(canonical.read_bytes(), packaged.read_bytes(), name)
            if name == "contract.json":
                continue
            entry = next(
                item
                for item in self.manifest["resources"].values()
                if item["resource"] == name
            )
            self.assertEqual(canonical_resource_sha256(canonical), entry["canonical_sha256"])

    def test_dependencies_reuse_stage5_digest_and_graph_owner(self):
        dependencies = self.manifest["dependencies"]
        lineage_path = REPOSITORY / "docs/contracts/evidence-lineage/v1/contract.json"
        graph_contract = REPOSITORY / "docs/contracts/graph/v1/contract.json"
        graph_schema = REPOSITORY / "docs/contracts/graph/v1/graph.schema.json"
        self.assertEqual(
            canonical_resource_sha256(lineage_path),
            dependencies["evidence_lineage_contract_v1"]["canonical_sha256"],
        )
        self.assertEqual(
            STAGE5_LINEAGE_CONTRACT_SHA256,
            dependencies["evidence_lineage_contract_v1"]["canonical_sha256"],
        )
        self.assertEqual(
            canonical_resource_sha256(graph_contract),
            dependencies["graph_contract_v1"]["canonical_sha256"],
        )
        self.assertEqual(
            canonical_resource_sha256(graph_schema),
            dependencies["graph_schema_v1"]["canonical_sha256"],
        )
        self.assertIn("validate_graph_contract", dependencies["graph_contract_v1"]["relation"])
        self.assertIn("does not redefine", dependencies["graph_contract_v1"]["relation"])

    def test_six_operations_and_closed_preauthorization_allowlists_are_frozen(self):
        self.assertEqual(OPERATIONS, set(GRAPH_EVOLUTION_OPERATIONS))
        request_schema = self.schemas["request"]
        self.assertEqual(
            OPERATIONS,
            set(request_schema["$defs"]["operation"]["enum"]),
        )
        preauth = self.schemas["preauthorization"]
        self.assertEqual(
            OPERATIONS,
            set(preauth["properties"]["allowed_operations"]["items"]["enum"]),
        )
        self.assertEqual(
            CHANGE_CLASSES,
            set(preauth["properties"]["allowed_change_classes"]["items"]["enum"]),
        )
        self.assertEqual(
            PERMISSIONS,
            set(preauth["properties"]["allowed_permissions"]["items"]["enum"]),
        )
        self.assertFalse(preauth["additionalProperties"])
        self.assertFalse(preauth["properties"]["generation_budget"]["additionalProperties"])
        self.assertFalse(preauth["properties"]["evaluator"]["additionalProperties"])
        self.assertEqual(
            OPERATIONS,
            set(preauth["properties"]["operation_budgets"]["properties"]),
        )
        self.assertFalse(
            preauth["properties"]["operation_budgets"]["additionalProperties"]
        )

    def test_valid_documents_have_domain_separated_canonical_digests(self):
        values = {
            "request": request(),
            "preauthorization": preauthorization(),
            "proposal": proposal(),
            "acceptance": acceptance(),
            "result": result(),
            "error": error(),
        }
        validators = {
            "request": validate_graph_evolution_request,
            "preauthorization": validate_graph_evolution_preauthorization,
            "proposal": validate_graph_evolution_proposal,
            "acceptance": validate_graph_evolution_acceptance,
            "result": validate_graph_evolution_result,
            "error": validate_graph_evolution_error,
        }
        digests = set()
        for kind, value in values.items():
            with self.subTest(kind=kind):
                validation = validators[kind](value)
                self.assertTrue(validation.valid, validation.issues)
                expected = hashlib.sha256(
                    DOMAINS[kind] + canonical_bytes(value)
                ).hexdigest()
                self.assertEqual(expected, validation.digest)
                self.assertEqual(
                    expected,
                    canonical_graph_evolution_digest(kind, value),
                )
                self.assertEqual(
                    expected,
                    canonical_graph_evolution_digest(value),
                )
                self.assertTrue(
                    validate_graph_evolution_document(kind, value).valid
                )
                digests.add(expected)
        self.assertEqual(len(values), len(digests))

    def test_manifest_fixed_vector_matches_independent_request_digest(self):
        vector = self.manifest["canonical_digest"]["fixed_vectors"][0]
        self.assertEqual("request-001", vector["vector_id"])
        self.assertEqual(request(), vector["document"])
        expected = hashlib.sha256(
            DOMAINS["request"] + canonical_bytes(vector["document"])
        ).hexdigest()
        self.assertEqual(expected, vector["expected_sha256"])
        self.assertEqual(
            expected,
            canonical_graph_evolution_digest("request", vector["document"]),
        )

    def test_no_change_has_no_target_graph_or_generation(self):
        no_change = proposal("NO_CHANGE")
        self.assertTrue(validate_graph_evolution_proposal(no_change).valid)
        for forbidden in ("target_generation", "target_graph", "target_graph_digest"):
            self.assertNotIn(forbidden, no_change)
            invalid = copy.deepcopy(no_change)
            invalid[forbidden] = (
                minimal_graph() if forbidden == "target_graph" else 8
            )
            if forbidden == "target_graph_digest":
                invalid[forbidden] = "c" * 64
            self.assertFalse(validate_graph_evolution_proposal(invalid).valid)
        no_change_result = result("NO_CHANGE", "NO_CHANGE")
        self.assertTrue(validate_graph_evolution_result(no_change_result).valid)
        self.assertNotIn("target_generation", no_change_result)
        self.assertNotIn("target_graph_digest", no_change_result)

    def test_changed_proposal_requires_graph_owner_binding(self):
        value = proposal()
        self.assertTrue(validate_graph_evolution_proposal(value).valid)
        invalid_graph = copy.deepcopy(value)
        invalid_graph["target_graph"]["nodes"][0]["permission"] = "ROOT"
        validation = validate_graph_evolution_proposal(invalid_graph)
        self.assertFalse(validation.valid)
        self.assertIn("GRAPH_INVALID", {issue.issue_code for issue in validation.issues})
        wrong_digest = copy.deepcopy(value)
        wrong_digest["target_graph_digest"] = "f" * 64
        self.assertFalse(validate_graph_evolution_proposal(wrong_digest).valid)
        wrong_generation = copy.deepcopy(value)
        wrong_generation["target_generation"] = 9
        self.assertFalse(validate_graph_evolution_proposal(wrong_generation).valid)

    def test_strict_unknown_fields_duplicate_json_names_and_invalid_kind_fail(self):
        for validator, value in (
            (validate_graph_evolution_request, request()),
            (validate_graph_evolution_preauthorization, preauthorization()),
            (validate_graph_evolution_proposal, proposal()),
            (validate_graph_evolution_acceptance, acceptance()),
            (validate_graph_evolution_result, result()),
            (validate_graph_evolution_error, error()),
        ):
            invalid = copy.deepcopy(value)
            invalid["unexpected"] = True
            self.assertFalse(validator(invalid).valid)
        duplicate = (
            '{"schema_id":"urn:sagekit:graph-evolution:v1:request",'
            '"schema_id":"urn:sagekit:graph-evolution:v1:request"}'
        )
        self.assertFalse(validate_graph_evolution_request(duplicate).valid)
        with self.assertRaises(GraphEvolutionContractError):
            canonical_graph_evolution_digest("bogus", request())

    def test_malformed_enum_types_return_issues_without_raising(self):
        cases = []
        invalid_request = request()
        invalid_request["operation"] = []
        cases.append((validate_graph_evolution_request, invalid_request))
        invalid_proposer = request()
        invalid_proposer["proposer"]["permission"] = {}
        cases.append((validate_graph_evolution_request, invalid_proposer))
        invalid_preauth = preauthorization()
        invalid_preauth["evaluator"]["permission"] = []
        cases.append(
            (validate_graph_evolution_preauthorization, invalid_preauth)
        )
        invalid_acceptance = acceptance()
        invalid_acceptance["decision"] = {}
        cases.append((validate_graph_evolution_acceptance, invalid_acceptance))
        invalid_result = result()
        invalid_result["message_code"] = []
        cases.append((validate_graph_evolution_result, invalid_result))
        invalid_error = error()
        invalid_error["error_code"] = {}
        cases.append((validate_graph_evolution_error, invalid_error))
        for validator, value in cases:
            self.assertFalse(validator(value).valid)

    def test_preauthorization_is_bounded_and_fail_closed(self):
        self.assertTrue(
            validate_graph_evolution_preauthorization(preauthorization()).valid
        )
        cases = []
        duplicate_operation = preauthorization()
        duplicate_operation["allowed_operations"].append("NO_CHANGE")
        cases.append(duplicate_operation)
        unknown_budget = preauthorization()
        unknown_budget["operation_budgets"]["ROOT"] = 1
        cases.append(unknown_budget)
        unlisted_budget = preauthorization()
        unlisted_budget["allowed_operations"] = ["NO_CHANGE"]
        cases.append(unlisted_budget)
        invalid_role = preauthorization()
        invalid_role["authority"]["authority_role"] = "WORKER"
        cases.append(invalid_role)
        non_independent = preauthorization()
        non_independent["evaluator"]["independent"] = False
        cases.append(non_independent)
        for value in cases:
            self.assertFalse(
                validate_graph_evolution_preauthorization(value).valid,
                value,
            )

    def test_malformed_nested_allowlists_and_byte_overflow_return_issues(self):
        malformed = preauthorization()
        malformed["allowed_node_ids"] = None
        malformed["allowed_roles"] = None
        malformed["allowed_permissions"] = None
        validation = validate_graph_evolution_preauthorization(malformed)
        self.assertFalse(validation.valid)
        self.assertTrue(validation.issues)

        oversized = request()
        oversized["request_id"] = "x" * (1024 * 1024)
        validation = validate_graph_evolution_request(oversized)
        self.assertFalse(validation.valid)
        self.assertEqual(
            {"DOCUMENT_BYTE_BUDGET_EXCEEDED"},
            {issue.issue_code for issue in validation.issues},
        )

    def test_references_and_paths_reject_uri_absolute_and_newline_values(self):
        invalid_values = (
            "https://example.invalid/evidence",
            "SSH://example.invalid/evidence",
            "git+ssh://example.invalid/evidence",
            "file:///tmp/secret",
            "/etc/passwd",
            "\\\\server\\share",
            "C:\\secret.txt",
            "evidence/ok\nsecret",
        )
        for value in invalid_values:
            invalid_ref = request()
            invalid_ref["evidence_refs"] = [value]
            self.assertFalse(validate_graph_evolution_request(invalid_ref).valid)
            invalid_path = request()
            invalid_path["affected_paths"] = [value]
            self.assertFalse(validate_graph_evolution_request(invalid_path).valid)

    def test_privacy_forbidden_properties_are_absent_from_every_schema(self):
        for name, schema in self.schemas.items():
            property_names = {
                key
                for item in walk(schema)
                if isinstance(item, dict)
                for key in item.get("properties", {})
            }
            self.assertFalse(
                property_names.intersection(FORBIDDEN_PROPERTIES),
                (name, property_names.intersection(FORBIDDEN_PROPERTIES)),
            )
            self.assertIn("additionalProperties", schema)
            self.assertFalse(schema["additionalProperties"])

    def test_acceptance_is_evaluator_consistent_and_proposal_is_inert(self):
        accepted = acceptance()
        self.assertTrue(validate_graph_evolution_acceptance(accepted).valid)
        inconsistent = copy.deepcopy(accepted)
        inconsistent["evaluator"]["decision"] = "REJECT"
        self.assertFalse(validate_graph_evolution_acceptance(inconsistent).valid)
        boundaries = self.manifest["semantic_boundaries"]
        self.assertIn("does not grant", boundaries["proposal_inertness"])
        self.assertIn("does not execute", boundaries["proposal_inertness"])
        self.assertIn("host", boundaries["apply_ownership"])

    def test_result_and_error_are_exclusive(self):
        good_result = result()
        good_error = error()
        self.assertTrue(
            validate_graph_evolution_outcome(result=good_result).valid
        )
        self.assertTrue(
            validate_graph_evolution_outcome(error=good_error).valid
        )
        both = validate_graph_evolution_outcome(
            result=good_result,
            error=good_error,
        )
        neither = validate_graph_evolution_outcome()
        self.assertFalse(both.valid)
        self.assertFalse(neither.valid)
        self.assertEqual(
            {"RESULT_ERROR_EXCLUSIVITY"},
            {issue.issue_code for issue in both.issues},
        )
        self.assertEqual(
            {"RESULT_ERROR_EXCLUSIVITY"},
            {issue.issue_code for issue in neither.issues},
        )

    def test_result_operation_outcome_and_message_are_globally_bound(self):
        non_change_no_change = result("ADD_VERIFICATION", "NO_CHANGE")
        non_change_no_change["message_code"] = "NO_CHANGE_ACCEPTED"
        self.assertFalse(
            validate_graph_evolution_result(non_change_no_change).valid
        )
        unknown_message = result()
        unknown_message["message_code"] = "UNKNOWN_MESSAGE"
        self.assertFalse(validate_graph_evolution_result(unknown_message).valid)
        no_change_rejected = result("NO_CHANGE", "REJECTED")
        no_change_rejected["message_code"] = "EVOLUTION_REJECTED"
        self.assertTrue(validate_graph_evolution_result(no_change_rejected).valid)

    def test_preauthorization_requires_complete_fail_stop_set_and_zero_mutation_budget(self):
        for stop_condition in preauthorization()["stop_conditions"]:
            value = preauthorization()
            value["stop_conditions"].remove(stop_condition)
            self.assertFalse(
                validate_graph_evolution_preauthorization(value).valid,
                stop_condition,
            )

        exhausted = preauthorization()
        exhausted["generation_budget"]["remaining_generations"] = 0
        self.assertFalse(
            validate_graph_evolution_preauthorization(exhausted).valid
        )
        for operation in OPERATIONS - {"NO_CHANGE"}:
            exhausted["operation_budgets"][operation] = 0
            exhausted["allowed_operations"].remove(operation)
        self.assertTrue(
            validate_graph_evolution_preauthorization(exhausted).valid
        )
        self.assertGreater(exhausted["operation_budgets"]["NO_CHANGE"], 0)

    def test_opaque_identity_is_never_rejected_for_path_like_appearance(self):
        opaque_values = (
            "https://identity.example/pm",
            "/authority/private/path",
            r"C:\identity\node",
            "../identity/segment",
        )
        for opaque in opaque_values:
            value = request()
            value["graph_id"] = opaque
            value["authority"]["authority_id"] = opaque
            value["proposer"]["node_id"] = opaque
            value["node_id"] = opaque
            self.assertTrue(
                validate_graph_evolution_request(value).valid,
                opaque,
            )

    def test_paths_reject_empty_current_and_trailing_segments(self):
        for invalid_path in ("a//b", "./a", "a/./b", "a/", ".", ".."):
            value = request()
            value["affected_paths"] = [invalid_path]
            self.assertFalse(
                validate_graph_evolution_request(value).valid,
                invalid_path,
            )

    def test_error_issues_are_unique_and_use_uppercase_machine_codes(self):
        duplicate = error()
        duplicate["issues"].append(copy.deepcopy(duplicate["issues"][0]))
        self.assertFalse(validate_graph_evolution_error(duplicate).valid)
        for invalid_code in ("invalid_operation", "InvalidOperation", "_INVALID"):
            value = error()
            value["issues"][0]["issue_code"] = invalid_code
            self.assertFalse(
                validate_graph_evolution_error(value).valid,
                invalid_code,
            )

    def test_powershell_test_json_and_python_validation_have_real_parity_probes(self):
        validators = {
            "request": validate_graph_evolution_request,
            "preauthorization": validate_graph_evolution_preauthorization,
            "result": validate_graph_evolution_result,
            "error": validate_graph_evolution_error,
        }
        cases = []
        valid_opaque = request()
        valid_opaque["graph_id"] = "https://opaque.example/a/b"
        cases.append(("request", valid_opaque, True))
        for invalid_path in ("a//b", "./a", "a/"):
            value = request()
            value["affected_paths"] = [invalid_path]
            cases.append(("request", value, False))
        invalid_result = result("ADD_VERIFICATION", "NO_CHANGE")
        invalid_result["message_code"] = "NO_CHANGE_ACCEPTED"
        cases.append(("result", invalid_result, False))
        invalid_message = result()
        invalid_message["message_code"] = "NOT_A_MESSAGE"
        cases.append(("result", invalid_message, False))
        rejected_no_change = result("NO_CHANGE", "REJECTED")
        rejected_no_change["message_code"] = "EVOLUTION_REJECTED"
        cases.append(("result", rejected_no_change, True))
        duplicate_issue = error()
        duplicate_issue["issues"].append(copy.deepcopy(duplicate_issue["issues"][0]))
        cases.append(("error", duplicate_issue, False))
        lowercase_issue = error()
        lowercase_issue["issues"][0]["issue_code"] = "invalid_operation"
        cases.append(("error", lowercase_issue, False))
        long_location = error()
        long_location["issues"][0]["location"] = "$." + "a" * 511
        cases.append(("error", long_location, False))
        uri_reference = request()
        uri_reference["evidence_refs"] = ["Git+SSH://example.invalid/evidence"]
        cases.append(("request", uri_reference, False))
        missing_corrective_context = request("ADD_CORRECTIVE")
        cases.append(("request", missing_corrective_context, False))
        valid_corrective_context = request("ADD_CORRECTIVE")
        valid_corrective_context["reason_code"] = "OBSERVED_FAILURE"
        valid_corrective_context["finding_ref"] = "finding/review-001"
        valid_corrective_context["root_cause_ref"] = "root-cause/review-001"
        cases.append(("request", valid_corrective_context, True))
        incomplete_stops = preauthorization()
        incomplete_stops["stop_conditions"].pop()
        cases.append(("preauthorization", incomplete_stops, False))
        exhausted_mutation = preauthorization()
        exhausted_mutation["generation_budget"]["remaining_generations"] = 0
        cases.append(("preauthorization", exhausted_mutation, False))

        for kind, value, expected in cases:
            with self.subTest(kind=kind, value=value):
                python_valid = validators[kind](value).valid
                schema_valid = powershell_test_json(
                    CANONICAL / f"{kind}.schema.json",
                    value,
                )
                self.assertEqual(expected, python_valid)
                self.assertEqual(expected, schema_valid)
                self.assertEqual(python_valid, schema_valid)

    def test_valid_decision_chains_bind_all_documents_and_parent_graph(self):
        for operation in OPERATIONS:
            chain = operation_chain(operation)
            with self.subTest(operation=operation):
                validation = validate_decision_chain(*chain)
                self.assertTrue(validation.valid, validation.issues)

        rejected = operation_chain("ADD_VERIFICATION", "REJECTED")
        validation = validate_decision_chain(*rejected)
        self.assertTrue(validation.valid, validation.issues)
        rejected_no_change = operation_chain("NO_CHANGE", "REJECTED")
        validation = validate_decision_chain(*rejected_no_change)
        self.assertTrue(validation.valid, validation.issues)

    def test_decision_chain_recomputes_digests_and_binds_authority_scope_and_budget(self):
        mutators = (
            lambda chain: chain[2].__setitem__("request_digest", "f" * 64),
            lambda chain: chain[3]["authority"].__setitem__(
                "authority_id", "pm/other"
            ),
            lambda chain: chain[1]["allowed_roles"].remove("Controller"),
            lambda chain: chain[1]["allowed_permissions"].remove(
                "WRITE_AUTHORIZED"
            ),
            lambda chain: chain[1]["allowed_paths"].__setitem__(
                0, "unrelated/**"
            ),
            lambda chain: chain[1]["operation_budgets"].__setitem__(
                "ADD_VERIFICATION", 0
            ),
            lambda chain: chain[1]["generation_budget"].__setitem__(
                "remaining_generations", 0
            ),
            lambda chain: chain[5].__setitem__("generation", 6),
        )
        for mutate in mutators:
            chain = list(operation_chain("ADD_VERIFICATION"))
            mutate(chain)
            with self.subTest(mutate=mutate):
                self.assertFalse(validate_decision_chain(*chain).valid)

    def test_operation_specific_graph_deltas_fail_closed(self):
        cases = []

        corrective = list(operation_chain("ADD_CORRECTIVE"))
        corrective[2]["target_graph"]["nodes"][-1]["permission"] = "WRITE_AUTHORIZED"
        corrective[2]["target_graph_digest"] = canonical_graph_digest(
            corrective[2]["target_graph"]
        )
        cases.append(rebind_chain(corrective))

        verification = list(operation_chain("ADD_VERIFICATION"))
        verification[2]["target_graph"]["nodes"][-1][
            "permission"
        ] = "WRITE_AUTHORIZED"
        verification[2]["target_graph_digest"] = canonical_graph_digest(
            verification[2]["target_graph"]
        )
        cases.append(rebind_chain(verification))

        investigation = list(operation_chain("ADD_INVESTIGATION"))
        investigation[2]["target_graph"]["nodes"][-1][
            "classification"
        ] = "required"
        investigation[2]["target_graph_digest"] = canonical_graph_digest(
            investigation[2]["target_graph"]
        )
        cases.append(rebind_chain(investigation))

        split = list(operation_chain("SPLIT_PENDING"))
        split[2]["target_graph"]["nodes"][2]["verifier"] = "verifier/weaker"
        split[2]["target_graph_digest"] = canonical_graph_digest(
            split[2]["target_graph"]
        )
        cases.append(rebind_chain(split))

        disabled = list(operation_chain("DISABLE_OPTIONAL_PENDING"))
        disabled[5]["joins"].append(
            {
                "id": "join/optional-required",
                "requires": ["node/controller", "node/optional"],
                "policy": "required-plus-optional",
            }
        )
        cases.append(rebind_chain(disabled))

        changed_gate = list(operation_chain("ADD_VERIFICATION"))
        changed_gate[2]["target_graph"]["human_gates"].append("gate/other")
        changed_gate[2]["target_graph_digest"] = canonical_graph_digest(
            changed_gate[2]["target_graph"]
        )
        cases.append(rebind_chain(changed_gate))

        changed_completion = list(operation_chain("ADD_VERIFICATION"))
        changed_completion[2]["target_graph"][
            "completion_verifier"
        ] = "verifier/other"
        changed_completion[2]["target_graph_digest"] = canonical_graph_digest(
            changed_completion[2]["target_graph"]
        )
        cases.append(rebind_chain(changed_completion))

        for chain in cases:
            self.assertFalse(validate_decision_chain(*chain).valid)

    def test_split_pending_cannot_rewrite_or_enter_parent_human_gates(self):
        attacks = (
            ("add split to gate", lambda join: join["requires"].append("node/split-part")),
            ("reorder gate requirements", lambda join: join["requires"].reverse()),
        )
        for name, attack in attacks:
            chain = list(operation_chain("SPLIT_PENDING"))
            attack(chain[2]["target_graph"]["joins"][0])
            rebind_chain(chain)
            with self.subTest(attack=name):
                validation = validate_decision_chain(*chain)
                self.assertFalse(validation.valid, validation.issues)
                self.assertIn(
                    "PARENT_JOIN_CHANGED",
                    {issue.issue_code for issue in validation.issues},
                )

    def test_add_verification_rejects_optional_investigation_and_verifier_attacks(self):
        attacks = (
            (
                "optional node",
                lambda chain: chain[2]["target_graph"]["nodes"][-1].__setitem__(
                    "classification", "optional"
                ),
            ),
            (
                "investigator role",
                lambda chain: chain[2]["target_graph"]["nodes"][-1].__setitem__(
                    "role", "Investigator"
                ),
            ),
            (
                "investigation verifier",
                lambda chain: chain[2]["target_graph"]["nodes"][-1].__setitem__(
                    "verifier", "verifier/investigation"
                ),
            ),
            (
                "replace existing verifier",
                lambda chain: chain[2]["target_graph"]["nodes"][1].__setitem__(
                    "verifier", "verifier/replacement"
                ),
            ),
            (
                "downgrade existing verifier",
                lambda chain: chain[2]["target_graph"]["nodes"][1].__setitem__(
                    "classification", "optional"
                ),
            ),
        )
        for name, attack in attacks:
            chain = list(operation_chain("ADD_VERIFICATION"))
            attack(chain)
            rebind_chain(chain)
            with self.subTest(attack=name):
                self.assertFalse(validate_decision_chain(*chain).valid)

    def test_delta_hardening_preserves_all_six_legal_operations(self):
        self.assertEqual(6, len(OPERATIONS))
        for operation in sorted(OPERATIONS):
            with self.subTest(operation=operation):
                validation = validate_decision_chain(*operation_chain(operation))
                self.assertTrue(validation.valid, validation.issues)

    def test_chain_binds_parent_authority_proposer_and_evaluator_controls(self):
        authority_mismatch = list(operation_chain("ADD_VERIFICATION"))
        authority_mismatch[5]["source_authority"]["identity"] = "pm/other"

        proposer_mismatch = list(operation_chain("ADD_VERIFICATION"))
        proposer_mismatch[0]["proposer"]["role"] = "Verifier"
        proposer_mismatch[2]["proposer"]["role"] = "Verifier"

        evaluator_mismatch = list(operation_chain("ADD_VERIFICATION"))
        evaluator_mismatch[1]["evaluator"]["permission"] = "WRITE_AUTHORIZED"

        for chain in (
            rebind_chain(authority_mismatch),
            rebind_chain(proposer_mismatch),
            rebind_chain(evaluator_mismatch),
        ):
            self.assertFalse(validate_decision_chain(*chain).valid)

    def test_module_does_not_construct_or_apply_proposals(self):
        import sagekit.graph_evolution_contract as module

        public = set(module.__all__)
        self.assertFalse(
            {
                "build_proposal",
                "create_proposal",
                "apply_proposal",
                "execute_proposal",
                "schedule_proposal",
            }.intersection(public)
        )
        source = Path(module.__file__).read_text(encoding="utf-8").lower()
        for forbidden in (
            "subprocess",
            "sqlite",
            "scheduler",
            "stage7",
            "from .cli",
            "import cli",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
