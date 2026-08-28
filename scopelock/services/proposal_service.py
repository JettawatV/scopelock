"""Deterministic proposal payload composition and fixed-template rendering."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scopelock.domain.workflow_models import ProposalData, RenderedProposal


def canonical_proposal_bytes(proposal: ProposalData) -> bytes:
    payload = proposal.model_dump(mode="json")
    return (
        json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
        + "\n"
    ).encode("utf-8")


def proposal_content_checksum(proposal: ProposalData) -> str:
    return hashlib.sha256(canonical_proposal_bytes(proposal)).hexdigest()


def verify_rendered_proposal(rendered: RenderedProposal) -> bool:
    data = Path(rendered.proposal_data_path).read_bytes()
    return hashlib.sha256(data).hexdigest() == rendered.content_checksum


class ProposalRenderer:
    """Write exact proposal data plus a human-readable fixed Markdown template."""

    def __init__(self, output_root: str | Path) -> None:
        self._output_root = Path(output_root)

    def render(
        self,
        proposal: ProposalData,
        *,
        commercial_artifact_id: str,
        artifact_version: int,
    ) -> RenderedProposal:
        output_dir = self._output_root / proposal.project_id
        output_dir.mkdir(parents=True, exist_ok=True)
        stem = f"proposal-v{artifact_version}"
        data_path = output_dir / f"{stem}.json"
        markdown_path = output_dir / f"{stem}.md"

        data_bytes = canonical_proposal_bytes(proposal)
        checksum = hashlib.sha256(data_bytes).hexdigest()
        self._atomic_write(data_path, data_bytes)
        self._atomic_write(
            markdown_path,
            self._markdown(proposal, checksum).encode("utf-8"),
        )
        return RenderedProposal(
            commercial_artifact_id=commercial_artifact_id,
            proposal_data_path=str(data_path.resolve()),
            proposal_markdown_path=str(markdown_path.resolve()),
            content_checksum=checksum,
            source_scope_version_id=proposal.source_scope_version_id,
            source_scope_version_number=proposal.source_scope_version_number,
            sop_version=proposal.sop_version,
        )

    @staticmethod
    def _atomic_write(path: Path, content: bytes) -> None:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_bytes(content)
        temporary.replace(path)

    @staticmethod
    def _markdown(proposal: ProposalData, checksum: str) -> str:
        requirement_lines = "\n".join(
            f"- {item.requirement_id}: {item.description}"
            for item in proposal.requirements
        )
        line_item_lines = "\n".join(
            f"- {item.module_key} x{item.quantity}: "
            f"USD {item.subtotal_usd:,}"
            for item in proposal.line_items
        )
        assumption_lines = "\n".join(
            f"- {item}" for item in proposal.assumptions
        ) or "- None"
        exclusion_lines = "\n".join(
            f"- {item}" for item in proposal.exclusions
        ) or "- None"
        evidence_lines = "\n".join(
            f"- [{item.source_type}:{item.source_id}] {item.quote_or_rule}"
            for item in proposal.evidence
        ) or "- None"
        return f"""# Proposal — {proposal.project_title}

Client: {proposal.client_name} <{proposal.client_email}>

## Objective

{proposal.objective}

## Requirements

{requirement_lines}

## Scope and deterministic pricing

{line_item_lines}

**Total: USD {proposal.total_usd:,}**

**Timeline: {proposal.timeline.total_days} days**

## Assumptions

{assumption_lines}

## Exclusions

{exclusion_lines}

## Evidence

{evidence_lines}

## Change control

This proposal is valid for {proposal.validity_days} days. Any material scope
change requires a reviewed proposal revision or change order.

---
SOP version: {proposal.sop_version}  
Source scope version: {proposal.source_scope_version_number} ({proposal.source_scope_version_id})  
Proposal data SHA-256: {checksum}
"""
