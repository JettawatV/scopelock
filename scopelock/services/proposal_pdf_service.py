"""Deterministic client-facing PDF rendering for sealed commercial artifacts."""

from __future__ import annotations

from functools import partial
from html import escape
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from scopelock.domain.models import CommercialArtifact, ScopeVersion
from scopelock.domain.workflow_models import ProjectRecord


_INK = colors.HexColor("#17201D")
_MUTED = colors.HexColor("#5C6863")
_LINE = colors.HexColor("#D8DEDB")
_SURFACE = colors.HexColor("#F2F5F3")
_ACCENT = colors.HexColor("#D8F0E2")


def _humanize(value: str) -> str:
    return value.replace("_", " ").strip().title()


def _money(value: int, *, signed: bool = False) -> str:
    prefix = "+" if signed and value > 0 else ""
    return f"{prefix}USD {value:,}"


class _InvariantCanvas(canvas.Canvas):
    """ReportLab canvas with repeatable metadata and document identifiers."""

    def __init__(self, *args, **kwargs) -> None:
        kwargs["invariant"] = 1
        kwargs["pageCompression"] = 1
        super().__init__(*args, **kwargs)


def render_commercial_artifact_pdf(
    *,
    artifact: CommercialArtifact,
    project: ProjectRecord,
    proposed_scope: ScopeVersion,
    baseline_scope: ScopeVersion | None = None,
) -> bytes:
    """Render a sealed proposal or change order without invoking an LLM."""

    if artifact.project_id != project.id or proposed_scope.project_id != project.id:
        raise ValueError("Commercial PDF inputs must belong to one project")
    if proposed_scope.id != artifact.proposed_scope_version_id:
        raise ValueError("Commercial PDF scope does not match the sealed artifact")
    if artifact.baseline_scope_version_id:
        if baseline_scope is None or baseline_scope.id != artifact.baseline_scope_version_id:
            raise ValueError("Change order PDF requires the exact accepted baseline")

    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"ScopeLock {_humanize(artifact.artifact_type.value)}",
        author="ScopeLock",
        subject="Approval-gated commercial scope",
    )
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="ScopeLockTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=25,
            leading=29,
            textColor=_INK,
            spaceAfter=4 * mm,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ScopeLockHeading",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            textColor=_INK,
            spaceBefore=5 * mm,
            spaceAfter=2.5 * mm,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ScopeLockBody",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=14,
            textColor=_INK,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ScopeLockSmall",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=10,
            textColor=_MUTED,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ScopeLockAmount",
            parent=styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            alignment=TA_RIGHT,
            textColor=_INK,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ScopeLockTableHeader",
            parent=styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=10,
            textColor=colors.white,
        )
    )

    label = _humanize(artifact.artifact_type.value)
    reference = f"Version {artifact.version_number}"
    if artifact.change_order_number is not None:
        reference = f"Change order {artifact.change_order_number} - {reference}"

    story = [
        Paragraph("ScopeLock", styles["ScopeLockSmall"]),
        Paragraph(escape(label), styles["ScopeLockTitle"]),
        Paragraph(escape(project.title), styles["Heading2"]),
        Spacer(1, 2 * mm),
        Table(
            [
                ["Prepared for", escape(project.client_name)],
                ["Client email", escape(project.client_email)],
                ["Document", escape(reference)],
                ["SOP version", escape(artifact.sop_version)],
                ["Prepared", artifact.created_at.date().isoformat()],
            ],
            colWidths=[34 * mm, 122 * mm],
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), _SURFACE),
                    ("TEXTCOLOR", (0, 0), (0, -1), _MUTED),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                    ("GRID", (0, 0), (-1, -1), 0.5, _LINE),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 7),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            ),
        ),
        Paragraph("Commercial summary", styles["ScopeLockHeading"]),
    ]

    summary_rows = [
        ["Proposed total", _money(artifact.pricing_result.total_usd)],
        ["Delivery timeline", f"{artifact.timeline_result.total_days} days"],
    ]
    if baseline_scope is not None:
        summary_rows.extend(
            [
                [
                    "Price change",
                    _money(
                        artifact.pricing_result.total_usd
                        - baseline_scope.total_price_usd,
                        signed=True,
                    ),
                ],
                [
                    "Timeline change",
                    f"{artifact.timeline_result.total_days - baseline_scope.timeline_days:+d} days",
                ],
            ]
        )
    story.append(
        Table(
            summary_rows,
            colWidths=[78 * mm, 78 * mm],
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), _ACCENT),
                    ("TEXTCOLOR", (0, 0), (-1, -1), _INK),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("BOX", (0, 0), (-1, -1), 0.7, _INK),
                    ("INNERGRID", (0, 0), (-1, -1), 0.4, _LINE),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            ),
        )
    )

    story.append(Paragraph("Scope and deliverables", styles["ScopeLockHeading"]))
    for requirement in proposed_scope.requirements:
        story.append(
            KeepTogether(
                [
                    Paragraph(
                        f"<b>{escape(requirement.requirement_id)} - "
                        f"{escape(requirement.category)}</b>",
                        styles["ScopeLockBody"],
                    ),
                    Paragraph(escape(requirement.description), styles["ScopeLockBody"]),
                    Spacer(1, 1.5 * mm),
                ]
            )
        )

    story.append(Paragraph("Deterministic pricing", styles["ScopeLockHeading"]))
    price_rows: list[list[object]] = [
        [
            Paragraph("Module", styles["ScopeLockTableHeader"]),
            Paragraph("Qty", styles["ScopeLockTableHeader"]),
            Paragraph("Rule", styles["ScopeLockTableHeader"]),
            Paragraph("Amount", styles["ScopeLockTableHeader"]),
        ]
    ]
    for line in artifact.pricing_result.line_items:
        price_rows.append(
            [
                Paragraph(escape(_humanize(line.module_key)), styles["ScopeLockBody"]),
                str(line.quantity),
                escape(_humanize(line.unit_rule)),
                Paragraph(_money(line.subtotal_usd), styles["ScopeLockAmount"]),
            ]
        )
    price_rows.append(
        [
            Paragraph("<b>Total</b>", styles["ScopeLockBody"]),
            "",
            "",
            Paragraph(_money(artifact.pricing_result.total_usd), styles["ScopeLockAmount"]),
        ]
    )
    story.append(
        Table(
            price_rows,
            colWidths=[72 * mm, 15 * mm, 32 * mm, 37 * mm],
            repeatRows=1,
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), _INK),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("BACKGROUND", (0, -1), (-1, -1), _SURFACE),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 1), (-1, -1), 8.5),
                    ("GRID", (0, 0), (-1, -1), 0.5, _LINE),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (1, 1), (1, -1), "CENTER"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            ),
        )
    )

    if proposed_scope.assumptions:
        story.append(Paragraph("Assumptions", styles["ScopeLockHeading"]))
        for item in proposed_scope.assumptions:
            story.append(Paragraph(f"- {escape(item)}", styles["ScopeLockBody"]))
    if proposed_scope.exclusions:
        story.append(Paragraph("Exclusions", styles["ScopeLockHeading"]))
        for item in proposed_scope.exclusions:
            story.append(Paragraph(f"- {escape(item)}", styles["ScopeLockBody"]))

    story.extend(
        [
            Paragraph("Change control", styles["ScopeLockHeading"]),
            Paragraph(
                "Price and timeline are calculated from the named SOP version. "
                "Any later scope expansion, reduction, or replacement requires a "
                "separate reviewed revision or change order before commercial communication.",
                styles["ScopeLockBody"],
            ),
            Spacer(1, 5 * mm),
            HRFlowable(width="100%", thickness=0.6, color=_LINE),
            Spacer(1, 2 * mm),
            Paragraph(
                f"Artifact {escape(artifact.id)} - checksum "
                f"{escape(artifact.checksum or 'unsealed')}",
                styles["ScopeLockSmall"],
            ),
        ]
    )

    document.build(story, canvasmaker=partial(_InvariantCanvas))
    return buffer.getvalue()
