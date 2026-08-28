"""
EMI Service — Core reducing-balance loan calculations and effective cost metrics.
"""
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
from typing import Dict, Any, Optional

def calculate_emi(
    principal: float,
    annual_rate: float,
    tenure_months: int,
    down_payment: float = 0.0,
    processing_fee_val: float = 0.0,
    processing_fee_type: str = "percentage",  # "percentage" or "flat"
    start_date_str: Optional[str] = None
) -> Dict[str, Any]:
    """
    Calculates monthly EMI, total interest, total repayment, processing fees,
    effective total cost, interest-to-principal ratio, and payoff date.
    
    Formula: EMI = P * r * (1+r)^n / ((1+r)^n - 1)
    """
    principal = max(0.0, float(principal))
    annual_rate = max(0.0, float(annual_rate))
    tenure_months = max(1, int(tenure_months))
    down_payment = max(0.0, float(down_payment))
    
    # Net loan principal after down payment
    net_principal = max(0.0, principal - down_payment)
    
    # Processing fee calculation
    if processing_fee_type == "percentage":
        processing_fee = (net_principal * max(0.0, processing_fee_val)) / 100.0
    else:
        processing_fee = max(0.0, processing_fee_val)
        
    monthly_rate = (annual_rate / 100.0) / 12.0
    
    if net_principal == 0:
        emi = 0.0
        total_interest = 0.0
        total_repayment = 0.0
    elif monthly_rate == 0:
        emi = net_principal / tenure_months
        total_repayment = net_principal
        total_interest = 0.0
    else:
        compound_factor = (1 + monthly_rate) ** tenure_months
        emi = net_principal * (monthly_rate * compound_factor) / (compound_factor - 1)
        total_repayment = emi * tenure_months
        total_interest = total_repayment - net_principal

    effective_total_cost = net_principal + total_interest + processing_fee + down_payment
    
    interest_to_principal_ratio = (
        (total_interest / net_principal * 100.0) if net_principal > 0 else 0.0
    )
    
    # Date calculations
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str[:10], "%Y-%m-%d")
        except ValueError:
            start_date = datetime.now(timezone.utc)
    else:
        start_date = datetime.now(timezone.utc)
        
    end_date = start_date + relativedelta(months=tenure_months)

    return {
        "gross_loan_amount": round(principal, 2),
        "down_payment": round(down_payment, 2),
        "net_principal": round(net_principal, 2),
        "annual_rate": round(annual_rate, 2),
        "tenure_months": tenure_months,
        "monthly_emi": round(emi, 2),
        "total_interest": round(total_interest, 2),
        "total_repayment": round(total_repayment, 2),
        "processing_fee": round(processing_fee, 2),
        "effective_total_cost": round(effective_total_cost, 2),
        "interest_to_principal_ratio": round(interest_to_principal_ratio, 2),
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d")
    }
