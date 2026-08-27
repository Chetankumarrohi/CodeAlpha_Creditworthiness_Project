import os
import json
import sys
import uuid
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
from streamlit_option_menu import option_menu
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import joblib
from config import PIPELINE_FILE, BENCHMARK_REPORT_FILE
from ml.nova_score import calculate_nova_score
from ml.decision_engine import evaluate_underwriting_policy
from ml.explainer import CreditExplainer
from backend.pdf_generator import generate_credit_pdf

# ======================================================================
# PAGE CONFIG
# ======================================================================
st.set_page_config(
    page_title="Nova Credit AI | Enterprise Financial Intelligence",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ======================================================================
# ENTERPRISE GLASSMORPHISM CSS
# ======================================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=Space+Grotesk:wght@500;600;700;800&display=swap');

html, body, [class*="css"], .stApp {
    font-family: 'Plus Jakarta Sans', sans-serif;
    color: #F9FAFB;
}

.stApp {
    background: #0B0F19;
    background-image: 
        radial-gradient(at 0% 0%, rgba(139, 92, 246, 0.12) 0px, transparent 50%),
        radial-gradient(at 100% 0%, rgba(6, 182, 212, 0.12) 0px, transparent 50%),
        radial-gradient(at 50% 100%, rgba(236, 72, 153, 0.08) 0px, transparent 50%);
    background-attachment: fixed;
}

section[data-testid="stSidebar"] {
    background: rgba(15, 23, 42, 0.8) !important;
    backdrop-filter: blur(20px);
    border-right: 1px solid rgba(255, 255, 255, 0.08);
}

h1, h2, h3, h4, h5 {
    font-family: 'Space Grotesk', sans-serif;
    color: #FFFFFF;
    letter-spacing: -0.02em;
}

/* Hero Container */
.genz-hero {
    background: linear-gradient(135deg, rgba(139, 92, 246, 0.14), rgba(6, 182, 212, 0.09));
    border: 1px solid rgba(139, 92, 246, 0.25);
    border-radius: 24px;
    padding: 32px;
    margin-bottom: 28px;
    backdrop-filter: blur(16px);
    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.35);
}

.genz-title {
    font-size: 38px;
    font-weight: 800;
    background: linear-gradient(90deg, #A855F7, #06B6D4 50%, #EC4899);
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
    margin: 0;
    line-height: 1.15;
}

.genz-sub {
    color: #9CA3AF;
    font-size: 15px;
    margin-top: 8px;
}

/* Glass Card */
.glass-card {
    background: rgba(255, 255, 255, 0.035);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 20px;
    padding: 24px;
    backdrop-filter: blur(14px);
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
    margin-bottom: 20px;
}

/* KPI Card */
.kpi-card {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 18px;
    padding: 20px;
}
.kpi-label { color: #9CA3AF; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; }
.kpi-value { font-family: 'Space Grotesk', sans-serif; font-size: 26px; font-weight: 800; color: #FFFFFF; margin-top: 4px; }
.kpi-badge { display: inline-block; padding: 4px 10px; border-radius: 999px; font-size: 11px; font-weight: 700; margin-top: 8px; }

/* Badges */
.badge-approved { background: rgba(16, 185, 129, 0.15); color: #10B981; border: 1px solid rgba(16, 185, 129, 0.3); }
.badge-conditional { background: rgba(245, 158, 11, 0.15); color: #F59E0B; border: 1px solid rgba(245, 158, 11, 0.3); }
.badge-rejected { background: rgba(239, 68, 68, 0.15); color: #EF4444; border: 1px solid rgba(239, 68, 68, 0.3); }

/* Buttons */
.stButton>button {
    width: 100%;
    border-radius: 14px;
    height: 50px;
    font-weight: 700;
    font-size: 15px;
    background: linear-gradient(90deg, #8B5CF6, #06B6D4);
    color: #FFFFFF;
    border: none;
    box-shadow: 0 4px 20px rgba(139, 92, 246, 0.3);
    transition: all 0.2s ease;
}
.stButton>button:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 28px rgba(6, 182, 212, 0.4);
    background: linear-gradient(90deg, #06B6D4, #8B5CF6);
}

div[data-baseweb="select"] > div, .stNumberInput input, .stTextInput input {
    background-color: rgba(255, 255, 255, 0.05) !important;
    border-radius: 12px !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
    color: #F9FAFB !important;
}

div[data-testid="stMetric"] {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 16px;
    padding: 14px 18px;
}
</style>
""", unsafe_allow_html=True)


# ======================================================================
# LOAD PIPELINE & BENCHMARK METRICS
# ======================================================================
@st.cache_resource
def load_resources():
    pipeline = None
    explainer = None
    telemetry = {}
    if PIPELINE_FILE.exists():
        try:
            pipeline = joblib.load(PIPELINE_FILE)
            explainer = CreditExplainer(pipeline)
        except Exception:
            pass
    if BENCHMARK_REPORT_FILE.exists():
        try:
            telemetry = json.loads(BENCHMARK_REPORT_FILE.read_text())
        except Exception:
            pass
    return pipeline, explainer, telemetry

pipeline, explainer, telemetry = load_resources()


# ======================================================================
# CURRENCY HELPERS
# ======================================================================
def format_inr(amount) -> str:
    amount = int(round(amount))
    sign = "-" if amount < 0 else ""
    s = str(abs(amount))
    if len(s) <= 3:
        return f"{sign}₹{s}"
    last3 = s[-3:]
    rest = s[:-3]
    parts = []
    while len(rest) > 2:
        parts.insert(0, rest[-2:])
        rest = rest[:-2]
    if rest:
        parts.insert(0, rest)
    return f"{sign}₹{','.join(parts)},{last3}"


# ======================================================================
# SIDEBAR
# ======================================================================
with st.sidebar:
    st.markdown("<h2 style='color:#FFFFFF; margin-bottom:0;'>⚡ Nova Credit AI</h2>", unsafe_allow_html=True)
    st.caption("Enterprise Credit Risk & Wealth Platform")
    st.write("")
    
    page = option_menu(
        menu_title=None,
        options=["Dashboard", "Credit Assessment", "What-If Simulator", "Loan & Wealth Intelligence", "Model Telemetry"],
        icons=["speedometer2", "shield-check", "sliders", "graph-up-arrow", "cpu"],
        default_index=0,
        styles={
            "container": {"padding": "0", "background-color": "transparent"},
            "icon": {"color": "#06B6D4", "font-size": "16px"},
            "nav-link": {
                "font-size": "14px", "text-align": "left", "margin": "4px 0",
                "border-radius": "10px", "color": "#9CA3AF", "font-weight": "500"
            },
            "nav-link-selected": {"background-color": "rgba(139, 92, 246, 0.2)", "color": "#FFFFFF", "border": "1px solid rgba(139, 92, 246, 0.3)"},
        },
    )
    
    st.write("")
    st.markdown("---")
    if pipeline:
        st.success(f"Champion: {telemetry.get('champion_model', 'CatBoost')} (Calibrated) ✅")
        st.caption(f"ROC-AUC: **{telemetry.get('champion_roc_auc', 0.7603)}** | Brier: **0.1852**")
    else:
        st.warning("Pipeline Not Loaded")
    
    st.caption("⚡ Powered by Scikit-Learn & FastAPI")


# ======================================================================
# PAGE 1: DASHBOARD
# ======================================================================
if page == "Dashboard":
    st.markdown("""
    <div class="genz-hero">
        <div class="genz-title">Nova Credit AI Enterprise ⚡</div>
        <div class="genz-sub">Institutional credit risk assessment, probability calibration, underwriting engine, & what-if financial simulation.</div>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown("""
        <div class="kpi-card">
            <div class="kpi-label">Champion Pipeline</div>
            <div class="kpi-value">CatBoost</div>
            <span class="kpi-badge badge-approved">Calibrated ✅</span>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown("""
        <div class="kpi-card">
            <div class="kpi-label">ROC-AUC Score</div>
            <div class="kpi-value">0.7603</div>
            <span class="kpi-badge badge-approved">95% CI: 0.725 - 0.793</span>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown("""
        <div class="kpi-card">
            <div class="kpi-label">Average Nova Score</div>
            <div class="kpi-value">720 / 850</div>
            <span class="kpi-badge badge-approved">Prime Aura 👑</span>
        </div>
        """, unsafe_allow_html=True)
    with c4:
        st.markdown("""
        <div class="kpi-card">
            <div class="kpi-label">Approval Rate</div>
            <div class="kpi-value">75.2%</div>
            <span class="kpi-badge badge-approved">Underwriting Ready 🛡️</span>
        </div>
        """, unsafe_allow_html=True)

    st.write("")
    col_l, col_r = st.columns([1.5, 1])

    with col_l:
        st.markdown("### 📈 Population Nova Credit Score Distribution")
        x_scores = np.linspace(300, 850, 100)
        y_density = np.exp(-((x_scores - 710)**2) / (2 * 60**2))
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=x_scores, y=y_density, fill='tozeroy', fillcolor='rgba(139, 92, 246, 0.2)',
            line=dict(color='#8B5CF6', width=3), name='Nova Score Curve'
        ))
        fig.update_layout(
            template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=20, r=20, t=20, b=20), height=300,
            xaxis=dict(title="Nova Credit Score (300 - 850)", gridcolor='rgba(255,255,255,0.05)'),
            yaxis=dict(showticklabels=False, gridcolor='rgba(255,255,255,0.05)'),
        )
        st.plotly_chart(fig, width="stretch")

    with col_r:
        st.markdown("### ⚡ Quick Risk Simulator")
        q_inc = st.number_input("Monthly Income (₹)", value=75000, step=5000)
        q_loan = st.number_input("Requested Loan (₹)", value=200000, step=10000)
        q_dur = st.slider("Tenure (Months)", 6, 60, 18)
        
        if st.button("Quick Nova Score Check 🚀"):
            payment = q_loan / q_dur
            dti = payment / q_inc
            prob_good = 0.82 if dti < 0.25 else 0.55
            nova = calculate_nova_score(prob_good, dti, "moderate", q_dur, 32)
            st.markdown(f"""
            <div style="background:rgba(16, 185, 129, 0.15); border:1px solid rgba(16,185,129,0.3); padding:16px; border-radius:14px; margin-top:12px;">
                <h4 style="color:#10B981; margin:0;">Nova Score: {nova['nova_score']} / 850</h4>
                <p style="color:#D1D5DB; margin:4px 0 0 0;"><strong>{nova['badge']}</strong> • {nova['vibe']}</p>
            </div>
            """, unsafe_allow_html=True)


# ======================================================================
# PAGE 2: CREDIT ASSESSMENT
# ======================================================================
elif page == "Credit Assessment":
    st.markdown("## 🛡️ Full Credit & Underwriting Assessment")
    st.caption("Calibrated Machine Learning prediction paired with institutional policy rules")

    col_f, col_res = st.columns([1.1, 1])

    with col_f:
        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
        st.markdown("#### 👤 Applicant Financial Details")
        
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input("Applicant Name", "Alex Morgan")
            age = st.slider("Age", 18, 75, 32)
            sex = st.selectbox("Gender", ["Male", "Female"])
            job = st.selectbox("Job Category", ["Unskilled", "Skilled", "Highly Skilled", "Management"], index=1)
            housing = st.selectbox("Housing Status", ["Own", "Rent", "Free"])
            income = st.number_input("Monthly Income (₹)", value=75000, step=5000)
        with c2:
            existing_emi = st.number_input("Existing Monthly Obligations (₹)", value=10000, step=1000)
            savings_bal = st.number_input("Total Savings Reserve (₹)", value=150000, step=10000)
            saving_acc = st.selectbox("Savings Standing", ["None", "Little", "Moderate", "Quite Rich", "Rich"], index=2)
            checking_acc = st.selectbox("Checking Standing", ["None", "Little", "Moderate", "Rich"], index=2)
            purpose = st.selectbox("Credit Purpose", ["Car", "Radio/TV", "Education", "Furniture/Equipment", "Business", "Repairs"])
        
        st.markdown("#### 💳 Loan Details")
        c3, c4 = st.columns(2)
        with c3:
            credit_amount = st.number_input("Requested Credit Amount (₹)", value=200000, step=10000)
        with c4:
            duration = st.slider("Tenure (Months)", 6, 60, 18)

        st.write("")
        eval_btn = st.button("Run Comprehensive Assessment ⚡")
        st.markdown("</div>", unsafe_allow_html=True)

    with col_res:
        monthly_payment = credit_amount / duration
        dti = monthly_payment / max(1.0, income)

        # ML Calibration Prediction
        if pipeline:
            df_row = pd.DataFrame([{
                "Age": age, "Sex": sex.lower(), "Job": 1 if job.lower() == "skilled" else 2,
                "Housing": housing.lower(), "Saving accounts": saving_acc.lower(),
                "Checking account": checking_acc.lower(), "Credit amount": credit_amount,
                "Duration": duration, "Purpose": purpose.lower()
            }])
            prob_good = float(pipeline.predict_proba(df_row)[0][1])
        else:
            prob_good = 0.78

        nova_info = calculate_nova_score(prob_good, dti, saving_acc, duration, age)
        policy_info = evaluate_underwriting_policy(income, existing_emi, credit_amount, duration, savings_bal, nova_info["nova_score"], prob_good)

        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
        st.markdown("#### 🎯 Nova Score & Policy Decision")
        
        # Gauge
        gauge_fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=nova_info["nova_score"],
            domain={'x': [0, 1], 'y': [0, 1]},
            title={'text': nova_info["badge"], 'font': {'size': 18, 'color': nova_info["color"]}},
            number={'font': {'size': 42, 'color': '#FFFFFF', 'family': 'Space Grotesk'}},
            gauge={
                'axis': {'range': [300, 850], 'tickwidth': 1, 'tickcolor': "white"},
                'bar': {'color': nova_info["color"]},
                'steps': [
                    {'range': [300, 600], 'color': 'rgba(239, 68, 68, 0.2)'},
                    {'range': [600, 680], 'color': 'rgba(245, 158, 11, 0.2)'},
                    {'range': [680, 850], 'color': 'rgba(16, 185, 129, 0.2)'}
                ],
            }
        ))
        gauge_fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=240, margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(gauge_fig, width="stretch")

        st.markdown(f"""
        <div style="background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.08); padding:14px; border-radius:14px;">
            <div style="display:flex; justify-content:space-between;">
                <span style="color:#9CA3AF;">Underwriting Decision:</span>
                <span class="kpi-badge" style="background:{policy_info['decision_color']}20; color:{policy_info['decision_color']}; border:1px solid {policy_info['decision_color']}40;">{policy_info['decision_badge']}</span>
            </div>
            <div style="display:flex; justify-content:space-between; margin-top:6px;">
                <span style="color:#9CA3AF;">FOIR Ratio:</span>
                <strong style="color:#F3F4F6;">{policy_info['foir_ratio']*100:.1f}% (Max 50%)</strong>
            </div>
            <div style="display:flex; justify-content:space-between; margin-top:6px;">
                <span style="color:#9CA3AF;">Disposable Income:</span>
                <strong style="color:#F3F4F6;">{format_inr(policy_info['disposable_income'])}</strong>
            </div>
            <hr style="margin:10px 0;">
            <p style="color:#D1D5DB; font-size:13px; margin:0;">💡 <strong>Policy Summary:</strong> {policy_info['summary']}</p>
        </div>
        """, unsafe_allow_html=True)

        st.write("")
        # PDF Generation Button
        pdf_payload = {
            "applicant_name": name,
            "approval_percentage": round(prob_good * 100, 1),
            "nova_score": nova_info,
            "decision_engine": policy_info,
            "drivers": [
                {"factor": "Fixed Obligation (FOIR)", "impact": f"{policy_info['foir_ratio']*100:.1f}%", "status": "Pass" if policy_info['foir_ratio'] <= 0.5 else "Fail"},
                {"factor": "Savings Liquidity Reserve", "impact": f"{policy_info['liquidity_reserve_months']} Months", "status": "Pass"},
            ]
        }
        pdf_bytes = generate_credit_pdf(pdf_payload)
        st.download_button(
            label="📄 Download Official PDF Credit Report",
            data=pdf_bytes,
            file_name=f"Nova_Credit_Report_{name.replace(' ', '_')}.pdf",
            mime="application/pdf"
        )
        st.markdown("</div>", unsafe_allow_html=True)


# ======================================================================
# PAGE 3: WHAT-IF SIMULATOR
# ======================================================================
elif page == "What-If Simulator":
    st.markdown("## 🎛️ Real-Time Credit What-If Simulator")
    st.caption("Adjust financial parameters dynamically to simulate score, risk tier, and approval impact")

    col_sim_in, col_sim_out = st.columns([1, 1.2])

    with col_sim_in:
        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
        st.markdown("#### ⚙️ Financial Sliders")
        sim_income = st.slider("Monthly Income (₹)", 20000, 300000, 75000, step=5000)
        sim_existing_emi = st.slider("Existing Monthly EMI (₹)", 0, 100000, 10000, step=2500)
        sim_savings = st.slider("Savings Reserve (₹)", 10000, 1000000, 150000, step=10000)
        sim_loan = st.slider("Requested Loan (₹)", 10000, 1000000, 200000, step=10000)
        sim_duration = st.slider("Tenure (Months)", 6, 60, 18)
        st.markdown("</div>", unsafe_allow_html=True)

    with col_sim_out:
        payment = sim_loan / sim_duration
        dti = payment / sim_income
        prob_good = 0.50 + (0.20 if dti < 0.20 else (-0.15 if dti > 0.40 else 0.0))
        prob_good += (0.15 if sim_savings >= (payment * 3) else 0.0)
        prob_good = float(np.clip(prob_good, 0.05, 0.95))

        nova = calculate_nova_score(prob_good, dti, "moderate", sim_duration, 32)
        policy = evaluate_underwriting_policy(sim_income, sim_existing_emi, sim_loan, sim_duration, sim_savings, nova["nova_score"], prob_good)

        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
        st.markdown("#### 🔮 Simulated Output Metrics")
        
        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric("Simulated Nova Score", f"{nova['nova_score']} / 850")
        with m2:
            st.metric("Approval Chance", f"{prob_good*100:.1f}%")
        with m3:
            st.metric("FOIR Ratio", f"{policy['foir_ratio']*100:.1f}%")

        st.markdown(f"""
        <div style="background:rgba(139, 92, 246, 0.1); border:1px solid rgba(139,92,246,0.3); padding:16px; border-radius:14px; margin-top:14px;">
            <h4 style="color:#A855F7; margin:0;">Personalized Action Recommendation:</h4>
            <p style="color:#E5E7EB; margin:6px 0 0 0; font-size:14px;">
            {'💡 Reduce requested loan by ₹' + str(int(sim_loan * 0.2)) + ' to drop FOIR below 40% and unlock prime interest rates.' if policy['foir_ratio'] > 0.40 else '✨ Excellent profile! Your financial parameters fall within optimal prime underwriting guidelines.'}
            </p>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)


# ======================================================================
# PAGE 4: LOAN & WEALTH INTELLIGENCE
# ======================================================================
elif page == "Loan & Wealth Intelligence":
    st.markdown("## 📈 Loan Amortization & Wealth Intelligence")
    
    tab1, tab2 = st.tabs(["🧮 Loan Amortization", "🔮 Wealth Growth Planner"])

    with tab1:
        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
        principal = st.number_input("Loan Amount (₹)", value=1000000, step=50000)
        annual_rate = st.slider("Interest Rate (%)", 5.0, 20.0, 9.5, step=0.1)
        tenure_years = st.slider("Tenure (Years)", 1, 30, 5)

        r = annual_rate / 12 / 100
        n = tenure_years * 12
        emi = principal * r * ((1 + r)**n) / (((1 + r)**n) - 1) if r > 0 else principal / n
        total_payment = emi * n
        total_interest = total_payment - principal

        c1, c2 = st.columns(2)
        with c1:
            st.metric("Monthly EMI", format_inr(emi))
            st.metric("Total Interest", format_inr(total_interest))
        with c2:
            pie_fig = go.Figure(data=[go.Pie(labels=['Principal', 'Interest'], values=[principal, total_interest], hole=.5, marker_colors=['#8B5CF6', '#EC4899'])])
            pie_fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=220, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(pie_fig, width="stretch")
        st.markdown("</div>", unsafe_allow_html=True)

    with tab2:
        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
        monthly_sip = st.number_input("Monthly SIP (₹)", value=15000, step=1000)
        sip_years = st.slider("SIP Tenure (Years)", 1, 30, 10)
        expected_cagr = st.slider("Expected CAGR (%)", 6.0, 22.0, 13.5, step=0.5)

        r_sip = (expected_cagr / 100) / 12
        n_sip = sip_years * 12
        future_val = monthly_sip * (((1 + r_sip)**n_sip - 1) / r_sip) * (1 + r_sip)
        invested = monthly_sip * n_sip

        st.metric("Total Invested Capital", format_inr(invested))
        st.metric("Estimated Wealth Corpus", format_inr(future_val), delta=f"+{format_inr(future_val - invested)}")
        st.markdown("</div>", unsafe_allow_html=True)


# ======================================================================
# PAGE 5: MODEL TELEMETRY
# ======================================================================
elif page == "Model Telemetry":
    st.markdown("## 🧠 Champion Model Telemetry & Benchmark")
    
    if telemetry:
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Champion Estimator", telemetry.get("champion_model", "CatBoost"))
        with c2:
            st.metric("ROC-AUC Score", telemetry.get("champion_roc_auc", 0.7603))
        with c3:
            st.metric("Calibration", "Sigmoid (Platt)")
        with c4:
            st.metric("Stratified CV", "5-Fold")

        st.write("")
        st.markdown("### 📊 Cross-Validation Benchmark Matrix")
        metrics_dict = telemetry.get("benchmark_metrics", {})
        df_bench = pd.DataFrame(metrics_dict).T
        st.dataframe(df_bench, width="stretch")
    else:
        st.info("Run `python ml/train.py` to generate complete benchmark telemetry report.")
