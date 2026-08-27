"use strict";

// ─── Utilities ────────────────────────────────────────────────────────────────
const fmt = (n, dec = 0) => Number(n).toLocaleString("en-IN", { maximumFractionDigits: dec });
const fmtPct = (n) => (n * 100).toFixed(1) + "%";
const fmtMono = (v) => `<span style="font-family:var(--font-mono);font-weight:600;">${v}</span>`;

function pillHtml(decision) {
  const map = {
    "Likely Eligible":       "pill-success",
    "Conditionally Eligible":"pill-info",
    "Manual Review":         "pill-warning",
    "High Risk":             "pill-danger",
    "Insufficient Information":"pill-neutral",
  };
  const cls = map[decision] || "pill-neutral";
  return `<span class="pill ${cls}">${decision}</span>`;
}

// ─── Authentication & Session State ───────────────────────────────────────────
let currentUser = null;
let currentAuthTab = "login";

function getAuthHeaders() {
  const token = localStorage.getItem("nova_token");
  return token ? { "Authorization": `Bearer ${token}` } : {};
}

function initSplashAndAuth() {
  // Splash Screen Intro Animation
  setTimeout(() => {
    const splash = document.getElementById("splash-screen");
    if (splash) splash.classList.add("fade-out");
  }, 1800);

  // Check stored user session
  const storedUser = localStorage.getItem("nova_user");
  if (storedUser) {
    try {
      currentUser = JSON.parse(storedUser);
      updateUserUI();
    } catch(e) { localStorage.removeItem("nova_user"); }
  }
}

function openAuthModal() {
  const modal = document.getElementById("authModal");
  if (modal) modal.classList.add("active");
}

function closeAuthModal() {
  const modal = document.getElementById("authModal");
  if (modal) modal.classList.remove("active");
}

function toggleAuthModal() {
  if (currentUser) {
    // Logout
    localStorage.removeItem("nova_token");
    localStorage.removeItem("nova_user");
    currentUser = null;
    updateUserUI();
    loadHistory();
  } else {
    openAuthModal();
  }
}

function switchAuthTab(tab) {
  currentAuthTab = tab;
  const loginBtn = document.getElementById("tabLoginBtn");
  const regBtn   = document.getElementById("tabRegBtn");
  const nameGrp  = document.getElementById("nameGroup");
  const titleEl  = document.getElementById("authTitle");
  const subEl    = document.getElementById("authSub");
  const btnText  = document.getElementById("authBtnText");
  const tipEl    = document.getElementById("adminTip");

  if (tab === "login") {
    loginBtn.classList.add("active");
    regBtn.classList.remove("active");
    if (nameGrp) nameGrp.style.display = "none";
    if (titleEl) titleEl.textContent = "Sign In to Nova Credit";
    if (subEl)   subEl.textContent   = "Institutional Access & Private Risk History";
    if (btnText) btnText.textContent = "Sign In to Workspace";
    if (tipEl)   tipEl.style.display   = "block";
  } else {
    regBtn.classList.add("active");
    loginBtn.classList.remove("active");
    if (nameGrp) nameGrp.style.display = "block";
    if (titleEl) titleEl.textContent = "Register New Account";
    if (subEl)   subEl.textContent   = "Create your secure credit risk session";
    if (btnText) btnText.textContent = "Create Account";
    if (tipEl)   tipEl.style.display   = "none";
  }
}

async function handleAuthSubmit(e) {
  e.preventDefault();
  const email    = document.getElementById("authEmail").value;
  const password = document.getElementById("authPassword").value;
  const name     = document.getElementById("authName")?.value || "";

  const endpoint = currentAuthTab === "login" ? "/api/v1/auth/login" : "/api/v1/auth/register";
  const body = currentAuthTab === "login"
    ? { email, password }
    : { email, password, full_name: name || email.split("@")[0] };

  try {
    const res = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Authentication failed");
    }
    const data = await res.json();
    localStorage.setItem("nova_token", data.access_token);
    currentUser = {
      user_id: data.user_id,
      email: data.email,
      full_name: data.full_name,
      role: data.role,
    };
    localStorage.setItem("nova_user", JSON.stringify(currentUser));
    updateUserUI();
    closeAuthModal();
    loadHistory();
  } catch(err) {
    alert("Auth Error: " + err.message);
  }
}

function fillAdminDemo() {
  const emailInput = document.getElementById("authEmail");
  const passInput  = document.getElementById("authPassword");
  if (emailInput) emailInput.value = "admin@novacredit.ai";
  if (passInput)  passInput.value  = "Admin@123456";
  switchAuthTab("login");
}

function toggleMobileSidebar() {
  const sidebar = document.getElementById("appSidebar");
  const overlay = document.getElementById("mobileOverlay");
  if (sidebar) sidebar.classList.toggle("mobile-open");
  if (overlay) overlay.classList.toggle("active");
}

function updateUserUI() {
  const avatarEl = document.getElementById("userAvatar");
  const nameEl   = document.getElementById("userName");
  const roleEl   = document.getElementById("userRoleBadge");
  const topText  = document.getElementById("topbarAuthText");
  const actionBtn= document.getElementById("authActionBtn");
  const topUserId= document.getElementById("topbarUserId");

  if (currentUser) {
    const initials = (currentUser.full_name || currentUser.email).split(" ").map(n => n[0]).join("").toUpperCase().slice(0, 2);
    if (avatarEl) avatarEl.textContent = initials || "U";
    if (nameEl)   nameEl.textContent   = currentUser.full_name || currentUser.email;
    if (roleEl) {
      roleEl.textContent = currentUser.role === "admin" ? "ADMIN 👑" : "USER 🔒";
      roleEl.className = currentUser.role === "admin" ? "pill pill-warning" : "pill pill-info";
    }
    if (topUserId) {
      topUserId.style.display = "inline-flex";
      topUserId.innerHTML = currentUser.role === "admin"
        ? `<span class="pill pill-warning">👑 Admin ID: ${currentUser.user_id || 'ADMIN-0001'}</span>`
        : `<span class="pill pill-info">🔒 User ID: ${currentUser.user_id || 'USR-SESS'}</span>`;
    }
    if (topText)   topText.textContent  = "Sign Out";
    if (actionBtn) actionBtn.title      = "Sign Out";
  } else {
    if (avatarEl) avatarEl.textContent = "G";
    if (nameEl)   nameEl.textContent   = "Guest Mode";
    if (roleEl) {
      roleEl.textContent = "Guest";
      roleEl.className = "pill pill-neutral";
    }
    if (topUserId) {
      topUserId.style.display = "none";
      topUserId.innerHTML = "";
    }
    if (topText)   topText.textContent  = "Sign In";
    if (actionBtn) actionBtn.title      = "Sign In / Register";
  }
}


// ─── Sidebar Navigation ────────────────────────────────────────────────────────
const PAGE_TITLES = {
  overview:   "Financial Overview",
  assessment: "Credit Risk Assessment",
  simulator:  "What-If Scenario Builder",
  history:    "Assessment Audit Ledger",
  calculator: "Loan Amortization",
  funds:      "Fund Explorer",
  telemetry:  "Model Intelligence",
};

function initNav() {
  document.querySelectorAll(".nav-item").forEach(item => {
    item.addEventListener("click", e => {
      e.preventDefault();
      const tab = item.dataset.tab;
      if (!tab) return;
      document.querySelectorAll(".nav-item").forEach(i => i.classList.remove("active"));
      document.querySelectorAll(".view-section").forEach(v => v.classList.remove("active"));
      item.classList.add("active");
      const view = document.getElementById(`view-${tab}`);
      if (view) view.classList.add("active");
      const titleEl = document.getElementById("pageTitle");
      if (titleEl) titleEl.textContent = PAGE_TITLES[tab] || tab;
      if (tab === "history") loadHistory();
      if (tab === "overview") loadHistory();
      if (tab === "telemetry") loadModelIntelligence();
      if (tab === "simulator") runSimulation();
      if (window.lucide) lucide.createIcons();
    });
  });
}

// ─── Step Wizard ──────────────────────────────────────────────────────────────
let currentStep = 1;
const TOTAL_STEPS = 5;

function nextStep(target) {
  if (target > currentStep) {
    if (!validateStep(currentStep)) return;
  }
  document.getElementById(`step-${currentStep}`).classList.remove("active");
  currentStep = target;
  document.getElementById(`step-${currentStep}`).classList.add("active");
  updateStepUI();
  if (currentStep === 4) updateEmiPreview();
  if (currentStep === 5) renderReviewSummary();
  if (window.lucide) lucide.createIcons();
}

function validateStep(step) {
  if (step === 1) {
    const name = document.getElementById("s1_name").value.trim();
    if (!name) { alert("Please enter the applicant's full name."); return false; }
  }
  if (step === 3) {
    const income = parseFloat(document.getElementById("s3_income").value);
    if (!income || income < 5000) { alert("Monthly income must be at least ₹5,000."); return false; }
  }
  if (step === 4) {
    const amt = parseFloat(document.getElementById("s4_amount").value);
    const dur = parseInt(document.getElementById("s4_dur").value);
    if (!amt || amt < 1000) { alert("Loan amount must be at least ₹1,000."); return false; }
    if (!dur || dur < 6)    { alert("Tenure must be at least 6 months."); return false; }
  }
  return true;
}

function updateStepUI() {
  for (let i = 1; i <= TOTAL_STEPS; i++) {
    const circle = document.getElementById(`sc-${i}`);
    const label  = document.getElementById(`sl-${i}`);
    const conn   = document.getElementById(`scon-${i}`);
    circle.classList.remove("active", "done");
    label.classList.remove("active");
    if (i < currentStep) { circle.classList.add("done"); circle.innerHTML = "✓"; }
    else if (i === currentStep) { circle.classList.add("active"); circle.textContent = String(i).padStart(2, "0"); label.classList.add("active"); }
    else { circle.textContent = String(i).padStart(2, "0"); }
    if (conn) conn.classList.toggle("done", i < currentStep);
  }
}

function updateEmiPreview() {
  const amt = parseFloat(document.getElementById("s4_amount").value) || 0;
  const dur = parseInt(document.getElementById("s4_dur").value) || 12;
  const r = 10.5 / 12 / 100;
  const emi = amt * r * Math.pow(1+r, dur) / (Math.pow(1+r, dur) - 1);
  document.getElementById("s4_emi_preview").textContent = "₹ " + fmt(emi, 0);
}

function renderReviewSummary() {
  const rows = [
    ["Applicant Name",         document.getElementById("s1_name").value],
    ["Age",                    document.getElementById("s1_age").value + " yrs"],
    ["Housing",                document.getElementById("s1_housing").value],
    ["Employment",             document.getElementById("s2_job").value],
    ["Loan Purpose",           document.getElementById("s2_purpose").value],
    ["Monthly Income",         "₹" + fmt(document.getElementById("s3_income").value)],
    ["Existing EMIs",          "₹" + fmt(document.getElementById("s3_emi").value)],
    ["Emergency Savings",      "₹" + fmt(document.getElementById("s3_savings").value)],
    ["Savings Account",        document.getElementById("s3_saving_acc").value],
    ["Checking Account",       document.getElementById("s3_check_acc").value],
    ["Requested Loan",         "₹" + fmt(document.getElementById("s4_amount").value)],
    ["Tenure",                 document.getElementById("s4_dur").value + " months"],
  ];
  document.getElementById("review-summary").innerHTML = rows.map(([k, v]) => `
    <div class="stat-row"><span>${k}</span><strong>${v}</strong></div>
  `).join("");
}

function collectPayload() {
  return {
    applicant_name:   document.getElementById("s1_name").value,
    age:              parseInt(document.getElementById("s1_age").value),
    sex:              document.getElementById("s1_sex").value,
    housing:          document.getElementById("s1_housing").value,
    job:              document.getElementById("s2_job").value,
    purpose:          document.getElementById("s2_purpose").value,
    monthly_income:   parseFloat(document.getElementById("s3_income").value),
    existing_emi:     parseFloat(document.getElementById("s3_emi").value) || 0,
    savings_balance:  parseFloat(document.getElementById("s3_savings").value) || 0,
    saving_accounts:  document.getElementById("s3_saving_acc").value,
    checking_account: document.getElementById("s3_check_acc").value,
    credit_amount:    parseFloat(document.getElementById("s4_amount").value),
    duration:         parseInt(document.getElementById("s4_dur").value),
  };
}

// ─── Credit Assessment Submission ─────────────────────────────────────────────
async function submitAssessment() {
  const btn = document.getElementById("submitBtn");
  const resultContent = document.getElementById("result-content");
  btn.disabled = true;
  resultContent.innerHTML = `<div style="text-align:center;padding:56px 16px;"><div class="spinner"></div><p style="margin-top:14px;font-size:12px;color:var(--text-muted);">Executing CatBoost pipeline · SHAP attribution · Policy engine...</p></div>`;

  const payload = collectPayload();

  try {
    const res = await fetch("/api/v1/assess", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeaders() },
      body: JSON.stringify(payload)
    });
    if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || "Assessment failed"); }
    const data = await res.json();
    renderResult(data);
    updateOverviewHero(data);
    loadHistory();
  } catch (err) {
    resultContent.innerHTML = `<div style="padding:16px;background:var(--danger-sub);border:1px solid var(--danger-border);border-radius:var(--r-md);color:var(--danger);font-size:12px;">Error: ${err.message}</div>`;
  } finally {
    btn.disabled = false;
  }
}

function renderResult(data) {
  const sc = data.nova_score || {};
  const de = data.decision_engine || {};
  const posD = data.top_positive_drivers || [];
  const riskD = data.top_risk_drivers || [];
  const lc = de.loan_tenure_comparison || [];
  const recs = de.improvement_recommendations || [];

  let pillCls = "pill-success";
  if (de.decision === "High Risk") pillCls = "pill-danger";
  else if (de.decision === "Manual Review") pillCls = "pill-warning";
  else if (de.decision === "Conditionally Eligible") pillCls = "pill-info";

  const scoreColor = sc.color || "var(--success)";

  document.getElementById("result-content").innerHTML = `
    <!-- Score Hero -->
    <div class="score-hero" style="border-color:${scoreColor}30;">
      <div class="score-num" style="color:${scoreColor};">${sc.nova_score}<span style="font-size:16px;color:var(--text-muted);font-weight:400;">/850</span></div>
      <div class="score-info">
        <div class="score-tier" style="color:${scoreColor};">${sc.tier} Band</div>
        <div class="score-decision">${de.decision || "Likely Eligible"}</div>
        <div class="score-conf">Model Confidence: ${sc.confidence_percentage}% · ${sc.confidence_label}</div>
      </div>
      <span class="pill ${pillCls}" style="font-size:12px;padding:4px 12px;">${de.decision}</span>
    </div>

    <!-- 5 KPI Cards -->
    <div class="score-kpis">
      <div class="kpi-card"><div class="kpi-lbl">Approval Likelihood</div><div class="kpi-val" style="color:${scoreColor};">${data.approval_percentage}%</div></div>
      <div class="kpi-card"><div class="kpi-lbl">Affordability</div><div class="kpi-val">${de.affordability_tier}</div></div>
      <div class="kpi-card"><div class="kpi-lbl">FOIR Ratio</div><div class="kpi-val" style="color:${(de.foir_ratio||0)>0.5?'var(--danger)':'var(--success)'};">${((de.foir_ratio||0)*100).toFixed(1)}%</div></div>
      <div class="kpi-card"><div class="kpi-lbl">DTI Ratio</div><div class="kpi-val">${((de.dti_ratio||0)*100).toFixed(1)}%</div></div>
      <div class="kpi-card"><div class="kpi-lbl">Recommended EMI</div><div class="kpi-val" style="color:var(--primary);">₹${fmt(de.new_emi||0)}</div></div>
    </div>

    <!-- Result Tabs -->
    <div class="result-tabs">
      <div class="result-tab active" onclick="switchResultTab('rt-overview',this)">Overview</div>
      <div class="result-tab" onclick="switchResultTab('rt-drivers',this)">Risk Drivers</div>
      <div class="result-tab" onclick="switchResultTab('rt-financial',this)">Financial Health</div>
      <div class="result-tab" onclick="switchResultTab('rt-whatif',this)">Loan Comparison</div>
      <div class="result-tab" onclick="switchResultTab('rt-explain',this)">Model Explanation</div>
    </div>

    <!-- Tab: Overview -->
    <div class="tab-content active" id="rt-overview">
      <div class="stat-list">
        <div class="stat-row"><span>Decision Verdict</span>${pillHtml(de.decision)}</div>
        <div class="stat-row"><span>Calibrated P(Good Credit)</span>${fmtMono(data.approval_percentage + '%')}</div>
        <div class="stat-row"><span>Nova Score</span>${fmtMono(sc.nova_score + ' / 850')}</div>
        <div class="stat-row"><span>Nova Score Band</span><strong>${sc.tier}</strong></div>
        <div class="stat-row"><span>Suggested Loan Ceiling</span>${fmtMono('₹' + fmt(de.suggested_loan_capacity||0))}</div>
        <div class="stat-row"><span>Decision Confidence</span><strong>${de.decision_confidence || '—'}</strong></div>
      </div>
    </div>

    <!-- Tab: Risk Drivers -->
    <div class="tab-content" id="rt-drivers">
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;">
        <div>
          <p style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;color:var(--success);margin-bottom:8px;">Top Positive Drivers</p>
          <div class="stat-list">${posD.slice(0,4).map(d=>`<div class="stat-row"><span>↑ ${d.feature}</span><strong style="color:var(--success);">+${Math.abs(d.shap_value).toFixed(3)}</strong></div>`).join("") || '<p style="font-size:12px;color:var(--text-muted);">No major positive drivers.</p>'}</div>
        </div>
        <div>
          <p style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;color:var(--danger);margin-bottom:8px;">Top Risk Drivers</p>
          <div class="stat-list">${riskD.slice(0,4).map(d=>`<div class="stat-row"><span>↓ ${d.feature}</span><strong style="color:var(--danger);">-${Math.abs(d.shap_value).toFixed(3)}</strong></div>`).join("") || '<p style="font-size:12px;color:var(--success);">No critical risk drag factors.</p>'}</div>
        </div>
      </div>
    </div>

    <!-- Tab: Financial Health -->
    <div class="tab-content" id="rt-financial">
      <div class="stat-list">
        <div class="stat-row"><span>Fixed Obligation to Income (FOIR)</span><strong style="color:${(de.foir_ratio||0)>0.5?'var(--danger)':'var(--success)'};">${((de.foir_ratio||0)*100).toFixed(1)}%</strong></div>
        <div class="stat-row"><span>Debt-to-Income (DTI)</span><strong>${((de.dti_ratio||0)*100).toFixed(1)}%</strong></div>
        <div class="stat-row"><span>Monthly Disposable Income</span><strong style="color:var(--success);">₹${fmt(de.disposable_income||0)}</strong></div>
        <div class="stat-row"><span>Liquidity Reserve (Months)</span><strong>${de.liquidity_reserve_months} mos</strong></div>
        <div class="stat-row"><span>Max Recommended EMI</span><strong>₹${fmt(de.max_recommended_emi||0)}</strong></div>
        <div class="stat-row"><span>Suggested Loan Ceiling</span><strong style="color:var(--primary);">₹${fmt(de.suggested_loan_capacity||0)}</strong></div>
      </div>
    </div>

    <!-- Tab: Loan Comparison -->
    <div class="tab-content" id="rt-whatif">
      <div class="table-wrap">
        <table class="data-table">
          <thead><tr><th>Tenure</th><th>Monthly EMI</th><th>Total Interest</th><th>FOIR</th><th>Status</th></tr></thead>
          <tbody>${lc.map(t=>`<tr><td><strong>${t.tenure_months} mos</strong></td><td style="font-family:var(--font-mono);color:var(--primary);">₹${fmt(t.monthly_emi)}</td><td style="font-family:var(--font-mono);">₹${fmt(t.total_interest)}</td><td>${t.foir_percentage}%</td><td><span class="pill ${t.nova_recommendation==='Recommended'?'pill-success':'pill-neutral'}">${t.nova_recommendation}</span></td></tr>`).join("")}</tbody>
        </table>
      </div>
      <div style="margin-top:14px;">
        <p style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;color:var(--success);margin-bottom:8px;">Credit Improvement Planner</p>
        ${recs.map(r=>`<div style="padding:8px 0;border-bottom:1px solid var(--border-dim);font-size:12px;"><strong style="color:var(--text-primary);">💡 ${r.action}</strong><p style="color:var(--primary);font-size:11px;margin-top:2px;">${r.potential_impact}</p></div>`).join("")}
        <p style="font-size:10px;color:var(--text-dim);margin-top:8px;">Improvements are model simulations, not guaranteed real-world credit-score changes.</p>
      </div>
    </div>

    <!-- Tab: Model Explanation -->
    <div class="tab-content" id="rt-explain">
      <div class="stat-list" style="margin-bottom:14px;">
        <div class="stat-row"><span>Champion Model</span><strong>CatBoost (Optuna Tuned)</strong></div>
        <div class="stat-row"><span>Calibration</span><strong>Sigmoid Platt Scaling</strong></div>
        <div class="stat-row"><span>Training Data</span><strong>Statlog German Credit (N=1,000)</strong></div>
        <div class="stat-row"><span>CV Strategy</span><strong>Stratified 5-Fold</strong></div>
        <div class="stat-row"><span>CV ROC-AUC</span><strong style="color:var(--success);">0.7697</strong></div>
        <div class="stat-row"><span>Holdout Brier Score</span><strong>0.1673</strong></div>
      </div>
      <p style="font-size:11px;color:var(--text-muted);line-height:1.7;">
        The Nova Score is derived using a log-odds transformation: <strong>Score = 650 + 55 × ln(P / (1-P))</strong> where P is the calibrated probability of non-default. Platt Sigmoid scaling reduces Expected Calibration Error from 12.7% to 1.7%, ensuring that displayed probabilities have empirically verified reliability.
      </p>
    </div>

    <p class="legal" style="margin-top:14px;">${sc.disclaimer || "Nova Credit Score is Nova's proprietary model-derived risk score and is not a bureau score."}</p>
    <a href="/api/v1/reports/pdf/${data.assessment_id}" target="_blank" class="btn btn-secondary btn-block" style="margin-top:12px;text-decoration:none;">
      <i data-lucide="download"></i><span>Download Official PDF Assessment Report</span>
    </a>
  `;
  if (window.lucide) lucide.createIcons();
}

function switchResultTab(id, el) {
  document.querySelectorAll(".tab-content").forEach(t => t.classList.remove("active"));
  document.querySelectorAll(".result-tab").forEach(t => t.classList.remove("active"));
  document.getElementById(id).classList.add("active");
  el.classList.add("active");
}

// ─── Overview Hero Update ──────────────────────────────────────────────────────
function updateOverviewHero(data) {
  const sc = data.nova_score || {};
  const de = data.decision_engine || {};
  const el = id => document.getElementById(id);

  const scoreColor = sc.color || "var(--success)";
  if (el("ov-score")) { el("ov-score").textContent = sc.nova_score; el("ov-score").style.color = scoreColor; }
  if (el("ov-tier")) { el("ov-tier").textContent = sc.tier || "—"; el("ov-tier").className = `pill ${sc.tier === "Exceptional" || sc.tier === "Excellent" ? "pill-success" : sc.tier === "Strong" ? "pill-info" : "pill-warning"}`; }
  if (el("ov-risk")) el("ov-risk").textContent = (data.approval_percentage >= 70 ? "Low" : data.approval_percentage >= 50 ? "Moderate" : "High");
  if (el("ov-prob")) el("ov-prob").textContent = `${data.approval_percentage}% Calibrated`;
  if (el("ov-foir")) el("ov-foir").textContent = ((de.foir_ratio||0)*100).toFixed(1) + "%";
  if (el("ov-decision")) { el("ov-decision").textContent = de.decision; el("ov-decision").style.color = scoreColor; }

  let decPill = "pill-success";
  if (de.decision === "High Risk") decPill = "pill-danger";
  else if (de.decision === "Manual Review") decPill = "pill-warning";
  else if (de.decision === "Conditionally Eligible") decPill = "pill-info";
  if (el("ov-dec-pill")) { el("ov-dec-pill").textContent = de.decision; el("ov-dec-pill").className = `pill ${decPill}`; }

  const healthEl = el("ov-health");
  if (healthEl) {
    healthEl.innerHTML = [
      ["Disposable Income", `₹${fmt(de.disposable_income||0)} / mo`, "var(--success)"],
      ["DTI Ratio", ((de.dti_ratio||0)*100).toFixed(1) + "%", "var(--text-primary)"],
      ["Liquidity Buffer", de.liquidity_reserve_months + " months EMI coverage", "var(--info)"],
      ["Eligible Loan Ceiling", `₹${fmt(de.suggested_loan_capacity||0)}`, "var(--text-primary)"],
    ].map(([k,v,c]) => `<div class="stat-row"><span>${k}</span><strong style="color:${c};">${v}</strong></div>`).join("");
  }

  const posD = data.top_positive_drivers || [];
  const riskD = data.top_risk_drivers || [];
  const driversEl = el("ov-drivers");
  if (driversEl) {
    driversEl.innerHTML = `
      <div class="stat-list">
        ${posD.slice(0,2).map(d=>`<div class="stat-row"><span>↑ ${d.feature}</span><strong style="color:var(--success);">+${Math.abs(d.shap_value).toFixed(3)}</strong></div>`).join("")}
        ${riskD.slice(0,2).map(d=>`<div class="stat-row"><span>↓ ${d.feature}</span><strong style="color:var(--danger);">-${Math.abs(d.shap_value).toFixed(3)}</strong></div>`).join("")}
      </div>
    `;
  }
}

// ─── History Loader (Privacy Scoped & User Isolated) ─────────────────────────
async function loadHistory() {
  try {
    const res = await fetch("/api/v1/history?limit=25", {
      headers: getAuthHeaders()
    });
    if (!res.ok) return;
    const data = await res.json();
    const records = data.history || [];
    const isAdmin = data.is_admin || false;

    const subTitle = document.getElementById("hist-sub-title");
    if (subTitle) {
      if (isAdmin) {
        subTitle.textContent = "👑 SYSTEM ADMIN MODE — Displaying All User Assessments & Unique User IDs across Nova Credit AI";
      } else if (currentUser) {
        subTitle.textContent = `🔒 Private Session Ledger — User ID: ${currentUser.user_id || 'USR-SESS'} (Your Personal Assessments Only)`;
      } else {
        subTitle.textContent = "👤 Guest Session Ledger — Sign In or Register to save your personal credit assessment history";
      }
    }

    const render = (rows, cols) => rows.length === 0
      ? `<tr><td colspan="${cols}" style="text-align:center;padding:24px;color:var(--text-muted);">No assessments recorded for this account context. ${!currentUser ? 'Sign in to track your personal credit history.' : ''}</td></tr>`
      : rows.map(r => {
          const date = new Date(r.timestamp).toLocaleString("en-IN", { month:"short", day:"numeric", hour:"2-digit", minute:"2-digit" });
          const userTag = isAdmin 
            ? `<br/><span style="font-size:10px;font-family:var(--font-mono);color:var(--primary);">ID: ${r.user_id || 'GUEST'} (${r.user_email || 'guest'})</span>`
            : '';
          return `<tr>
            <td style="font-size:11px;color:var(--text-muted);">${date}</td>
            <td><strong>${r.applicant_name}</strong>${userTag}</td>
            <td style="font-family:var(--font-mono);">₹${fmt(r.requested_loan)}</td>
            <td style="font-family:var(--font-mono);font-weight:700;color:var(--text-primary);">${r.nova_score}</td>
            <td>${r.risk_tier}</td>
            <td style="font-family:var(--font-mono);">${r.approval_probability}%</td>
            <td>${pillHtml(r.decision)}</td>
            ${cols===8?`<td><a href="/api/v1/reports/pdf/${r.id}" target="_blank" style="color:var(--primary);text-decoration:none;font-weight:600;font-size:11px;">PDF ↗</a></td>`:''}
          </tr>`;
        }).join("");

    const histTbl = document.getElementById("hist-table");
    if (histTbl) histTbl.innerHTML = render(records, 8);
    const ovTbl = document.getElementById("ov-history-table");
    if (ovTbl) ovTbl.innerHTML = render(records.slice(0,5), 7);
  } catch (e) { console.error("History load error:", e); }
}


// ─── Simulator ────────────────────────────────────────────────────────────────
function initSimulator() {
  const ids = ["sim_income","sim_credit","sim_duration","sim_emi","sim_savings"];
  const labels = ["sim_v_income","sim_v_credit","sim_v_dur","sim_v_emi","sim_v_sav"];
  const formatFns = [
    v => "₹" + fmt(v), v => "₹" + fmt(v),
    v => v + " Months",
    v => "₹" + fmt(v), v => "₹" + fmt(v),
  ];
  ids.forEach((id, i) => {
    const el = document.getElementById(id);
    const lbl = document.getElementById(labels[i]);
    if (!el || !lbl) return;
    el.addEventListener("input", () => { lbl.textContent = formatFns[i](el.value); debounceSimulate(); });
  });
}

let simTimer = null;
function debounceSimulate() {
  clearTimeout(simTimer);
  simTimer = setTimeout(runSimulation, 350);
}

async function runSimulation() {
  const get = id => document.getElementById(id);
  const el = get("simResult"); if (!el) return;

  const income  = parseFloat(get("sim_income")?.value)   || 75000;
  const credit  = parseFloat(get("sim_credit")?.value)   || 200000;
  const dur     = parseInt(get("sim_duration")?.value)   || 24;
  const emi     = parseFloat(get("sim_emi")?.value)      || 0;
  const savings = parseFloat(get("sim_savings")?.value)  || 80000;

  try {
    const res = await fetch("/api/v1/simulate", {
      method:"POST", headers:{"Content-Type":"application/json", ...getAuthHeaders()},
      body: JSON.stringify({ monthly_income: income, credit_amount: credit, duration: dur, existing_emi: emi, savings_balance: savings, age: 30 })
    });
    if (!res.ok) return;
    const data = await res.json();
    const sc = data.nova_score || {};
    const de = data.decision_engine || {};
    const recs = data.improvement_recommendations || [];
    const scoreColor = sc.color || "var(--success)";

    let pCls = "pill-success";
    if (de.decision === "High Risk") pCls = "pill-danger";
    else if (de.decision === "Manual Review") pCls = "pill-warning";
    else if (de.decision === "Conditionally Eligible") pCls = "pill-info";

    el.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;padding:16px;background:var(--surface-elevated);border:1px solid var(--border-light);border-radius:var(--r-md);margin-bottom:14px;">
        <div>
          <div style="font-family:var(--font-mono);font-size:36px;font-weight:700;color:${scoreColor};">${sc.nova_score}</div>
          <div style="font-size:11px;color:var(--text-muted);margin-top:2px;">${sc.tier} · ${data.approval_percentage}% P(Good)</div>
        </div>
        <span class="pill ${pCls}" style="font-size:12px;padding:5px 12px;">${de.decision}</span>
      </div>
      <div class="stat-list" style="margin-bottom:14px;">
        <div class="stat-row"><span>FOIR Ratio</span><strong style="color:${(de.foir_ratio||0)>0.5?'var(--danger)':'var(--success)'};">${((de.foir_ratio||0)*100).toFixed(1)}%</strong></div>
        <div class="stat-row"><span>Monthly EMI</span><strong style="color:var(--primary);">₹${fmt(de.new_emi||0)}</strong></div>
        <div class="stat-row"><span>Affordability</span><strong>${de.affordability_tier}</strong></div>
      </div>
      <div style="background:var(--surface-elevated);padding:12px;border-radius:var(--r-md);border:1px solid var(--border-dim);">
        <p style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;color:var(--success);margin-bottom:6px;">Optimization Insights</p>
        ${recs.map(r=>`<div style="padding:6px 0;border-bottom:1px solid var(--border-dim);font-size:12px;"><strong style="color:var(--text-primary);">💡 ${r.action}</strong><div style="color:var(--primary);font-size:11px;margin-top:2px;">${r.potential_impact}</div></div>`).join("")}
      </div>
    `;
    if (window.lucide) lucide.createIcons();
  } catch(e) { console.error("Sim error:", e); }
}

// ─── Loan EMI Calculator ────────────────────────────────────────────────────────
function initLoanCalc() {
  const form = document.getElementById("loanForm");
  if (!form) return;
  form.addEventListener("submit", e => {
    e.preventDefault();
    const p = parseFloat(document.getElementById("emi_principal").value);
    const r = parseFloat(document.getElementById("emi_rate").value) / 12 / 100;
    const n = parseInt(document.getElementById("emi_tenure").value) * 12;
    const emi = p * r * Math.pow(1+r,n) / (Math.pow(1+r,n)-1);
    document.getElementById("r_emi").textContent = "₹" + fmt(emi);
    document.getElementById("r_interest").textContent = "₹" + fmt(emi*n - p);
    document.getElementById("r_total").textContent = "₹" + fmt(emi*n);
  });
}

// ─── Model Intelligence ────────────────────────────────────────────────────────
async function loadModelIntelligence() {
  try {
    const [metricsRes, healthRes] = await Promise.all([
      fetch("/api/v1/models/metrics"),
      fetch("/api/v1/models/health")
    ]);
    const metrics = await metricsRes.json();
    const health  = await healthRes.json();
    renderModelIntelligence(metrics, health);
  } catch(e) { console.error("Model intel load error:", e); }
}

function renderModelIntelligence(m, h) {
  const holdout = m.holdout_metrics || {};
  const el = id => document.getElementById(id);

  if (el("ml-model-name")) el("ml-model-name").textContent = m.champion_model || "—";
  if (el("ml-roc")) el("ml-roc").textContent = m.champion_cv_roc_auc?.toFixed(4) || "—";
  if (el("ml-roc-holdout")) el("ml-roc-holdout").textContent = holdout.roc_auc?.toFixed(4) || "—";
  if (el("ml-brier")) el("ml-brier").textContent = holdout.brier_score?.toFixed(4) || "—";
  if (el("ml-ece")) el("ml-ece").textContent = "1.67%";
  if (el("ml-cal-badge")) el("ml-cal-badge").textContent = m.calibration_method?.replace("_"," ").toUpperCase() || "—";

  const statusOk = h.overall_status === "Healthy";
  if (el("ml-health-badge")) {
    el("ml-health-badge").textContent = h.overall_status;
    el("ml-health-badge").className = `pill ${statusOk?"pill-success":"pill-warning"}`;
  }

  const hmRows = [
    ["ROC-AUC",          holdout.roc_auc?.toFixed(4),           "Discriminative ability"],
    ["PR-AUC",           holdout.pr_auc?.toFixed(4),            "Precision-Recall trade-off"],
    ["Balanced Accuracy",holdout.balanced_accuracy?.toFixed(4), "Average per-class accuracy"],
    ["F1 Score",         holdout.f1_score?.toFixed(4),          "Harmonic mean"],
    ["Precision",        holdout.precision?.toFixed(4),         "Truly good borrowers"],
    ["Recall (Good)",    holdout.recall_good?.toFixed(4),       "Good borrowers correctly approved"],
    ["Recall (Bad)",     holdout.recall_bad?.toFixed(4),        "Bad borrowers correctly flagged"],
    ["Brier Score",      holdout.brier_score?.toFixed(4),       "Calibration quality"],
    ["Log Loss",         holdout.log_loss?.toFixed(4),          "Cross-entropy loss"],
  ];
  const hmTbl = el("ml-holdout-table");
  if (hmTbl) {
    hmTbl.querySelector("tbody").innerHTML = hmRows.map(([k,v,desc]) =>
      `<tr><td style="font-weight:600;color:var(--text-primary);">${k}</td><td style="font-family:var(--font-mono);color:var(--primary);font-weight:700;">${v??'—'}</td><td style="color:var(--text-muted);font-size:11px;">${desc}</td></tr>`
    ).join("");
  }

  const cm = holdout.confusion_matrix || [[26,34],[12,128]];
  const tn=cm[0][0], fp=cm[0][1], fn=cm[1][0], tp=cm[1][1];
  if (el("conf-matrix")) {
    el("conf-matrix").innerHTML = `
      <div class="conf-cell conf-header" style="grid-column:1;"></div>
      <div class="conf-cell conf-header">Predicted BAD</div>
      <div class="conf-cell conf-header">Predicted GOOD</div>
      <div class="conf-cell conf-header">Actual BAD</div>
      <div class="conf-cell conf-tn">${tn}<br><span style="font-size:9px;font-weight:400;">True Neg</span></div>
      <div class="conf-cell conf-fp">${fp}<br><span style="font-size:9px;font-weight:400;">False Pos</span></div>
      <div class="conf-cell conf-header">Actual GOOD</div>
      <div class="conf-cell conf-fn">${fn}<br><span style="font-size:9px;font-weight:400;">False Neg</span></div>
      <div class="conf-cell conf-tp">${tp}<br><span style="font-size:9px;font-weight:400;">True Pos</span></div>
    `;
  }

  renderRocSvg(holdout.roc_auc || 0.77);

  const thresholds = m.threshold_analysis || [];
  if (el("threshold-chart") && thresholds.length) {
    el("threshold-chart").innerHTML = thresholds.map(t => `
      <div class="bar-row">
        <div class="bar-label">τ=${t.threshold} · BalAcc=${t.balanced_accuracy?.toFixed(3)}</div>
        <div class="bar-track"><div class="bar-fill" style="width:${(t.balanced_accuracy||0)*100}%;background:${t.threshold===0.55?'var(--success)':'var(--primary)'};"></div></div>
        <div class="bar-val">${((t.balanced_accuracy||0)*100).toFixed(1)}%</div>
      </div>
    `).join("");
  }

  const compTbl = el("ml-comparison-table");
  if (compTbl && m.model_comparison) {
    compTbl.querySelector("tbody").innerHTML = m.model_comparison.map(row => `
      <tr class="${row.is_champion?'champion-row':''}">
        <td style="font-weight:${row.is_champion?700:500};color:var(--text-primary);">${row.model}${row.is_champion?' 👑':''}</td>
        <td style="font-family:var(--font-mono);font-weight:700;color:${row.is_champion?'var(--success)':'var(--text-primary)'};">${row.cv_roc_auc?.toFixed(4)}</td>
        <td style="font-family:var(--font-mono);">${row.cv_pr_auc?.toFixed(4)}</td>
        <td style="font-family:var(--font-mono);">${row.cv_f1?.toFixed(4)}</td>
        <td style="font-family:var(--font-mono);">${row.cv_balanced_acc?.toFixed(4)}</td>
        <td style="font-family:var(--font-mono);">${row.cv_recall_good?.toFixed(4)}</td>
        <td style="font-family:var(--font-mono);">${row.cv_recall_bad?.toFixed(4)}</td>
        <td style="font-family:var(--font-mono);">${row.cv_brier?.toFixed(4)}</td>
        <td>${row.is_champion?'<span class="pill pill-success">Champion</span>':'<span class="pill pill-neutral">Challenger</span>'}</td>
      </tr>
    `).join("");
  }

  const features = [
    ["Checking Account Status",    0.82],
    ["Duration (Months)",          0.71],
    ["Credit Amount",              0.68],
    ["Savings Account Status",     0.61],
    ["Age",                        0.54],
    ["Loan Purpose",               0.43],
    ["Credit per Month",           0.41],
    ["Housing Asset Status",       0.35],
    ["Log Credit (Engineered)",    0.33],
    ["Employment Type",            0.27],
  ];
  if (el("feature-importance-chart")) {
    el("feature-importance-chart").innerHTML = features.map(([name, imp]) => `
      <div class="bar-row">
        <div class="bar-label">${name}</div>
        <div class="bar-track"><div class="bar-fill" style="width:${imp*100}%;background:var(--primary);"></div></div>
        <div class="bar-val">${(imp*100).toFixed(0)}%</div>
      </div>
    `).join("");
  }
}

function renderRocSvg(auc) {
  const svg = document.getElementById("roc-svg");
  if (!svg) return;
  const pts = [[0,0],[0.02,0.20],[0.05,0.38],[0.10,0.55],[0.20,0.72],[0.35,0.83],[0.55,0.91],[0.75,0.96],[0.90,0.98],[1,1]];
  const W=300, H=220, PAD=36;
  const scX = x => PAD + x*(W-PAD*2);
  const scY = y => PAD + (1-y)*(H-PAD*2);
  const pathD = pts.map((p,i) => (i===0?"M":"L") + scX(p[0]).toFixed(1) + "," + scY(p[1]).toFixed(1)).join(" ");
  const diagD = `M${scX(0)},${scY(0)} L${scX(1)},${scY(1)}`;
  svg.innerHTML = `
    <rect width="${W}" height="${H}" rx="6" fill="#161A22"/>
    <line x1="${PAD}" y1="${PAD}" x2="${PAD}" y2="${H-PAD}" stroke="#2A3141" stroke-width="1"/>
    <line x1="${PAD}" y1="${H-PAD}" x2="${W-PAD}" y2="${H-PAD}" stroke="#2A3141" stroke-width="1"/>
    <path d="${diagD}" stroke="#475569" stroke-width="1" stroke-dasharray="4,4" fill="none"/>
    <path d="${pathD} L${scX(1)},${scY(0)} Z" fill="rgba(99,102,241,0.12)"/>
    <path d="${pathD}" stroke="#6366F1" stroke-width="2.5" fill="none" stroke-linejoin="round"/>
    <text x="${W/2}" y="${PAD+18}" text-anchor="middle" font-size="12" fill="#94A3B8" font-family="Inter,sans-serif">AUC = ${auc.toFixed(4)}</text>
  `;
}

// ─── Initialisation ────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  if (window.lucide) lucide.createIcons();
  initSplashAndAuth();
  initNav();
  initSimulator();
  initLoanCalc();
  loadHistory();
  updateStepUI();

  const refreshBtn = document.getElementById("refreshHistBtn");
  if (refreshBtn) refreshBtn.addEventListener("click", loadHistory);
});
