"""Local, non-UI commands for repeatable ScopeLock development rehearsals."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scopelock.repositories.in_memory import InMemoryApplicationRepository
from scopelock.services.initial_proposal_workflow import InitialProposalWorkflow
from scopelock.services.golden_path_rehearsal import GoldenPathRehearsal
from scopelock.services.sop_service import load_sop
from scopelock.testing.local_golden_path import load_local_golden_fixture


def _initial_proposal(args: argparse.Namespace) -> int:
    email, analysis, _ = load_local_golden_fixture(args.fixture)
    repository = InMemoryApplicationRepository(clock=lambda: email.received_at)
    workflow = InitialProposalWorkflow(
        catalog=load_sop(args.sop),
        repository=repository,
        analyzer=lambda _: analysis,
        artifact_root=args.output,
    )
    result = None
    for _ in range(args.repeat):
        result = workflow.run(email)
    assert result is not None
    print(
        json.dumps(
            {
                "command": "initial-proposal",
                "repeat_count": args.repeat,
                "replayed": result.replayed,
                "project_id": result.project.id,
                "project_status": result.project.lifecycle_status.value,
                "artifact_id": result.artifact.id,
                "artifact_status": result.artifact.status.value,
                "scope_version_id": result.scope_version_id,
                "currency": result.proposal.currency,
                "total_usd": result.proposal.total_usd,
                "timeline_days": result.proposal.timeline.total_days,
                "proposal_checksum": result.rendered_proposal.content_checksum,
                "proposal_data_path": result.rendered_proposal.proposal_data_path,
                "proposal_markdown_path": result.rendered_proposal.proposal_markdown_path,
                "agent_runs": len(repository.list(collection="agent_runs")),
                "tool_actions": len(repository.list(collection="tool_actions")),
                "scope_decisions": len(repository.list(collection="scope_decisions")),
                "artifacts": len(repository.list(collection="artifacts")),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _golden_path(args: argparse.Namespace) -> int:
    email, analysis, followups = load_local_golden_fixture(args.fixture)
    repository = InMemoryApplicationRepository(clock=lambda: email.received_at)
    result = GoldenPathRehearsal(
        catalog=load_sop(args.sop),
        repository=repository,
        artifact_root=args.output,
    ).run(email=email, analysis=analysis, followups=followups)
    print(
        json.dumps(
            {
                "command": "golden-path",
                "demo_mode": result.demo_mode,
                "final_project_status": result.final_project.lifecycle_status.value,
                "baseline_total_usd": result.accepted_baseline.total_price_usd,
                "baseline_timeline_days": result.accepted_baseline.timeline_days,
                "price_delta_usd": result.finalized_buffer.net_price_delta_usd,
                "timeline_delta_days": result.finalized_buffer.net_timeline_delta_days,
                "proposed_total_usd": result.proposed_change_scope.total_price_usd,
                "scope_event_classifications": [
                    event.classification.value for event in result.scope_events
                ],
                "artifact_types": [
                    artifact.artifact_type.value for artifact in result.artifacts
                ],
                "approvals": len(result.approvals),
                "send_intents": len(result.send_intents),
                "elapsed_seconds": round(result.elapsed_seconds, 6),
                "collections": {
                    collection: len(repository.list(collection=collection))
                    for collection in (
                        "projects",
                        "scope_versions",
                        "scope_events",
                        "buffers",
                        "artifacts",
                        "approvals",
                        "sends",
                    )
                },
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="scopelock-local")
    subcommands = parser.add_subparsers(dest="command", required=True)
    initial = subcommands.add_parser(
        "initial-proposal",
        help="Turn the reviewed golden email into a proposal awaiting approval.",
    )
    initial.add_argument(
        "--fixture",
        type=Path,
        default=Path("tests/fixtures/local_golden_path.json"),
    )
    initial.add_argument(
        "--sop", type=Path, default=Path("config/jvl_sop.example.yaml")
    )
    initial.add_argument(
        "--output", type=Path, default=Path("artifacts/local_workflow")
    )
    initial.add_argument("--repeat", type=int, default=1, choices=range(1, 11))
    initial.set_defaults(handler=_initial_proposal)

    golden = subcommands.add_parser(
        "golden-path",
        help="Rehearse the complete post-acceptance change-order demo locally.",
    )
    golden.add_argument(
        "--fixture",
        type=Path,
        default=Path("tests/fixtures/local_golden_path.json"),
    )
    golden.add_argument(
        "--sop", type=Path, default=Path("config/jvl_sop.example.yaml")
    )
    golden.add_argument(
        "--output", type=Path, default=Path("artifacts/local_workflow")
    )
    golden.set_defaults(handler=_golden_path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
