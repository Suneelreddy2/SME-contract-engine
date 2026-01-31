"""Generate PDF report from analysis result for legal review."""
from typing import Dict, Any
from io import BytesIO


def build_analysis_pdf(result: Dict[str, Any]) -> bytes:
    """Build a PDF from the 10-part analysis result. Returns PDF bytes."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib import colors

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=inch, leftMargin=inch, topMargin=inch, bottomMargin=inch)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Small", fontSize=9, spaceAfter=6))
    story = []

    def add_heading(t: str):
        story.append(Paragraph(t, styles["Heading1"]))
        story.append(Spacer(1, 12))

    def add_para(t: str):
        story.append(Paragraph(t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"), styles["Normal"]))
        story.append(Spacer(1, 6))

    # 1. Contract type
    o = result.get("1_contract_type_and_overview", {})
    add_heading("1. Contract Type & Overview")
    add_para(f"<b>Type:</b> {o.get('contract_type', 'N/A')}")
    add_para(f"<b>Explanation:</b> {o.get('explanation', 'N/A')}")
    story.append(Spacer(1, 16))

    # 2. Risk score
    r7 = result.get("7_contract_risk_score_summary", {})
    add_heading("2. Contract Risk Score")
    add_para(f"<b>Composite score (0–100):</b> {r7.get('composite_risk_score_0_to_100', 0)} — {r7.get('interpretation', 'N/A')}")
    story.append(Spacer(1, 16))

    # 3. Entities
    e = result.get("3_entity_and_attribute_extraction", {})
    add_heading("3. Key Entities")
    add_para(f"<b>Parties:</b> {', '.join(e.get('parties', []) or ['Not detected'])}")
    add_para(f"<b>Governing law:</b> {e.get('jurisdiction_or_governing_law') or 'Not specified'}")
    add_para(f"<b>Duration:</b> {e.get('dates_and_duration', {}).get('duration_text') or 'Not specified'}")
    add_para(f"<b>Termination conditions:</b> {', '.join(e.get('termination_conditions', []) or ['Not extracted'])}")
    story.append(Spacer(1, 16))

    # 4. Clause-by-clause
    add_heading("4. Clause-by-Clause Explanation")
    for c in result.get("4_clause_by_clause_explanation_table", [])[:30]:
        story.append(Paragraph(f"<b>Clause {c.get('clause_number')}: {c.get('heading', '')[:60]}</b>", styles["Normal"]))
        story.append(Paragraph(f"Intent: {c.get('intent')} — {c.get('business_impact', '')[:200]}", styles["Small"]))
        story.append(Spacer(1, 4))
    story.append(Spacer(1, 16))

    # 5. Risk table
    add_heading("5. Risk Analysis")
    r5 = result.get("5_risk_analysis_and_flags", {})
    table_data = [["Clause", "Heading", "Risk", "Flags"]]
    for row in r5.get("clause_risk_table", [])[:25]:
        table_data.append([
            str(row.get("clause_number", "")),
            (row.get("heading") or "")[:40],
            row.get("risk_level", ""),
            ", ".join(row.get("flags", []))[:50],
        ])
    if len(table_data) > 1:
        t = Table(table_data, colWidths=[1.2 * inch, 2 * inch, 0.8 * inch, 2 * inch])
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.grey), ("FONTSIZE", (0, 0), (-1, -1), 8)]))
        story.append(t)
    story.append(Spacer(1, 12))
    for amb in r5.get("ambiguity_flags", [])[:10]:
        add_para(f"<i>Ambiguity:</i> \"{amb.get('phrase', '')}\" — {amb.get('reason', '')}")
    story.append(Spacer(1, 16))

    # 6. Renegotiation suggestions
    add_heading("6. Renegotiation Suggestions")
    for s in result.get("6_renegotiation_suggestions", [])[:15]:
        add_para(f"<b>Clause {s.get('clause_number')}:</b> {s.get('suggested_change', '')[:300]}")
    story.append(Spacer(1, 16))

    # 7. Executive summary
    add_heading("7. Executive Summary")
    ex = result.get("8_executive_business_summary", {})
    add_para(ex.get("overview", "")[:500])
    add_para("<b>Key obligations:</b>")
    for ob in ex.get("key_obligations_to_note", [])[:8]:
        add_para(f"• {ob[:200]}")
    add_para("<b>Biggest risks:</b>")
    for risk in ex.get("biggest_risks_in_simple_terms", [])[:5]:
        add_para(f"• {risk[:200]}")
    add_para("<b>What to negotiate:</b>")
    for neg in ex.get("what_to_negotiate_before_signing", [])[:5]:
        add_para(f"• {neg[:200]}")
    story.append(Spacer(1, 16))

    # 8. Best practices
    add_heading("8. SME Best Practices")
    bp = result.get("9_sme_template_and_best_practices", {})
    for rec in bp.get("recommendations", [])[:6]:
        add_para(f"• {rec}")
    for cl in bp.get("clauses_to_add_or_strengthen", [])[:4]:
        add_para(f"• {cl}")

    doc.build(story)
    return buffer.getvalue()
