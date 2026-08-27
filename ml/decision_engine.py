import math
from typing import Dict, Any, List
from config import MAX_ALLOWED_FOIR, MAX_ALLOWED_DTI, MIN_DISPOSABLE_INCOME, MIN_LIQUIDITY_MONTHS


def evaluate_underwriting_policy(
    monthly_income: float,
    existing_emi: float,
    credit_amount: float,
    duration_months: int,
    savings_balance: float,
    nova_score: int,
    calibrated_prob_good: float,
    interest_rate: float = 10.5
) -> Dict[str, Any]:
    """
    Evaluates institutional underwriting policies, debt burden ratios, and affordability metrics
    independent of the ML risk probability.
    
    Decision States:
    - Likely Eligible (Instant Pre-approval at Prime Rates)
    - Conditionally Eligible (Subject to Collateral / Guarantor)
    - Manual Review (Borderline Debt Capacity / Documentation Required)
    - High Risk (Policy Threshold Violation / Excessive FOIR / High Default Odds)
    - Insufficient Information (Invalid financial parameters)
    """
    monthly_income = float(monthly_income)
    existing_emi = max(0.0, float(existing_emi))
    credit_amount = max(100.0, float(credit_amount))
    duration_months = max(1, int(duration_months))
    savings_balance = max(0.0, float(savings_balance))

    if monthly_income <= 0:
        return {
            "decision": "Insufficient Information",
            "decision_badge": "INSUFFICIENT DATA ⚠️",
            "decision_color": "#94A3B8",
            "summary": "Monthly income must be greater than zero for affordability assessment.",
            "eligibility_state": "Insufficient Information"
        }

    # Loan EMI Calculation
    r = interest_rate / 12 / 100
    n = duration_months
    if r > 0:
        new_emi = credit_amount * r * ((1 + r)**n) / (((1 + r)**n) - 1)
    else:
        new_emi = credit_amount / n

    total_monthly_obligations = existing_emi + new_emi
    
    # 1. FOIR (Fixed Obligation to Income Ratio)
    foir = total_monthly_obligations / monthly_income
    
    # 2. DTI (Debt-to-Annual-Income Ratio)
    total_estimated_debt = existing_emi * 24 + credit_amount # Estimated debt load
    dti = credit_amount / (monthly_income * (duration_months / 12))
    
    # 3. Disposable Income (accounting for 35% basic living expense)
    estimated_living_expenses = monthly_income * 0.35
    disposable_income = monthly_income - total_monthly_obligations - estimated_living_expenses
    
    # 4. Liquidity Ratio (Months of EMI covered by savings)
    liquidity_reserve_months = savings_balance / (new_emi + 1e-5)
    
    # 5. Affordability Classification
    if foir <= 0.35 and disposable_income >= 25000:
        affordability_tier = "Good"
    elif foir <= 0.48 and disposable_income >= MIN_DISPOSABLE_INCOME:
        affordability_tier = "Moderate"
    else:
        affordability_tier = "Stretched"

    # 6. Recommended Maximum EMI & Suggested Loan Capacity
    max_recommended_emi = max(0.0, (monthly_income * MAX_ALLOWED_FOIR) - existing_emi)
    if r > 0:
        suggested_loan_capacity = max_recommended_emi * (((1 + r)**n) - 1) / (r * ((1 + r)**n))
    else:
        suggested_loan_capacity = max_recommended_emi * n

    # Decision Engine Logic (Separated from raw ML)
    rejection_reasons = []
    condition_notes = []

    if foir > MAX_ALLOWED_FOIR:
        rejection_reasons.append(f"FOIR ({foir*100:.1f}%) exceeds institutional cap of {MAX_ALLOWED_FOIR*100:.0f}%.")
    if disposable_income < MIN_DISPOSABLE_INCOME:
        rejection_reasons.append(f"Monthly disposable income (₹{disposable_income:,.0f}) below safety buffer ₹{MIN_DISPOSABLE_INCOME:,.0f}.")
    if calibrated_prob_good < 0.40 or nova_score < 600:
        rejection_reasons.append("Proprietary Nova credit score indicates unacceptable default probability.")

    if liquidity_reserve_months < MIN_LIQUIDITY_MONTHS:
        condition_notes.append(f"Emergency savings reserve ({liquidity_reserve_months:.1f} mos) below recommended {MIN_LIQUIDITY_MONTHS} mos of EMI.")
    if 0.40 < foir <= MAX_ALLOWED_FOIR:
        condition_notes.append("Elevated debt obligation ratio — secondary income proof or co-borrower recommended.")

    # Determine Five-State Decision
    if rejection_reasons:
        decision = "High Risk"
        decision_badge = "HIGH RISK 🚩"
        decision_color = "#EF4444"
        summary = f"Declined due to policy threshold violation: {'; '.join(rejection_reasons)}"
        decision_confidence = "High"
    elif 0.45 <= calibrated_prob_good < 0.60 or 600 <= nova_score < 680 or foir > 0.42:
        decision = "Manual Review"
        decision_badge = "MANUAL REVIEW 🔍"
        decision_color = "#F59E0B"
        summary = "Referred to senior credit committee for secondary underwriting & income verification."
        decision_confidence = "Moderate"
    elif condition_notes or calibrated_prob_good < 0.75 or nova_score < 750:
        decision = "Conditionally Eligible"
        decision_badge = "CONDITIONALLY ELIGIBLE ⚡"
        decision_color = "#06B6D4"
        summary = "Approved subject to collateral confirmation, standard covenants, or verified payroll direct deposit."
        decision_confidence = "Medium-High"
    else:
        decision = "Likely Eligible"
        decision_badge = "LIKELY ELIGIBLE 👑"
        decision_color = "#10B981"
        summary = "Applicant meets prime institutional underwriting guidelines with excellent debt capacity."
        decision_confidence = "High"

    # Multi-Tenure Loan Comparison Matrix (24, 36, 48, 60 months)
    loan_tenure_comparison = []
    for tenure_m in [24, 36, 48, 60]:
        n_t = tenure_m
        if r > 0:
            emi_t = credit_amount * r * ((1 + r)**n_t) / (((1 + r)**n_t) - 1)
        else:
            emi_t = credit_amount / n_t
        total_pay_t = emi_t * n_t
        total_int_t = total_pay_t - credit_amount
        foir_t = (existing_emi + emi_t) / monthly_income
        
        loan_tenure_comparison.append({
            "tenure_months": tenure_m,
            "tenure_years": tenure_m // 12,
            "monthly_emi": round(emi_t, 2),
            "total_interest": round(total_int_t, 2),
            "total_cost": round(total_pay_t, 2),
            "foir_percentage": round(foir_t * 100, 1),
            "affordability": "Optimal" if foir_t <= 0.35 else ("Moderate" if foir_t <= 0.50 else "Risky"),
            "nova_recommendation": "Recommended" if (24 <= tenure_m <= 36 and foir_t <= 0.40) else "Feasible"
        })

    # Actionable Credit Improvement Recommendations
    improvement_recommendations = []
    if foir > 0.38:
        target_reduc = existing_emi * 0.35 if existing_emi > 2000 else 4000
        improvement_recommendations.append({
            "action": f"Reduce monthly obligations by ₹{target_reduc:,.0f}",
            "potential_impact": "+18 to +25 score points",
            "category": "Debt Burden Optimization"
        })
    if liquidity_reserve_months < 4:
        target_sav = (new_emi * 4) - savings_balance
        if target_sav > 0:
            improvement_recommendations.append({
                "action": f"Build emergency savings reserve to ₹{new_emi * 4:,.0f} (+₹{target_sav:,.0f})",
                "potential_impact": "Improved liquidity buffer & lower default probability",
                "category": "Liquidity Buffer"
            })
    if credit_amount > (monthly_income * 4):
        reduction_amt = credit_amount * 0.15
        improvement_recommendations.append({
            "action": f"Reduce requested credit amount by ₹{reduction_amt:,.0f}",
            "potential_impact": f"Drops FOIR by ~{((reduction_amt / duration_months) / monthly_income)*100:.1f}%, moving profile toward Likely Eligible",
            "category": "Credit Exposure"
        })
    if not improvement_recommendations:
        improvement_recommendations.append({
            "action": "Maintain current timely debt servicing and low utilization",
            "potential_impact": "Preserves prime credit standing",
            "category": "Maintenance"
        })

    return {
        "decision": decision,
        "decision_badge": decision_badge,
        "decision_color": decision_color,
        "decision_confidence": decision_confidence,
        "summary": summary,
        "affordability_tier": affordability_tier,
        "new_emi": round(new_emi, 2),
        "total_monthly_obligations": round(total_monthly_obligations, 2),
        "foir_ratio": round(foir, 4),
        "dti_ratio": round(dti, 4),
        "disposable_income": round(disposable_income, 2),
        "liquidity_reserve_months": round(liquidity_reserve_months, 1),
        "max_recommended_emi": round(max_recommended_emi, 2),
        "suggested_loan_capacity": round(suggested_loan_capacity, 2),
        "rejection_reasons": rejection_reasons,
        "condition_notes": condition_notes,
        "loan_tenure_comparison": loan_tenure_comparison,
        "improvement_recommendations": improvement_recommendations,
        "simulation_disclaimer": "Note: Improvements are model simulations, not guaranteed real-world credit-score changes."
    }
