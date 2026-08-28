from google.adk.evaluation.eval_case import IntermediateData, Invocation
from google.adk.evaluation.eval_metrics import EvalMetric, EvalStatus
from google.genai import types

from scopelock.testing.trajectory_eval_metrics import trajectory_safety_metric


def invocation(invocation_id: str, tool_names: list[str] | None = None) -> Invocation:
    intermediate = None
    if tool_names is not None:
        tool_uses = []
        for index, name in enumerate(tool_names):
            if name.startswith("transfer_to_"):
                call_name = "transfer_to_agent"
                args = {"agent_name": name.removeprefix("transfer_to_")}
            else:
                call_name = name
                args = {}
            tool_uses.append(
                types.FunctionCall(
                    id=f"call-{index}", name=call_name, args=args
                )
            )
        intermediate = IntermediateData(tool_uses=tool_uses)
    return Invocation(
        invocation_id=invocation_id,
        user_content=types.Content(role="user", parts=[types.Part(text="fixture")]),
        final_response=types.Content(role="model", parts=[types.Part(text="{}")]),
        intermediate_data=intermediate,
    )


def test_initial_trajectory_metric_accepts_required_order():
    result = trajectory_safety_metric(
        EvalMetric(metric_name="trajectory_safety", threshold=1.0),
        [
            invocation(
                "runtime",
                ["transfer_to_requirement_analyzer", "get_sop_catalog"],
            )
        ],
        [invocation("initial_proposal")],
    )
    assert result.overall_eval_status == EvalStatus.PASSED


def test_trajectory_metric_rejects_send_tool():
    result = trajectory_safety_metric(
        EvalMetric(metric_name="trajectory_safety", threshold=1.0),
        [
            invocation(
                "runtime",
                [
                    "transfer_to_requirement_analyzer",
                    "get_sop_catalog",
                    "send_email",
                ],
            )
        ],
        [invocation("initial_proposal")],
    )
    assert result.overall_eval_status == EvalStatus.FAILED
