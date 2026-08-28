"""
Amortization Service — Generates detailed monthly and yearly loan amortization schedules.
"""
from typing import Dict, Any, List
from backend.app.services.emi_service import calculate_emi

def generate_amortization_schedule(
    principal: float,
    annual_rate: float,
    tenure_months: int,
    down_payment: float = 0.0,
    processing_fee_val: float = 0.0,
    processing_fee_type: str = "percentage"
) -> Dict[str, Any]:
    """
    Generates monthly schedule and yearly summary for a reducing-balance loan.
    """
    summary = calculate_emi(
        principal=principal,
        annual_rate=annual_rate,
        tenure_months=tenure_months,
        down_payment=down_payment,
        processing_fee_val=processing_fee_val,
        processing_fee_type=processing_fee_type
    )
    
    net_principal = summary["net_principal"]
    monthly_emi = summary["monthly_emi"]
    monthly_rate = (annual_rate / 100.0) / 12.0
    
    monthly_schedule: List[Dict[str, Any]] = []
    yearly_schedule: List[Dict[str, Any]] = []
    
    balance = net_principal
    current_year = 1
    year_opening = balance
    year_principal = 0.0
    year_interest = 0.0
    year_emi_total = 0.0

    for m in range(1, tenure_months + 1):
        opening = balance
        if monthly_rate == 0:
            interest_part = 0.0
            principal_part = min(opening, monthly_emi)
        else:
            interest_part = opening * monthly_rate
            principal_part = min(opening, monthly_emi - interest_part)
            
        # Final month adjustment to zero out remaining balance accurately
        if m == tenure_months or (opening - principal_part) < 1.0:
            principal_part = opening
            actual_emi = principal_part + interest_part
            closing = 0.0
        else:
            actual_emi = monthly_emi
            closing = max(0.0, opening - principal_part)
            
        balance = closing
        
        month_record = {
            "month": m,
            "year": ((m - 1) // 12) + 1,
            "opening_balance": round(opening, 2),
            "emi": round(actual_emi, 2),
            "principal_paid": round(principal_part, 2),
            "interest_paid": round(interest_part, 2),
            "extra_payment": 0.0,
            "closing_balance": round(closing, 2)
        }
        monthly_schedule.append(month_record)
        
        year_principal += principal_part
        year_interest += interest_part
        year_emi_total += actual_emi

        if m % 12 == 0 or m == tenure_months:
            yearly_schedule.append({
                "year": current_year,
                "opening_balance": round(year_opening, 2),
                "total_emi": round(year_emi_total, 2),
                "principal_paid": round(year_principal, 2),
                "interest_paid": round(year_interest, 2),
                "extra_payment": 0.0,
                "closing_balance": round(closing, 2)
            })
            current_year += 1
            year_opening = closing
            year_principal = 0.0
            year_interest = 0.0
            year_emi_total = 0.0
            
    return {
        "summary": summary,
        "monthly_schedule": monthly_schedule,
        "yearly_schedule": yearly_schedule
    }
