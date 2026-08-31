"""Executable guardrails for the frozen ScopeLock agent plan."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.agent import root_agent
from app.sub_agents.requirement_analyzer import (
    PROMPT_VERSION as REQUIREMENT_PROMPT_VERSION,
    requirement_analyzer,
)
from app.sub_agents.scope_analyzer import (
    PROMPT_VERSION as SCOPE_PROMPT_VERSION,
    scope_analyzer,
)
from scopelock.domain.models import RequirementAnalysis, ScopeAnalysis
from scopelock.services.semantic_contracts import (
    SemanticContractViolation,
    validate_requirement_analysis,
)
from scopelock.services.sop_service import load_sop
from scopelock.testing.local_golden_path import load_local_golden_fixture


FORBIDDEN_AGENT_CAPABILITIES = {
    "approve",
    "create",
    "delete",
    "mutate",
    "price",
    "send",
    "timeline",
    "update",
    "write",
}


def _tool_names(agent) -> list[str]:
    return [getattr(tool, "__name__", type(tool).__name__) for tool in agent.tools]


def _schema_field_names(schema: object) -> set[str]:
    if isinstance(schema, dict):
        names = set(schema.get("properties", {}))
        for value in schema.values():
            names.update(_schema_field_names(value))
        return names
    if isinstance(schema, list):
        names: set[str] = set()
        for value in schema:
            names.update(_schema_field_names(value))
        return names
    return set()


def test_frozen_agent_roster_schemas_and_least_privilege_tools():
    assert root_agent.name == "scopelock"
    assert root_agent.tools == []
    assert [agent.name for agent in root_agent.sub_agents] == [
        "requirement_analyzer",
        "scope_analyzer",
    ]
    assert requirement_analyzer.output_schema is RequirementAnalysis
    assert scope_analyzer.output_schema is ScopeAnalysis
    assert _tool_names(requirement_analyzer) == ["get_sop_catalog"]
    assert _tool_names(scope_analyzer) == [
        "get_current_scope",
        "get_recent_thread_context",
        "get_sop_catalog",
    ]

    registered_tools = {
        name
        for agent in root_agent.sub_agents
        for name in _tool_names(agent)
    }
    assert not {
        fragment
        for fragment in FORBIDDEN_AGENT_CAPABILITIES
        if any(fragment in tool_name.casefold() for tool_name in registered_tools)
    }


def test_agent_prompts_keep_routing_tool_order_and_commerce_boundaries_explicit():
    assert REQUIREMENT_PROMPT_VERSION == "requirement_analyzer_v6"
    assert SCOPE_PROMPT_VERSION == "scope_analyzer_v4"
    assert "immediately transfer to requirement_analyzer" in root_agent.instruction
    assert "immediately\ntransfer to the scope_analyzer" in root_agent.instruction
    assert "Do not calculate price" in root_agent.instruction
    assert "or\nsend email" in root_agent.instruction

    requirement_prompt = requirement_analyzer.instruction
    assert "copied verbatim as one" in requirement_prompt
    assert "contiguous substring from BODY" in requirement_prompt
    assert "Always call get_sop_catalog before selecting" in requirement_prompt
    assert "semantic catalog only" in requirement_prompt
    assert "retain all supported mappings" in requirement_prompt
    assert "Decompose compound sentences into atomic requirements" in requirement_prompt
    assert "does not replace a primary workflow module" in requirement_prompt
    assert "Never calculate or promise a project total" in requirement_prompt
    assert "Never change project state or send email" in requirement_prompt
    assert "Return only RequirementAnalysis" in requirement_prompt

    scope_prompt = scope_analyzer.instruction
    required_order = [
        "1. get_current_scope(project_id)",
        "2. get_recent_thread_context(project_id)",
        "3. get_sop_catalog()",
    ]
    positions = [scope_prompt.index(value) for value in required_order]
    assert positions == sorted(positions)
    assert "one event for each independent client change" in scope_prompt
    assert "A coordinated noun list can contain multiple atomic changes" in scope_prompt
    assert "Coverage takes precedence" in scope_prompt
    assert "Never mutate state" in scope_prompt
    assert "or send email" in scope_prompt
    assert "Return only ScopeAnalysis" in scope_prompt


def test_agent_output_schemas_have_no_commercial_or_action_fields():
    forbidden_fragments = {
        "approval",
        "cost",
        "duration",
        "price",
        "send",
        "timeline",
        "total",
    }
    for model in (RequirementAnalysis, ScopeAnalysis):
        field_names = _schema_field_names(model.model_json_schema())
        violating_fields = {
            field
            for field in field_names
            if any(fragment in field.casefold() for fragment in forbidden_fragments)
        }
        assert violating_fields == set()


def test_reviewed_semantic_corpora_retain_safety_assertions():
    requirement_cases = json.loads(
        Path("tests/fixtures/requirement_analyzer_cases.json").read_text(
            encoding="utf-8"
        )
    )["cases"]
    scope_cases = json.loads(
        Path("tests/fixtures/scope_analyzer_cases.json").read_text(
            encoding="utf-8"
        )
    )["cases"]

    assert {case["category"] for case in requirement_cases}.issuperset({
        "golden_path",
        "irrelevant_email",
        "ambiguous_request",
        "out_of_catalog_request",
        "prompt_injection",
        "mixed_scope",
        "client_constraint",
        "thai_supported",
        "thai_ambiguous",
    })
    for case in requirement_cases:
        assertions = case["expected_assertions"]
        assert assertions["require_no_commerce_fields"] is True
        assert "send" in assertions["forbidden_tool_name_fragments"]
        assert "price" in assertions["forbidden_tool_name_fragments"]

    assert len(scope_cases) >= 35
    for case in scope_cases:
        assertions = case["expected_assertions"]
        assert assertions["require_evidence"] is True
        assert assertions["require_no_commerce_fields"] is True
        assert assertions["required_tool_order"] == [
            "get_current_scope",
            "get_recent_thread_context",
            "get_sop_catalog",
        ]


def test_requirement_semantic_contract_accepts_only_the_reviewed_safe_shape():
    email, analysis, _ = load_local_golden_fixture()
    catalog = load_sop("config/jvl_sop.example.yaml")
    valid_keys = {module.key for module in catalog.modules}

    validate_requirement_analysis(
        analysis,
        valid_module_keys=valid_keys,
        expected_message_id=email.message_id,
        normalized_message_body=email.body,
        expected_sop_version=catalog.version,
    )

    first = analysis.selected_sop_modules[0]
    unsafe_variants = [
        analysis.model_copy(
            update={
                "selected_sop_modules": [
                    first.model_copy(update={"evidence": []}),
                    *analysis.selected_sop_modules[1:],
                ]
            }
        ),
        analysis.model_copy(
            update={
                "selected_sop_modules": [
                    first.model_copy(update={"module_key": "invented_module"}),
                    *analysis.selected_sop_modules[1:],
                ]
            }
        ),
        analysis.model_copy(update={"objective": "Estimate the cost immediately."}),
        analysis.model_copy(
            update={
                "selected_sop_modules": [
                    *analysis.selected_sop_modules,
                    first,
                ]
            }
        ),
    ]

    for unsafe in unsafe_variants:
        with pytest.raises(SemanticContractViolation):
            validate_requirement_analysis(
                unsafe,
                valid_module_keys=valid_keys,
            )


@pytest.mark.parametrize("unsafe_kind", ["message_id", "gmail_quote", "sop_version"])
def test_requirement_evidence_is_bound_to_authoritative_sources(unsafe_kind):
    email, analysis, _ = load_local_golden_fixture()
    catalog = load_sop("config/jvl_sop.example.yaml")
    first = analysis.selected_sop_modules[0]
    evidence = list(first.evidence)
    if unsafe_kind == "message_id":
        evidence[0] = evidence[0].model_copy(update={"source_id": "other-message"})
    elif unsafe_kind == "gmail_quote":
        evidence[0] = evidence[0].model_copy(update={"quote_or_rule": "invented quote"})
    else:
        evidence[1] = evidence[1].model_copy(update={"source_version": "old-sop"})
    unsafe = analysis.model_copy(
        update={
            "selected_sop_modules": [
                first.model_copy(update={"evidence": evidence}),
                *analysis.selected_sop_modules[1:],
            ]
        }
    )

    with pytest.raises(SemanticContractViolation):
        validate_requirement_analysis(
            unsafe,
            valid_module_keys={module.key for module in catalog.modules},
            expected_message_id=email.message_id,
            normalized_message_body=email.body,
            expected_sop_version=catalog.version,
        )


def test_requirement_fixed_package_quantity_fails_closed():
    email, analysis, _ = load_local_golden_fixture()
    catalog = load_sop("config/jvl_sop.example.yaml")
    first = analysis.selected_sop_modules[0]
    unsafe = analysis.model_copy(
        update={
            "selected_sop_modules": [
                first.model_copy(update={"quantity": 2}),
                *analysis.selected_sop_modules[1:],
            ]
        }
    )

    with pytest.raises(SemanticContractViolation, match="quantity 2 is outside"):
        validate_requirement_analysis(
            unsafe,
            valid_module_keys={module.key for module in catalog.modules},
            expected_message_id=email.message_id,
            normalized_message_body=email.body,
            expected_sop_version=catalog.version,
            quantity_limits={
                module.key: (module.quantity.minimum, module.quantity.maximum)
                for module in catalog.modules
            },
        )
