import io
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


def generate_credit_pdf(assessment_data: dict) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'DocTitle', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=22, leading=26,
        textColor=colors.HexColor('#0F172A')
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubtitle', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=10, leading=14,
        textColor=colors.HexColor('#7C3AED')
    )

    heading_style = ParagraphStyle(
        'Heading2', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=12, leading=16,
        textColor=colors.HexColor('#0F172A'), spaceBefore=8, spaceAfter=4
    )

    body_style = ParagraphStyle(
        'BodyText', parent=styles['Normal'],
        fontName='Helvetica', fontSize=9, leading=13,
        textColor=colors.HexColor('#334155')
    )

    badge_style = ParagraphStyle(
        'BadgeText', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=10, leading=14,
        textColor=colors.HexColor('#0F172A')
    )

    elements = []

    # 1. Header Banner
    elements.append(Paragraph("NOVA CREDIT RISK & WEALTH INTELLIGENCE", subtitle_style))
    elements.append(Paragraph("Nova Credit Intelligence Report", title_style))
    elements.append(Paragraph(f"Generated: {datetime.utcnow().strftime('%B %d, %Y - %H:%M UTC')} | Reference ID: {assessment_data.get('assessment_id', 'N/A')[:8]}", ParagraphStyle('Date', parent=body_style, textColor=colors.HexColor('#64748B'))))
    elements.append(Spacer(1, 8))
    elements.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#7C3AED'), spaceAfter=12))

    # 2. Executive Assessment Summary
    applicant_name = assessment_data.get("applicant_name", "Applicant")
    score_info = assessment_data.get("nova_score", {})
    nova_score = score_info.get("nova_score", 700)
    tier = score_info.get("tier", "Strong")
    decision_info = assessment_data.get("decision_engine", {})
    decision = decision_info.get("decision", "Likely Eligible")
    prob_pct = assessment_data.get("approval_percentage", 75.0)

    summary_data = [
        [Paragraph("<b>Applicant Legal Name:</b>", body_style), Paragraph(applicant_name, body_style), Paragraph("<b>Proprietary Nova Score:</b>", body_style), Paragraph(f"<b><font size=12 color='#7C3AED'>{nova_score} / 850</font></b>", badge_style)],
        [Paragraph("<b>Underwriting Decision:</b>", body_style), Paragraph(f"<b><font color='#0D9488'>{decision}</font></b>", badge_style), Paragraph("<b>Credit Risk Classification:</b>", body_style), Paragraph(tier, body_style)],
        [Paragraph("<b>Model Default Confidence:</b>", body_style), Paragraph(f"{score_info.get('confidence_percentage', 85)}% ({score_info.get('confidence_label', 'High')})", body_style), Paragraph("<b>Calibrated P(Good Credit):</b>", body_style), Paragraph(f"<b>{prob_pct}%</b>", body_style)],
        [Paragraph("<b>Fixed Obligation (FOIR):</b>", body_style), Paragraph(f"{decision_info.get('foir_ratio', 0.3)*100:.1f}%", body_style), Paragraph("<b>Affordability Standing:</b>", body_style), Paragraph(decision_info.get('affordability_tier', 'Good'), body_style)],
    ]

    summary_table = Table(summary_data, colWidths=[135, 135, 135, 135])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 10))

    # 3. Financial Affordability Matrix
    elements.append(Paragraph("1. Institutional Affordability & Capacity Analysis", heading_style))
    metrics_data = [
        ["Financial Ratio / Metric", "Assessed Value", "Policy Threshold", "Underwriting Status"],
        ["Fixed Obligation to Income (FOIR)", f"{decision_info.get('foir_ratio', 0.3)*100:.1f}%", "Max 50.0%", "Pass" if decision_info.get('foir_ratio', 0.3) <= 0.5 else "Fail"],
        ["Debt-to-Income Ratio (DTI)", f"{decision_info.get('dti_ratio', 0.2)*100:.1f}%", "Max 40.0%", "Pass" if decision_info.get('dti_ratio', 0.2) <= 0.4 else "Fail"],
        ["Monthly Disposable Income", f"₹{decision_info.get('disposable_income', 25000):,.0f}", "Min ₹15,000", "Pass" if decision_info.get('disposable_income', 25000) >= 15000 else "Fail"],
        ["Emergency Liquidity Buffer", f"{decision_info.get('liquidity_reserve_months', 4)} Months", "Min 3.0 Months", "Pass" if decision_info.get('liquidity_reserve_months', 4) >= 3 else "Warning"],
        ["Max Recommended EMI", f"₹{decision_info.get('max_recommended_emi', 25000):,.0f}", "50% Income Ceiling", "Suggested Cap"],
        ["Estimated Eligible Loan Capacity", f"₹{decision_info.get('suggested_loan_capacity', 500000):,.0f}", "Tenure Scaled", "Pre-qualified"],
    ]

    metrics_table = Table(metrics_data, colWidths=[180, 110, 130, 120])
    metrics_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0F172A')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    elements.append(metrics_table)
    elements.append(Spacer(1, 10))

    # 4. Multi-Tenure Loan Comparison
    loan_comp = decision_info.get("loan_tenure_comparison", [])
    if loan_comp:
        elements.append(Paragraph("2. Multi-Tenure Amortization & Cost Comparison", heading_style))
        tenure_rows = [["Tenure", "Monthly EMI", "Total Interest", "Total Repayment", "FOIR", "Recommendation"]]
        for t in loan_comp:
            tenure_rows.append([
                f"{t.get('tenure_months')} Mos ({t.get('tenure_years')} Yrs)",
                f"₹{t.get('monthly_emi'):,.0f}",
                f"₹{t.get('total_interest'):,.0f}",
                f"₹{t.get('total_cost'):,.0f}",
                f"{t.get('foir_percentage')}%",
                t.get('nova_recommendation', 'Feasible')
            ])
        comp_table = Table(tenure_rows, colWidths=[90, 90, 90, 100, 70, 100])
        comp_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#475569')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
            ('PADDING', (0,0), (-1,-1), 4),
        ]))
        elements.append(comp_table)
        elements.append(Spacer(1, 10))

    # 5. SHAP Drivers (Positive vs Risk)
    elements.append(Paragraph("3. Explainable Machine Learning Attribution (SHAP)", heading_style))
    pos_drivers = assessment_data.get("top_positive_drivers", [])
    risk_drivers = assessment_data.get("top_risk_drivers", [])
    
    driver_rows = [["Factor & Feature Attribution", "SHAP Value", "Risk Direction Impact"]]
    for d in pos_drivers[:3]:
        driver_rows.append([f"↑ {d.get('feature', '')}", f"+{abs(d.get('shap_value', 0)):.3f}", "Favorable Credit Vector"])
    for d in risk_drivers[:3]:
        driver_rows.append([f"↓ {d.get('feature', '')}", f"-{abs(d.get('shap_value', 0)):.3f}", "Risk Drag Vector"])

    driver_table = Table(driver_rows, colWidths=[240, 120, 180])
    driver_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0284C7')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('PADDING', (0,0), (-1,-1), 4),
    ]))
    elements.append(driver_table)
    elements.append(Spacer(1, 10))

    # 6. Actionable Credit Improvement Planner
    improvements = decision_info.get("improvement_recommendations", [])
    if improvements:
        elements.append(Paragraph("4. Recommended Credit Improvement Actions", heading_style))
        action_rows = [["Action Recommendation", "Category", "Simulated Score & Risk Impact"]]
        for a in improvements:
            action_rows.append([a.get("action", ""), a.get("category", ""), a.get("potential_impact", "")])
        act_table = Table(action_rows, colWidths=[240, 120, 180])
        act_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#059669')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
            ('PADDING', (0,0), (-1,-1), 4),
        ]))
        elements.append(act_table)
        elements.append(Spacer(1, 12))

    # 7. Model Versioning & Regulatory Disclaimer
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#CBD5E1'), spaceAfter=6))
    elements.append(Paragraph(f"<b>Model Telemetry:</b> Champion CatBoost + Platt Calibration | Pipeline v3.0.0 | Academic Baseline: Statlog German Credit Data (UCI)", ParagraphStyle('Meta', parent=body_style, fontSize=7, textColor=colors.HexColor('#64748B'))))
    elements.append(Paragraph(f"<b>Statutory Disclaimer:</b> {score_info.get('disclaimer', 'Nova Credit Score is a proprietary model-derived risk score and is not a bureau score.')} {decision_info.get('simulation_disclaimer', '')}", ParagraphStyle('Disc', parent=body_style, fontSize=7, textColor=colors.HexColor('#94A3B8'))))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()
