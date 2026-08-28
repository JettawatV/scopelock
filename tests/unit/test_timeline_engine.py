from pathlib import Path

import pytest

from scopelock.domain.models import ModuleQuantity
from scopelock.services.sop_service import load_sop
from scopelock.services.timeline_engine import (
    InvalidTimelineQuantityError,
    MissingTimelineDependencyError,
    TimelineEngine,
    TimelineInputError,
    UnknownTimelineModuleError,
)


SOP_PATH = Path("config/jvl_sop.example.yaml")


def selection(module_key: str, quantity: int = 1) -> ModuleQuantity:
    return ModuleQuantity(module_key=module_key, quantity=quantity)


def test_golden_modules_use_largest_base_and_parallel_modules_add_zero():
    engine = TimelineEngine(load_sop(SOP_PATH))

    result = engine.calculate(
        [
            selection("core_workflow_automation"),
            selection("email_intake"),
            selection("operations_dashboard"),
            selection("email_notifications"),
        ]
    )

    assert result.sop_version == "jvl-demo-v1"
    assert result.base_module_key == "core_workflow_automation"
    assert result.total_days == 5
    assert sum(item.incremental_days for item in result.line_items) == 5
    assert {
        item.module_key: item.incremental_days for item in result.line_items
    } == {
        "core_workflow_automation": 5,
        "email_intake": 0,
        "email_notifications": 0,
        "operations_dashboard": 0,
    }


def test_non_parallel_expansion_adds_five_days_in_dependency_order():
    engine = TimelineEngine(load_sop(SOP_PATH))

    result = engine.calculate(
        [selection("line_approval"), selection("line_notifications")]
    )

    assert result.total_days == 5
    assert [item.module_key for item in result.line_items] == [
        "line_notifications",
        "line_approval",
    ]
    assert [item.incremental_days for item in result.line_items] == [3, 2]


def test_full_golden_scope_plus_line_expansion_is_ten_days():
    engine = TimelineEngine(load_sop(SOP_PATH))
    result = engine.calculate(
        [
            selection("core_workflow_automation"),
            selection("email_intake"),
            selection("operations_dashboard"),
            selection("email_notifications"),
            selection("line_notifications"),
            selection("line_approval"),
        ]
    )

    assert result.total_days == 10


def test_all_parallel_modules_use_only_the_longest_base_duration():
    engine = TimelineEngine(load_sop(SOP_PATH))

    result = engine.calculate(
        [selection("email_intake"), selection("operations_dashboard")]
    )

    assert result.base_module_key == "operations_dashboard"
    assert result.total_days == 3


def test_timeline_result_is_independent_of_selection_order():
    engine = TimelineEngine(load_sop(SOP_PATH))
    forward = [
        selection("line_notifications"),
        selection("line_approval"),
        selection("core_workflow_automation"),
    ]

    assert engine.calculate(forward) == engine.calculate(list(reversed(forward)))


def test_missing_dependency_and_invalid_inputs_fail_safely():
    engine = TimelineEngine(load_sop(SOP_PATH))

    with pytest.raises(MissingTimelineDependencyError, match="line_notifications"):
        engine.calculate([selection("line_approval")])
    with pytest.raises(UnknownTimelineModuleError):
        engine.calculate([selection("unknown_module")])
    with pytest.raises(InvalidTimelineQuantityError):
        engine.calculate([selection("email_intake", 2)])
    with pytest.raises(TimelineInputError):
        engine.calculate([{"module_key": "email_intake", "quantity": 1}])


def test_empty_selection_has_zero_duration_and_no_base_module():
    result = TimelineEngine(load_sop(SOP_PATH)).calculate([])

    assert result.total_days == 0
    assert result.base_module_key is None
    assert result.line_items == ()
