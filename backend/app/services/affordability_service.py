"""
Affordability Service — Evaluates FOIR, debt burden, disposable income, and loan health assessment.
"""
from typing import Dict, Any, Optional

# Configurable guidance bands (Nova Internal Guidance)
AFFORDABILITY_BANDS = {
    "COMFORTABLE": {"max_foir": 35.0, "label": "Comfortable", "color": "success"},
    "MANAGEABLE": {"max_foir": 45.0, "label": "Manageable", "color": "info"},
    "STRETCHED": {"max_foir": 55.0, "label": "Stretched", "color": "warning"},
    "HIGH_BURDEN": {"max_foir": 100.0, "label": "High Burden", "color": "danger"},
}

def evaluate_affordability(
    monthly_income: float,
    proposed_emi: float,
    existing_emi: float = 0.0,
    housing_rent: float = 0.0,
    other_fixed_obligations: float = 0.0,
    essential_expenses: float = 0.0,
    dependents: int = 0
) -> Dict[str, Any]:
    """
    Calculates FOIR, DTI, disposable income before/after proposed loan,
    and returns a structured Loan Health Assessment with financial reasoning.
    """
    monthly_income = max(0.0, float(monthly_income))
    proposed_emi = max(0.0, float(proposed_emi))
    existing_emi = max(0.0, float(existing_emi))
    housing_rent = max(0.0, float(housing_rent))
    other_fixed_obligations = max(0.0, float(other_fixed_obligations))
    essential_expenses = max(0.0, float(essential_expenses))
    dependents = max(0, int(dependents))

    existing_fixed = existing_emi + housing_rent + other_fixed_obligations
    total_fixed_with_new = existing_fixed + proposed_emi

    if monthly_income <= 0:
        return {
            "monthly_income": 0.0,
            "proposed_emi": round(proposed_emi, 2),
            "existing_fixed_obligations": round(existing_fixed, 2),
            "total_fixed_obligations": round(total_fixed_with_new, 2),
            "existing_foir": 0.0,
            "new_foir": 0.0,
            "emi_to_income_ratio": 0.0,
            "disposable_income_before": 0.0,
            "disposable_income_after": 0.0,
            "repayment_capacity": 0.0,
            "health_status": "Insufficient Information",
            "health_code": "INSUFFICIENT_DATA",
            "badge_color": "neutral",
            "explanation": "Monthly net income was not provided or is zero. Please supply income details for affordability modeling."
        }

    existing_foir = (existing_fixed / monthly_income) * 100.0
    new_foir = (total_fixed_with_new / monthly_income) * 100.0
    emi_to_income_ratio = (proposed_emi / monthly_income) * 100.0

    disposable_before = monthly_income - existing_fixed
    disposable_after = monthly_income - (total_fixed_with_new + essential_expenses)
    repayment_capacity = max(0.0, disposable_before - essential_expenses)

    # Classify loan health state
    if new_foir <= AFFORDABILITY_BANDS["COMFORTABLE"]["max_foir"]:
        health_code = "COMFORTABLE"
        health_status = "Comfortable"
        badge_color = "success"
        explanation = (
            f"The proposed EMI of ₹{proposed_emi:,.0f} represents {emi_to_income_ratio:.1f}% of your supplied monthly income "
            f"(₹{monthly_income:,.0f}). Total fixed obligations increase from {existing_foir:.1f}% to {new_foir:.1f}%, "
            f"which remains well within Nova's comfortable threshold (≤35%). Your remaining net disposable buffer is ₹{disposable_after:,.0f}/month."
        )
    elif new_foir <= AFFORDABILITY_BANDS["MANAGEABLE"]["max_foir"]:
        health_code = "MANAGEABLE"
        health_status = "Manageable"
        badge_color = "info"
        explanation = (
            f"The proposed EMI of ₹{proposed_emi:,.0f} brings total modeled fixed obligations to {new_foir:.1f}% of monthly income. "
            f"This falls into Nova's manageable band (35%–45%). You retain a post-loan cash buffer of ₹{disposable_after:,.0f}/month."
        )
    elif new_foir <= AFFORDABILITY_BANDS["STRETCHED"]["max_foir"]:
        health_code = "STRETCHED"
        health_status = "Stretched"
        badge_color = "warning"
        explanation = (
            f"Caution: Total fixed obligations with this new loan reach {new_foir:.1f}% of your income. "
            f"This places your finances in Nova's stretched band (45%–55%), leaving a tight monthly buffer of ₹{disposable_after:,.0f}. "
            f"Consider extending the loan tenure or making a down payment."
        )
    else:
        health_code = "HIGH_BURDEN"
        health_status = "High Burden"
        badge_color = "danger"
        explanation = (
            f"High Burden Alert: Total monthly obligations of ₹{total_fixed_with_new:,.0f} consume {new_foir:.1f}% of income, "
            f"exceeding Nova's recommended 55% limit. Your disposable income after obligations would be ₹{disposable_after:,.0f}/month. "
            f"Lenders are likely to flag this as excessive leverage."
        )

    return {
        "monthly_income": round(monthly_income, 2),
        "proposed_emi": round(proposed_emi, 2),
        "existing_fixed_obligations": round(existing_fixed, 2),
        "total_fixed_obligations": round(total_fixed_with_new, 2),
        "existing_foir": round(existing_foir, 2),
        "new_foir": round(new_foir, 2),
        "emi_to_income_ratio": round(emi_to_income_ratio, 2),
        "disposable_income_before": round(disposable_before, 2),
        "disposable_income_after": round(disposable_after, 2),
        "repayment_capacity": round(repayment_capacity, 2),
        "health_status": health_status,
        "health_code": health_code,
        "badge_color": badge_color,
        "explanation": explanation
    }
