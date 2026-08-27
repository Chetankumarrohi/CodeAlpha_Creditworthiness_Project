import numpy as np
from config import NOVA_SCORE_MIN, NOVA_SCORE_MAX

DISCLAIMER_TEXT = (
    "Nova Credit Score is Nova's proprietary model-derived risk score and is not a "
    "CIBIL, Experian, Equifax, CRIF, or FICO score."
)


def calculate_nova_score(
    calibrated_prob_good: float,
    dti: float,
    savings_standing: str,
    duration_months: int,
    age: int
) -> dict:
    """
    Calculates the proprietary Nova Credit Score (300 - 850) using a documented
    log-odds risk transformation and risk adjustments.
    
    Log-Odds Mapping:
    Log-Odds = ln( P(Good) / (1 - P(Good)) )
    Centered at Log-Odds = 0 (50% probability) -> Score = 650
    Scaling factor = 55 points per unit log-odds change.
    
    Score Bands:
    800 - 850: Exceptional
    750 - 799: Excellent
    700 - 749: Strong
    650 - 699: Moderate
    600 - 649: Weak
    300 - 599: High Risk
    """
    # Bound probability
    p = float(np.clip(calibrated_prob_good, 0.005, 0.995))
    
    # Calculate Log-Odds
    log_odds = float(np.log(p / (1.0 - p)))
    
    # Base Score derived from Log-Odds (scaled to 300 - 850 range)
    # Log-odds of +2.0 (~88% prob) -> 650 + 110 = 760
    # Log-odds of -2.0 (~12% prob) -> 650 - 110 = 540
    base_score = 650.0 + (log_odds * 55.0)

    # Financial Adjustments
    # 1. Debt-to-Income / Obligation Impact
    dti_adj = 30.0 if dti < 0.15 else (-40.0 if dti > 0.40 else 0.0)
    
    # 2. Liquid Savings Standing
    sav_clean = str(savings_standing).lower().strip()
    if sav_clean in ["rich", "quite rich"]:
        sav_adj = 25.0
    elif sav_clean == "moderate":
        sav_adj = 10.0
    elif sav_clean == "none":
        sav_adj = -25.0
    else:
        sav_adj = 0.0
    
    # 3. Loan Duration & Age Stability
    dur_adj = 15.0 if duration_months <= 12 else (-25.0 if duration_months > 36 else 0.0)
    age_adj = 15.0 if 28 <= age <= 55 else 0.0

    raw_score = base_score + dti_adj + sav_adj + dur_adj + age_adj
    final_score = int(round(np.clip(raw_score, NOVA_SCORE_MIN, NOVA_SCORE_MAX)))

    # Stable Score Band Classification
    if final_score >= 800:
        band = "Exceptional"
        badge = "NOVA EXCEPTIONAL 👑"
        vibe = "Prime Tier • Lowest Default Risk"
        color = "#10B981" # Emerald Green
    elif final_score >= 750:
        band = "Excellent"
        badge = "NOVA EXCELLENT 🛡️"
        vibe = "Strong Credit Profile"
        color = "#06B6D4" # Neon Cyan
    elif final_score >= 700:
        band = "Strong"
        badge = "NOVA STRONG ⚡"
        vibe = "Favorable Standing"
        color = "#3B82F6" # Royal Blue
    elif final_score >= 650:
        band = "Moderate"
        badge = "NOVA MODERATE 📊"
        vibe = "Acceptable Credit Risk"
        color = "#F59E0B" # Amber Gold
    elif final_score >= 600:
        band = "Weak"
        badge = "NOVA WEAK ⚠️"
        vibe = "Elevated Risk Profile"
        color = "#FB923C" # Orange
    else:
        band = "High Risk"
        badge = "HIGH RISK 🚩"
        vibe = "High Probability of Default"
        color = "#EF4444" # Crimson Red

    # Model Confidence Metric
    confidence_level = float(round(abs(p - 0.50) * 200.0, 1)) # 0% (at 0.50) to 99% (at 0.99)
    if confidence_level >= 70:
        conf_label = "High Confidence"
    elif confidence_level >= 40:
        conf_label = "Moderate Confidence"
    else:
        conf_label = "Borderline Confidence"

    return {
        "nova_score": final_score,
        "base_score": round(base_score, 1),
        "log_odds": round(log_odds, 3),
        "tier": band,
        "badge": badge,
        "vibe": vibe,
        "color": color,
        "confidence_percentage": confidence_level,
        "confidence_label": conf_label,
        "disclaimer": DISCLAIMER_TEXT,
        "adjustments": {
            "dti_adj": dti_adj,
            "savings_adj": sav_adj,
            "duration_adj": dur_adj,
            "age_adj": age_adj,
        }
    }
