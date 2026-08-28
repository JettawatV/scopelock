"""Create tracked Day 5 evidence from the latest complete native ADK result."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from scopelock.services.sop_service import load_sop
from scopelock.settings import PROJECT_ROOT, model_name
from scopelock.testing.scope_metrics import load_and_measure


HISTORY_DIR = PROJECT_ROOT / "app" / ".adk" / "eval_history"
FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "scope_analyzer_cases.json"
SOP_PATH = PROJECT_ROOT / "config" / "jvl_sop.example.yaml"
JSON_OUTPUT = PROJECT_ROOT / "docs" / "evidence" / "DAY_5_SCOPE_METRICS.json"
MARKDOWN_OUTPUT = PROJECT_ROOT / "docs" / "evidence" / "DAY_5_SCOPE_ANALYZER_EVIDENCE.md"


def latest_complete_result() -> Path:
    candidates = sorted(
        HISTORY_DIR.glob("app_scopelock_scope_analyzer_v1_*.evalset_result.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for path in candidates:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if len(payload.get("eval_case_results", [])) == 25:
            return path
    raise RuntimeError("No complete 25-case Scope Analyzer result exists")


def percentage(value: float) -> str:
    return f"{value * 100:.1f}%"


def render_report(result_path: Path, metrics: dict) -> str:
    fixture_payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    timestamp = datetime.now(timezone.utc).isoformat()
    lines = [
        "# Day 5 — Scope Analyzer evidence",
        "",
        f"Generated: `{timestamp}`",
        f"Model: `{model_name()}`",
        "Prompt: `scope_analyzer_v1`",
        f"Reviewed corpus: `tests/fixtures/scope_analyzer_cases.json` ({metrics['corpus_case_count']} cases)",
        f"Reviewer record: {fixture_payload['reviewer']}",
        f"Native ADK result: `app/.adk/eval_history/{result_path.name}` (local runtime evidence; ignored by Git)",
        "",
        "## Command",
        "",
        "```powershell",
        ".\\.venv313\\Scripts\\adk.exe eval app tests\\eval\\scope_analyzer.evalset.json --config_file_path tests\\eval\\scope_analyzer.config.json",
        "```",
        "",
        "## Measured result",
        "",
        f"- Exact classification-set accuracy: **{metrics['exact_match_cases']}/{metrics['corpus_case_count']} ({percentage(metrics['exact_match_accuracy'])})**.",
        f"- Expansion recall: **{percentage(metrics['expansion_recall'])}**.",
        f"- Invalid module rate: **{metrics['invalid_module_selections']}/{metrics['module_selections']} ({percentage(metrics['invalid_module_rate'])})**.",
        f"- Evidence coverage: **{metrics['evidence_obligations_satisfied']}/{metrics['evidence_obligations']} ({percentage(metrics['evidence_coverage'])})**.",
        f"- Strict malformed outputs: **{metrics['malformed_output_count']}**.",
        f"- Native `scope_contract` passes: **{metrics['native_contract_pass_count']}/{metrics['corpus_case_count']} ({percentage(metrics['native_contract_pass_rate'])})**.",
        "",
        "Evidence coverage counts a Gmail citation and accepted-scope citation for every event, plus one matching SOP citation for every selected module. Classification is multi-label because a message may contain a material event and CLOSURE.",
        "",
        "## Per-class precision and recall",
        "",
        "| Class | TP | FP | FN | Precision | Recall |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, values in metrics["per_class"].items():
        lines.append(
            f"| {label} | {values['true_positive']} | {values['false_positive']} | {values['false_negative']} | {percentage(values['precision'])} | {percentage(values['recall'])} |"
        )
    lines.extend(
        [
            "",
            "## Gate conclusion",
            "",
            (
                "DAY 5 PASS — all reviewed cases passed the strict native ADK contract, all reported metrics are calculated from the recorded corpus, and no unreviewed commercial action was permitted."
                if metrics["native_contract_pass_rate"] == 1.0
                else "DAY 5 BLOCKED — one or more reviewed cases failed the native ADK contract."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path)
    args = parser.parse_args()
    result_path = args.result or latest_complete_result()
    catalog = load_sop(SOP_PATH)
    metrics = load_and_measure(
        fixture_path=str(FIXTURE_PATH),
        eval_result_path=str(result_path),
        valid_module_keys={module.key for module in catalog.modules},
    )
    JSON_OUTPUT.write_text(
        json.dumps(metrics, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    MARKDOWN_OUTPUT.write_text(
        render_report(result_path, metrics),
        encoding="utf-8",
    )
    print(
        f"Measured {metrics['corpus_case_count']} cases: "
        f"accuracy={percentage(metrics['exact_match_accuracy'])}, "
        f"contract={percentage(metrics['native_contract_pass_rate'])}"
    )


if __name__ == "__main__":
    main()
