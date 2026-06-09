

import streamlit as st
import numpy as np
import pandas as pd
import joblib
import plotly.graph_objects as go

# LOAD MODEL
model = joblib.load("models/credit_model.pkl")
scaler = joblib.load("models/scaler.pkl")

# PAGE CONFIG
st.set_page_config(
    page_title="AI Credit Risk System",
    page_icon="💳",
    layout="wide"
)

# CUSTOM CSS
st.markdown("""
<style>

html, body, [class*="css"] {
    font-family: 'Poppins', sans-serif;
}

.main {
    background: linear-gradient(to right, #0f172a, #111827);
    color: white;
}

h1, h2, h3 {
    color: white;
}

.stButton>button {
    width: 100%;
    border-radius: 15px;
    height: 55px;
    font-size: 20px;
    font-weight: bold;
    background: linear-gradient(to right, #00c6ff, #0072ff);
    color: white;
    border: none;
}

.stButton>button:hover {
    background: linear-gradient(to right, #0072ff, #00c6ff);
}

.card {
    background: rgba(255,255,255,0.08);
    padding: 25px;
    border-radius: 20px;
    backdrop-filter: blur(10px);
    box-shadow: 0px 4px 30px rgba(0,0,0,0.2);
}

.metric-card {
    background: rgba(255,255,255,0.05);
    padding: 20px;
    border-radius: 15px;
    text-align: center;
}

</style>
""", unsafe_allow_html=True)

# TITLE
st.markdown("""
<h1 style='text-align:center;'>
💳 AI Creditworthiness Prediction System
</h1>
""", unsafe_allow_html=True)

st.markdown("""
<p style='text-align:center;font-size:18px;'>
Advanced Machine Learning system for predicting customer credit risk.
</p>
""", unsafe_allow_html=True)

st.write("")

# LAYOUT
col1, col2 = st.columns([1,1])

# LEFT SIDE INPUTS
with col1:

    st.markdown("<div class='card'>", unsafe_allow_html=True)

    st.subheader("📋 Customer Information")

    age = st.slider("Age", 18, 75, 30)

    income = st.number_input(
        "Monthly Income",
        min_value=1000,
        max_value=100000,
        value=25000
    )

    credit_amount = st.number_input(
        "Loan Amount",
        min_value=100,
        max_value=100000,
        value=5000
    )

    duration = st.slider(
        "Loan Duration (Months)",
        1,
        72,
        12
    )

    sex = st.selectbox(
        "Gender",
        ["Male", "Female"]
    )

    job = st.selectbox(
        "Job Type",
        [
            "Unskilled",
            "Skilled",
            "Highly Skilled",
            "Management"
        ]
    )

    housing = st.selectbox(
        "Housing",
        [
            "Own",
            "Rent",
            "Free"
        ]
    )

    purpose = st.selectbox(
        "Loan Purpose",
        [
            "Car",
            "Education",
            "Business",
            "Furniture",
            "Repairs"
        ]
    )

    predict_btn = st.button("🚀 Predict Credit Risk")

    st.markdown("</div>", unsafe_allow_html=True)

# RIGHT SIDE DASHBOARD
with col2:

    st.markdown("<div class='card'>", unsafe_allow_html=True)

    st.subheader("📊 Prediction Dashboard")

    if predict_btn:

        # ENCODING
        sex_map = {"Male":1, "Female":0}

        job_map = {
            "Unskilled":0,
            "Skilled":1,
            "Highly Skilled":2,
            "Management":3
        }

        housing_map = {
            "Own":0,
            "Rent":1,
            "Free":2
        }

        purpose_map = {
            "Car":0,
            "Education":1,
            "Business":2,
            "Furniture":3,
            "Repairs":4
        }

        debt_income_ratio = credit_amount / (income + 1)

        age_group = 0

        if age <= 25:
            age_group = 0
        elif age <= 35:
            age_group = 1
        elif age <= 50:
            age_group = 2
        else:
            age_group = 3

        # FEATURES
        features = np.array([[
            age,
            sex_map[sex],
            job_map[job],
            housing_map[housing],
            1,
            1,
            credit_amount,
            duration,
            purpose_map[purpose],
            debt_income_ratio,
            age_group
        ]])

        # SCALE
        features_scaled = scaler.transform(features)

        # PREDICTION
        prediction = model.predict(features_scaled)[0]

        probability = model.predict_proba(features_scaled)[0][1]

        # GAUGE CHART
        fig = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = probability * 100,
            title = {'text': "Approval Probability"},
            gauge = {
                'axis': {'range': [0,100]},
                'bar': {'color': "green"},
                'steps': [
                    {'range': [0,40], 'color': "red"},
                    {'range': [40,70], 'color': "orange"},
                    {'range': [70,100], 'color': "green"}
                ]
            }
        ))

        st.plotly_chart(fig, use_container_width=True)

        # RESULT
        if probability >= 0.7:

            st.success("✅ LOW CREDIT RISK")

        elif probability >= 0.4:

            st.warning("⚠️ MEDIUM CREDIT RISK")

        else:

            st.error("❌ HIGH CREDIT RISK")

        # METRICS
        c1, c2 = st.columns(2)

        with c1:
            st.metric(
                "Approval %",
                f"{probability*100:.2f}%"
            )

        with c2:
            st.metric(
                "Loan Amount",
                f"${credit_amount}"
            )

        # CUSTOMER SUMMARY
        st.subheader("👤 Customer Summary")

        summary = pd.DataFrame({
            "Feature":[
                "Age",
                "Income",
                "Loan Amount",
                "Duration",
                "Job"
            ],
            "Value":[
                age,
                income,
                credit_amount,
                duration,
                job
            ]
        })

        st.table(summary)

        # AI ANALYSIS
        st.subheader("🤖 AI Analysis")

        if probability >= 0.7:

            st.info("""
            • Customer has strong repayment reliability

            • Low probability of loan default

            • Financial profile appears stable

            • Recommended for approval
            """)

        elif probability >= 0.4:

            st.warning("""
            • Moderate repayment reliability

            • Medium financial risk detected

            • Additional verification recommended
            """)

        else:

            st.error("""
            • High default probability

            • Financial instability detected

            • Loan approval not recommended
            """)

    else:

        st.info("Enter customer details and click Predict.")

    st.markdown("</div>", unsafe_allow_html=True)

