"""
Tenure Optimizer Service — Evaluates dynamic tenure scenarios and identifies optimal repayment strategies.
"""
from typing import Dict, Any, List, Optional
from backend.app.services.emi_service import calculate_emi
from backend.app.services.affordability_service import evaluate_affordability

def optimize_tenures(
    principal: float,
    annual_rate: float,
    down_payment: float = 0.0,
    processing_fee_val: float = 0.0,
    processing_fee_type: str = "percentage",
    monthly_income: float = 0.0,
    existing_fixed_obligations: float = 0.0,
    target_tenure_months: Optional[int] = 36
) -> Dict[str, Any]:
    """
    Evaluates tenure options (12, 24, 36, 48, 60, 84, 120, 180, 240, 360 months)
    and tags:
    - Lowest Total Cost
    - Lowest EMI
    - Balanced Option
    """
    principal = max(0.0, float(principal))
    annual_rate = max(0.0, float(annual_rate))
    
    # Candidate tenures based on principal size
    if principal <= 300000:
        candidate_tenures = [6, 12, 18, 24, 36, 48]
    elif principal <= 1500000:
        candidate_tenures = [12, 24, 36, 48, 60, 84]
    else:
        candidate_tenures = [24, 36, 60, 120, 180, 240, 360]
        
    # Ensure target tenure is included if provided
    if target_tenure_months and target_tenure_months not in candidate_tenures and target_tenure_months > 0:
        candidate_tenures.append(target_tenure_months)
        candidate_tenures.sort()

    scenarios: List[Dict[str, Any]] = []
    min_interest = float("inf")
    min_emi = float("inf")
    
    lowest_cost_tenure = None
    lowest_emi_tenure = None

    for t in candidate_tenures:
        calc = calculate_emi(
            principal=principal,
            annual_rate=annual_rate,
            tenure_months=t,
            down_payment=down_payment,
            processing_fee_val=processing_fee_val,
            processing_fee_type=processing_fee_type
        )
        
        aff = evaluate_affordability(
            monthly_income=monthly_income,
            proposed_emi=calc["monthly_emi"],
            existing_emi=existing_fixed_obligations
        )
        
        item = {
            "tenure_months": t,
            "tenure_display": f"{t} Months" if t < 24 else f"{t} Months ({t//12}Y)",
            "monthly_emi": calc["monthly_emi"],
            "total_interest": calc["total_interest"],
            "total_repayment": calc["total_repayment"],
            "effective_total_cost": calc["effective_total_cost"],
            "foir": aff["new_foir"],
            "health_status": aff["health_status"],
            "health_code": aff["health_code"],
            "badge_color": aff["badge_color"],
            "tags": []
        }
        
        if calc["total_interest"] < min_interest:
            min_interest = calc["total_interest"]
            lowest_cost_tenure = t
            
        if calc["monthly_emi"] < min_emi:
            min_emi = calc["monthly_emi"]
            lowest_emi_tenure = t
            
        scenarios.append(item)

    # ── Balanced Option Recommendation Logic ──
    # Objective: Find shortest tenure where FOIR <= 38% (or lowest FOIR if all > 38%),
    # avoiding unnecessary interest inflation while preserving financial comfort.
    balanced_tenure = None
    comfortable_scenarios = [s for s in scenarios if s["foir"] <= 38.0 and s["monthly_income"] if "monthly_income" in s]
    
    if monthly_income > 0:
        # Filter for FOIR <= 38% or <= 45%
        valid = [s for s in scenarios if s["foir"] <= 38.0]
        if not valid:
            valid = [s for s in scenarios if s["foir"] <= 45.0]
        if not valid:
            valid = scenarios
        # Choose the shortest tenure among valid (which minimizes total interest while staying affordable)
        balanced_tenure = min(valid, key=lambda x: x["tenure_months"])["tenure_months"]
    else:
        # Default balanced: mid tenure in list
        mid_idx = len(scenarios) // 2
        balanced_tenure = scenarios[mid_idx]["tenure_months"]

    # Apply tags
    for s in scenarios:
        if s["tenure_months"] == lowest_cost_tenure:
            s["tags"].append("Lowest Total Cost")
        if s["tenure_months"] == lowest_emi_tenure:
            s["tags"].append("Lowest EMI")
        if s["tenure_months"] == balanced_tenure:
            s["tags"].append("Balanced Option")

    # Generate insight
    balanced_item = next((s for s in scenarios if s["tenure_months"] == balanced_tenure), scenarios[0])
    insight = (
        f"Nova recommends the {balanced_item['tenure_display']} tenure as the Balanced Option. "
        f"It requires a monthly EMI of ₹{balanced_item['monthly_emi']:,.0f} (modeled FOIR of {balanced_item['foir']:.1f}%), "
        f"saving ₹{scenarios[-1]['total_interest'] - balanced_item['total_interest']:,.0f} in interest compared to the longest tenure."
    )

    return {
        "target_tenure_months": target_tenure_months,
        "scenarios": scenarios,
        "lowest_cost_tenure": lowest_cost_tenure,
        "lowest_emi_tenure": lowest_emi_tenure,
        "balanced_tenure": balanced_tenure,
        "recommendation_insight": insight
    }
