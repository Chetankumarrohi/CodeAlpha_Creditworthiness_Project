"""
Loan Comparison Service — Side-by-side evaluation of up to 3 loan offers.
"""
from typing import Dict, Any, List
from backend.app.services.emi_service import calculate_emi
from backend.app.services.affordability_service import evaluate_affordability

def compare_loan_offers(
    offers: List[Dict[str, Any]],
    monthly_income: float = 0.0,
    existing_fixed_obligations: float = 0.0
) -> Dict[str, Any]:
    """
    Compares up to 3 loan offers side-by-side and highlights key metrics:
    - Lowest EMI
    - Lowest Total Interest
    - Lowest Effective Cost
    - Best Affordability
    """
    if not offers:
        return {"offers": [], "highlights": {}, "summary_note": "No loan offers provided for comparison."}
        
    offers = offers[:3]  # Max 3 offers
    evaluated_offers: List[Dict[str, Any]] = []

    min_emi = float("inf")
    min_interest = float("inf")
    min_cost = float("inf")
    min_foir = float("inf")

    lowest_emi_idx = 0
    lowest_interest_idx = 0
    lowest_cost_idx = 0
    best_affordability_idx = 0

    for idx, raw in enumerate(offers):
        offer_name = raw.get("offer_name", f"Offer {idx+1}")
        principal = max(0.0, float(raw.get("principal", 1000000)))
        rate = max(0.0, float(raw.get("annual_rate", 10.0)))
        tenure = max(1, int(raw.get("tenure_months", 36)))
        fee_val = max(0.0, float(raw.get("processing_fee", 0.0)))
        fee_type = raw.get("processing_fee_type", "percentage")
        other_fees = max(0.0, float(raw.get("other_upfront_fees", 0.0)))
        down_payment = max(0.0, float(raw.get("down_payment", 0.0)))
        prepay_notes = raw.get("prepayment_notes", "Standard terms")

        calc = calculate_emi(
            principal=principal,
            annual_rate=rate,
            tenure_months=tenure,
            down_payment=down_payment,
            processing_fee_val=fee_val,
            processing_fee_type=fee_type
        )

        aff = evaluate_affordability(
            monthly_income=monthly_income,
            proposed_emi=calc["monthly_emi"],
            existing_emi=existing_fixed_obligations
        )

        total_fees = calc["processing_fee"] + other_fees
        effective_total_cost = calc["net_principal"] + calc["total_interest"] + total_fees + down_payment

        item = {
            "offer_index": idx,
            "offer_name": offer_name,
            "gross_principal": round(principal, 2),
            "net_principal": calc["net_principal"],
            "annual_rate": round(rate, 2),
            "tenure_months": tenure,
            "monthly_emi": calc["monthly_emi"],
            "total_interest": calc["total_interest"],
            "total_repayment": calc["total_repayment"],
            "total_fees": round(total_fees, 2),
            "effective_total_cost": round(effective_total_cost, 2),
            "foir": aff["new_foir"],
            "health_status": aff["health_status"],
            "badge_color": aff["badge_color"],
            "prepayment_notes": prepay_notes,
            "highlights": []
        }

        if calc["monthly_emi"] < min_emi:
            min_emi = calc["monthly_emi"]
            lowest_emi_idx = idx

        if calc["total_interest"] < min_interest:
            min_interest = calc["total_interest"]
            lowest_interest_idx = idx

        if effective_total_cost < min_cost:
            min_cost = effective_total_cost
            lowest_cost_idx = idx

        if aff["new_foir"] < min_foir:
            min_foir = aff["new_foir"]
            best_affordability_idx = idx

        evaluated_offers.append(item)

    # Tag highlights
    if evaluated_offers:
        evaluated_offers[lowest_emi_idx]["highlights"].append("Lowest EMI")
        evaluated_offers[lowest_interest_idx]["highlights"].append("Lowest Interest")
        evaluated_offers[lowest_cost_idx]["highlights"].append("Lowest Effective Cost")
        if monthly_income > 0:
            evaluated_offers[best_affordability_idx]["highlights"].append("Best Affordability")

    lowest_cost_offer = evaluated_offers[lowest_cost_idx]["offer_name"]
    lowest_emi_offer = evaluated_offers[lowest_emi_idx]["offer_name"]
    
    summary_note = (
        f"{lowest_cost_offer} offers the lowest total effective cost (₹{evaluated_offers[lowest_cost_idx]['effective_total_cost']:,.0f}), "
        f"while {lowest_emi_offer} provides the lowest monthly commitment (₹{evaluated_offers[lowest_emi_idx]['monthly_emi']:,.0f}/month)."
    )

    return {
        "offers": evaluated_offers,
        "highlights": {
            "lowest_emi_offer": lowest_emi_offer,
            "lowest_interest_offer": evaluated_offers[lowest_interest_idx]["offer_name"],
            "lowest_effective_cost_offer": lowest_cost_offer,
            "best_affordability_offer": evaluated_offers[best_affordability_idx]["offer_name"] if monthly_income > 0 else None
        },
        "summary_note": summary_note
    }
