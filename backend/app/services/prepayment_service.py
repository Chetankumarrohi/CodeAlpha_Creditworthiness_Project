"""
Prepayment Service — Simulates one-time lump sum prepayments and monthly extra EMI payoff strategies.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
from backend.app.services.emi_service import calculate_emi

def simulate_prepayment(
    principal: float,
    annual_rate: float,
    tenure_months: int,
    prepayment_amount: float = 0.0,
    prepayment_month: int = 12,
    strategy: str = "reduce_tenure",  # "reduce_tenure" or "reduce_emi"
    extra_monthly_payment: float = 0.0,
    start_date_str: Optional[str] = None
) -> Dict[str, Any]:
    """
    Simulates:
    1. One-time prepayment at `prepayment_month` using either `reduce_tenure` or `reduce_emi`.
    2. Recurring `extra_monthly_payment` added to every monthly installment.
    """
    principal = max(0.0, float(principal))
    annual_rate = max(0.0, float(annual_rate))
    tenure_months = max(1, int(tenure_months))
    prepayment_amount = max(0.0, float(prepayment_amount))
    prepayment_month = max(1, min(tenure_months, int(prepayment_month)))
    extra_monthly_payment = max(0.0, float(extra_monthly_payment))

    # Base Original Loan
    base_summary = calculate_emi(principal, annual_rate, tenure_months, start_date_str=start_date_str)
    original_emi = base_summary["monthly_emi"]
    monthly_rate = (annual_rate / 100.0) / 12.0

    # Build schedule prior to prepayment
    balance = principal
    orig_total_interest = base_summary["total_interest"]
    
    new_schedule: List[Dict[str, Any]] = []
    total_interest_paid = 0.0
    total_principal_paid = 0.0
    
    current_emi = original_emi
    effective_months = 0
    
    for m in range(1, tenure_months + 1):
        if balance <= 0:
            break
            
        opening = balance
        interest_part = opening * monthly_rate if monthly_rate > 0 else 0.0
        
        # Apply lump sum prepayment at specified month
        lump_sum_this_month = prepayment_amount if m == prepayment_month else 0.0
        
        # Calculate monthly installment target
        actual_monthly_payment = current_emi + extra_monthly_payment
        principal_part = max(0.0, actual_monthly_payment - interest_part)
        
        # Total principal paid this month (regular principal + lump sum)
        total_p_this_month = principal_part + lump_sum_this_month
        
        if total_p_this_month >= opening:
            # Loan paid off in full this month
            principal_part = opening
            lump_sum_applied = max(0.0, opening - principal_part) # if lump sum exceeds
            closing = 0.0
            actual_paid = opening + interest_part
        else:
            closing = opening - total_p_this_month
            actual_paid = total_p_this_month + interest_part
            
        balance = closing
        total_interest_paid += interest_part
        total_principal_paid += total_p_this_month
        effective_months += 1
        
        new_schedule.append({
            "month": m,
            "opening_balance": round(opening, 2),
            "regular_emi": round(current_emi, 2),
            "extra_payment": round(extra_monthly_payment + lump_sum_this_month, 2),
            "principal_paid": round(total_p_this_month, 2),
            "interest_paid": round(interest_part, 2),
            "closing_balance": round(closing, 2)
        })
        
        # Recalculate EMI if strategy is reduce_emi and prepayment just occurred
        if m == prepayment_month and lump_sum_this_month > 0 and strategy == "reduce_emi" and balance > 0:
            remaining_tenure = tenure_months - prepayment_month
            if remaining_tenure > 0:
                new_calc = calculate_emi(balance, annual_rate, remaining_tenure)
                current_emi = new_calc["monthly_emi"]

    months_saved = max(0, tenure_months - effective_months)
    new_total_repayment = total_principal_paid + total_interest_paid
    interest_saved = max(0.0, orig_total_interest - total_interest_paid)
    
    # Dates
    if start_date_str:
        try:
            start_dt = datetime.strptime(start_date_str[:10], "%Y-%m-%d")
        except ValueError:
            start_dt = datetime.now(timezone.utc)
    else:
        start_dt = datetime.now(timezone.utc)
        
    orig_end_dt = start_dt + relativedelta(months=tenure_months)
    new_end_dt = start_dt + relativedelta(months=effective_months)

    # Narrative explanation
    if extra_monthly_payment > 0 and prepayment_amount > 0:
        narrative = (
            f"By prepaying ₹{prepayment_amount:,.0f} at Month {prepayment_month} and adding ₹{extra_monthly_payment:,.0f}/month extra, "
            f"you close the loan {months_saved} months early and save ₹{interest_saved:,.0f} in interest."
        )
    elif extra_monthly_payment > 0:
        narrative = (
            f"Paying ₹{extra_monthly_payment:,.0f} extra each month could close this simulated loan {months_saved} months earlier "
            f"and save approximately ₹{interest_saved:,.0f} in interest."
        )
    elif prepayment_amount > 0:
        strategy_lbl = "reducing your monthly EMI" if strategy == "reduce_emi" else "shortening your loan tenure"
        narrative = (
            f"A one-time prepayment of ₹{prepayment_amount:,.0f} after month {prepayment_month} ({strategy_lbl}) "
            f"saves approximately ₹{interest_saved:,.0f} in total interest and reduces total payoff time by {months_saved} months."
        )
    else:
        narrative = "No prepayment parameters applied. Displaying standard schedule."

    return {
        "original_tenure_months": tenure_months,
        "new_tenure_months": effective_months,
        "months_saved": months_saved,
        "original_total_interest": round(orig_total_interest, 2),
        "new_total_interest": round(total_interest_paid, 2),
        "interest_saved": round(interest_saved, 2),
        "original_total_repayment": round(base_summary["total_repayment"], 2),
        "new_total_repayment": round(new_total_repayment, 2),
        "original_end_date": orig_end_dt.strftime("%Y-%m-%d"),
        "new_end_date": new_end_dt.strftime("%Y-%m-%d"),
        "strategy": strategy,
        "prepayment_amount": round(prepayment_amount, 2),
        "prepayment_month": prepayment_month,
        "extra_monthly_payment": round(extra_monthly_payment, 2),
        "narrative": narrative,
        "schedule": new_schedule[:360]  # capped for API response size safety
    }
