"use strict";

// ─── Global State & Utilities ──────────────────────────────────────────────────
let currentUser = null;
let currentAuthMode = "login";
let userSearchTimer = null;

const fmt = (n, dec = 0) => Number(n || 0).toLocaleString("en-IN", { maximumFractionDigits: dec });
const fmtPct = (n) => ((n || 0) * 100).toFixed(1) + "%";

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

function actionBadgeHtml(action) {
  const map = {
    "account_created":            "pill-success",
    "login_success":              "pill-info",
    "login_failed":               "pill-danger",
    "logout":                     "pill-neutral",
    "password_changed":           "pill-warning",
    "credit_assessment_created":  "pill-primary",
    "what_if_simulation_run":     "pill-info",
    "report_generated":           "pill-success",
    "profile_updated":            "pill-neutral",
    "user_activated":             "pill-success",
    "user_deactivated":           "pill-danger",
  };
  const cls = map[action] || "pill-neutral";
  return `<span class="pill ${cls}">${action}</span>`;
}

function getAuthHeaders() {
  const token = localStorage.getItem("nova_token");
  return token ? { "Authorization": `Bearer ${token}` } : {};
}

// ─── SPA Client Router & Route Protection Guards ──────────────────────────────

function navigateTo(path) {
  window.history.pushState(null, "", path);
  routeResolver();
}

window.addEventListener("popstate", routeResolver);

async function routeResolver() {
  const rawPath = window.location.pathname;
  let path = rawPath.toLowerCase();
  if (path === "/" || path === "/login" || path === "") {
    path = "/login";
  }

  // Splash Screen Intro Animation dismissal
  setTimeout(() => {
    const splash = document.getElementById("splash-screen");
    if (splash) splash.classList.add("fade-out");
  }, 1200);

  // Validate stored session token with backend API
  const token = localStorage.getItem("nova_token");
  if (token) {
    try {
      const res = await fetch("/api/v1/auth/me", { headers: { "Authorization": `Bearer ${token}` } });
      if (res.ok) {
        currentUser = await res.json();
      } else {
        currentUser = null;
        localStorage.removeItem("nova_token");
        localStorage.removeItem("nova_user");
      }
    } catch (e) {
      console.warn("Session validation error:", e);
    }
  } else {
    currentUser = null;
  }

  const authGateEl = document.getElementById("view-auth");
  const appShellEl = document.getElementById("appShell");

  // If unauthenticated: redirect to /login and lock app shell
  if (!currentUser) {
    if (authGateEl) authGateEl.style.display = "flex";
    if (appShellEl) appShellEl.style.display = "none";
    return;
  }

  // If authenticated: reveal app shell & hide login gate
  if (authGateEl) authGateEl.style.display = "none";
  if (appShellEl) appShellEl.style.display = "flex";

  updateUserHeaderUI();

  // Admin Route Protection Guard: Only ADMIN role can access /admin/*
  if (path.startsWith("/admin")) {
    if (currentUser.role.upper !== "ADMIN" && currentUser.role !== "ADMIN") {
      alert("Access Denied: Administrative privileges required.");
      navigateTo("/app/dashboard");
      return;
    }
    setupAdminWorkspaceLayout();
    resolveAdminRoute(path);
  } else {
    setupUserWorkspaceLayout();
    resolveUserRoute(path);
  }

  // Refresh Lucide Icons
  if (window.lucide) window.lucide.createIcons();
}

function setupUserWorkspaceLayout() {
  const userNav = document.getElementById("navGroupUser");
  const adminNav = document.getElementById("navGroupAdmin");
  const brandTitle = document.getElementById("brandTitleText");
  const brandBadge = document.getElementById("brandRoleBadge");

  if (userNav) userNav.style.display = "block";
  if (adminNav) adminNav.style.display = "none";
  if (brandTitle) brandTitle.textContent = "NOVA CREDIT";
  if (brandBadge) {
    brandBadge.textContent = "v2.2";
    brandBadge.className = "brand-ver";
  }
}

function setupAdminWorkspaceLayout() {
  const userNav = document.getElementById("navGroupUser");
  const adminNav = document.getElementById("navGroupAdmin");
  const brandTitle = document.getElementById("brandTitleText");
  const brandBadge = document.getElementById("brandRoleBadge");

  if (userNav) userNav.style.display = "none";
  if (adminNav) adminNav.style.display = "block";
  if (brandTitle) brandTitle.textContent = "NOVA ADMIN";
  if (brandBadge) {
    brandBadge.textContent = "ADMIN 👑";
    brandBadge.className = "brand-ver pill pill-warning";
  }
}

function resolveUserRoute(path) {
  hideAllSections();
  const pageTitle = document.getElementById("pageTitle");

  if (path === "/app/credit-assessment") {
    showSection("view-user-assessment");
    if (pageTitle) pageTitle.textContent = "Credit Assessment Intake";
    loadAssessmentWizard();
  } else if (path === "/app/what-if") {
    showSection("view-user-what-if");
    if (pageTitle) pageTitle.textContent = "What-If Risk Simulator";
    loadWhatIfSimulator();
  } else if (path === "/app/history") {
    showSection("view-user-history");
    if (pageTitle) pageTitle.textContent = "Assessment History Ledger";
    loadHistory();
  } else if (path === "/app/loans") {
    showSection("view-user-loans");
    if (pageTitle) pageTitle.textContent = "Loan Amortization & Calculator";
    loadLoanCalculator();
  } else if (path === "/app/investments") {
    showSection("view-user-investments");
    if (pageTitle) pageTitle.textContent = "Wealth & Fund Explorer";
    loadFundExplorer();
  } else if (path === "/app/reports") {
    showSection("view-user-reports");
    if (pageTitle) pageTitle.textContent = "PDF Underwriting Reports";
    loadUserReports();
  } else if (path === "/app/profile") {
    showSection("view-user-profile");
    if (pageTitle) pageTitle.textContent = "Account & Financial Profile";
    loadUserProfile();
  } else if (path === "/app/settings") {
    showSection("view-user-settings");
    if (pageTitle) pageTitle.textContent = "Security & Password Settings";
  } else {
    // Default: /app/dashboard
    showSection("view-user-dashboard");
    if (pageTitle) pageTitle.textContent = "Financial Overview";
    loadUserDashboard();
  }
}

function resolveAdminRoute(path) {
  hideAllSections();
  const pageTitle = document.getElementById("pageTitle");

  if (path === "/admin/users") {
    showSection("view-admin-users");
    if (pageTitle) pageTitle.textContent = "User Accounts Management";
    loadAdminUsers();
  } else if (path === "/admin/activity") {
    showSection("view-admin-activity");
    if (pageTitle) pageTitle.textContent = "System Activity Audit Trail";
    loadAdminActivityLogs();
  } else if (path === "/admin/assessments") {
    showSection("view-admin-assessments");
    if (pageTitle) pageTitle.textContent = "Global Credit Underwriting Log";
    loadAdminAssessments();
  } else if (path === "/admin/models") {
    showSection("view-admin-models");
    if (pageTitle) pageTitle.textContent = "Champion Model Health & Diagnostics";
    loadAdminModels();
  } else if (path === "/admin/system") {
    showSection("view-admin-system");
    if (pageTitle) pageTitle.textContent = "System Diagnostic Overview";
  } else {
    // Default: /admin/dashboard
    showSection("view-admin-dashboard");
    if (pageTitle) pageTitle.textContent = "System Operational Dashboard";
    loadAdminDashboard();
  }
}

function hideAllSections() {
  document.querySelectorAll(".view-section").forEach(s => s.classList.remove("active"));
}

function showSection(id) {
  const el = document.getElementById(id);
  if (el) el.classList.add("active");
}

function toggleMobileSidebar() {
  const sidebar = document.getElementById("appSidebar");
  const overlay = document.getElementById("mobileOverlay");
  if (sidebar) sidebar.classList.toggle("mobile-open");
  if (overlay) overlay.classList.toggle("active");
}

// ─── Authentication Gate Handlers ──────────────────────────────────────────────

function switchAuthMode(mode) {
  currentAuthMode = mode;
  const btnLogin = document.getElementById("btnTabLogin");
  const btnReg = document.getElementById("btnTabRegister");
  const nameGrp = document.getElementById("fieldGroupName");
  const btnText = document.getElementById("btnAuthText");
  const forgotLink = document.getElementById("linkForgotPass");
  const headerTitle = document.getElementById("authHeaderTitle");
  const headerSub = document.getElementById("authHeaderSub");
  const chkText = document.getElementById("chkRememberText");

  hideAuthAlert();

  if (mode === "login") {
    if (btnLogin) btnLogin.classList.add("active");
    if (btnReg) btnReg.classList.remove("active");
    if (nameGrp) nameGrp.style.display = "none";
    if (btnText) btnText.textContent = "Sign In to Workspace";
    if (forgotLink) forgotLink.style.display = "inline";
    if (headerTitle) headerTitle.textContent = "Welcome back";
    if (headerSub) headerSub.textContent = "Sign in to continue to your workspace";
    if (chkText) chkText.textContent = "Remember me for 30 days";
  } else {
    if (btnReg) btnReg.classList.add("active");
    if (btnLogin) btnLogin.classList.remove("active");
    if (nameGrp) nameGrp.style.display = "block";
    if (btnText) btnText.textContent = "Create Workspace Account";
    if (forgotLink) forgotLink.style.display = "none";
    if (headerTitle) headerTitle.textContent = "Create your account";
    if (headerSub) headerSub.textContent = "Get started with Nova Credit AI workspace";
    if (chkText) chkText.textContent = "I agree to the Terms of Service & Privacy Policy";
  }
  if (window.lucide) window.lucide.createIcons();
}

function togglePasswordVisibility(inputId, btnEl) {
  const input = document.getElementById(inputId);
  if (!input) return;
  if (input.type === "password") {
    input.type = "text";
    btnEl.innerHTML = '<i data-lucide="eye-off"></i>';
  } else {
    input.type = "password";
    btnEl.innerHTML = '<i data-lucide="eye"></i>';
  }
  if (window.lucide) window.lucide.createIcons();
}

function toggleForgotPasswordView(show) {
  const mainForm = document.getElementById("authMainForm");
  const forgotForm = document.getElementById("forgotPassForm");
  if (show) {
    if (mainForm) mainForm.style.display = "none";
    if (forgotForm) forgotForm.style.display = "block";
  } else {
    if (mainForm) mainForm.style.display = "block";
    if (forgotForm) forgotForm.style.display = "none";
  }
}

function showAuthAlert(msg, isSuccess = false) {
  const alertEl = document.getElementById("authAlert");
  if (!alertEl) return;
  alertEl.style.display = "block";
  alertEl.className = isSuccess ? "auth-alert-banner success" : "auth-alert-banner error";
  alertEl.textContent = msg;
}

function hideAuthAlert() {
  const alertEl = document.getElementById("authAlert");
  if (alertEl) alertEl.style.display = "none";
}

async function handleAuthSubmit(e) {
  e.preventDefault();
  hideAuthAlert();

  const email = document.getElementById("inputAuthEmail").value.trim();
  const password = document.getElementById("inputAuthPassword").value.trim();
  const name = document.getElementById("inputAuthName")?.value.trim() || "";

  if (!email || !password) {
    showAuthAlert("Please provide email and password.");
    return;
  }

  const endpoint = currentAuthMode === "login" ? "/api/v1/auth/login" : "/api/v1/auth/register";
  const body = currentAuthMode === "login"
    ? { email, password }
    : { email, password, full_name: name || email.split("@")[0] };

  const submitBtn = document.getElementById("btnAuthSubmit");
  if (submitBtn) submitBtn.disabled = true;

  try {
    const res = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Authentication failed.");
    }

    localStorage.setItem("nova_token", data.access_token);
    currentUser = {
      user_id: data.user_id,
      email: data.email,
      full_name: data.full_name,
      role: data.role,
    };
    localStorage.setItem("nova_user", JSON.stringify(currentUser));

    // Redirect based on role
    if (currentUser.role.toUpperCase() === "ADMIN") {
      navigateTo("/admin/dashboard");
    } else {
      navigateTo("/app/dashboard");
    }
  } catch (err) {
    showAuthAlert(err.message);
  } finally {
    if (submitBtn) submitBtn.disabled = false;
  }
}

async function handleForgotPasswordSubmit(e) {
  e.preventDefault();
  hideAuthAlert();
  const email = document.getElementById("inputForgotEmail").value.trim();
  if (!email) return;

  try {
    const res = await fetch("/api/v1/auth/forgot-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });
    const data = await res.json();
    showAuthAlert(data.message || "Password reset instructions dispatched.", true);
    setTimeout(() => toggleForgotPasswordView(false), 2500);
  } catch (err) {
    showAuthAlert("Password recovery request failed.");
  }
}

async function handleLogout() {
  try {
    await fetch("/api/v1/auth/logout", {
      method: "POST",
      headers: getAuthHeaders(),
    });
  } catch (e) {}

  localStorage.removeItem("nova_token");
  localStorage.removeItem("nova_user");
  currentUser = null;
  navigateTo("/login");
}

function fillAdminDemo() {
  document.getElementById("inputAuthEmail").value = "admin@novacredit.ai";
  document.getElementById("inputAuthPassword").value = "AdminSecurePassword2026!";
  switchAuthMode("login");
}

function updateUserHeaderUI() {
  if (!currentUser) return;
  const avatarEl = document.getElementById("userAvatar");
  const nameEl = document.getElementById("userName");
  const roleEl = document.getElementById("userRoleBadge");
  const topUserId = document.getElementById("topbarUserId");

  const initials = (currentUser.full_name || currentUser.email).split(" ").map(n => n[0]).join("").toUpperCase().slice(0, 2);
  if (avatarEl) avatarEl.textContent = initials || "U";
  if (nameEl) nameEl.textContent = currentUser.full_name || currentUser.email;

  const isAdmin = currentUser.role.toUpperCase() === "ADMIN";
  if (roleEl) {
    roleEl.textContent = isAdmin ? "ADMIN 👑" : "USER 🔒";
    roleEl.className = isAdmin ? "pill pill-warning" : "pill pill-info";
  }
  if (topUserId) {
    topUserId.style.display = "inline-flex";
    topUserId.innerHTML = isAdmin
      ? `<span class="pill pill-warning">👑 Admin ID: ${currentUser.user_id || 'ADMIN'}</span>`
      : `<span class="pill pill-info">🔒 User ID: ${currentUser.user_id || 'USER'}</span>`;
  }
}

// ─── User Module Controllers (/app/*) ──────────────────────────────────────────

async function loadUserDashboard() {
  loadHistory();
  try {
    const res = await fetch("/api/v1/user/profile", { headers: getAuthHeaders() });
    if (res.ok) {
      const data = await res.json();
      const fp = data.financial_profile;
      if (fp) {
        document.getElementById("profSumIncome").textContent = "₹" + fmt(fp.monthly_income);
        document.getElementById("profSumEmi").textContent = "₹" + fmt(fp.existing_emi);
        document.getElementById("profSumSavings").textContent = "₹" + fmt(fp.savings_balance);
        document.getElementById("profSumHousing").textContent = fp.housing_type;
      }
    }
  } catch (e) {}
}

async function loadHistory() {
  try {
    const res = await fetch("/api/v1/history?limit=25", { headers: getAuthHeaders() });
    if (!res.ok) return;
    const data = await res.json();
    const records = data.history || [];
    const isAdmin = data.is_admin || false;

    const subTitle = document.getElementById("hist-sub-title");
    if (subTitle) {
      subTitle.textContent = isAdmin
        ? "👑 SYSTEM ADMIN MODE — Displaying All User Assessments"
        : `🔒 Private Session Ledger — User ID: ${currentUser?.user_id || 'USR'} (Your Personal Records Only)`;
    }

    const render = (rows) => rows.length === 0
      ? `<tr><td colspan="8" style="text-align:center;padding:24px;color:var(--text-muted);">No credit assessments recorded for this account.</td></tr>`
      : rows.map(r => {
          const date = new Date(r.timestamp).toLocaleString("en-IN", { month:"short", day:"numeric", hour:"2-digit", minute:"2-digit" });
          return `<tr>
            <td style="font-size:11px;color:var(--text-muted);">${date}</td>
            <td><strong>${r.applicant_name}</strong></td>
            <td style="font-family:var(--font-mono);">₹${fmt(r.requested_loan)}</td>
            <td style="font-family:var(--font-mono);font-weight:700;color:var(--text-primary);">${r.nova_score}</td>
            <td>${r.risk_tier}</td>
            <td style="font-family:var(--font-mono);">${r.approval_probability}%</td>
            <td>${pillHtml(r.decision)}</td>
            <td><a href="/api/v1/reports/pdf/${r.id}" target="_blank" style="color:var(--primary);text-decoration:none;font-weight:600;font-size:11px;">PDF ↗</a></td>
          </tr>`;
        }).join("");

    const histTbl = document.getElementById("hist-table");
    if (histTbl) histTbl.innerHTML = render(records);
    const ovTbl = document.getElementById("ov-history-table");
    if (ovTbl) ovTbl.innerHTML = render(records.slice(0, 5));
  } catch (e) { console.error("History load error:", e); }
}

async function loadUserReports() {
  try {
    const res = await fetch("/api/v1/history?limit=50", { headers: getAuthHeaders() });
    if (!res.ok) return;
    const data = await res.json();
    const records = data.history || [];
    const tbody = document.getElementById("reportsTableBody");
    if (!tbody) return;

    if (records.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:24px;color:var(--text-muted);">No reports generated yet. Submit a credit assessment to download PDF reports.</td></tr>`;
      return;
    }

    tbody.innerHTML = records.map(r => {
      const date = new Date(r.timestamp).toLocaleString("en-IN", { month:"short", day:"numeric", hour:"2-digit", minute:"2-digit" });
      return `<tr>
        <td style="font-family:var(--font-mono);font-size:11px;">REP-${r.id.slice(0,6)}</td>
        <td style="font-family:var(--font-mono);font-size:11px;">${r.id}</td>
        <td><strong>${r.applicant_name}</strong></td>
        <td><span class="pill pill-info">PDF Underwriting</span></td>
        <td style="font-size:11px;color:var(--text-muted);">${date}</td>
        <td><a href="/api/v1/reports/pdf/${r.id}" target="_blank" class="btn btn-secondary btn-sm">Download PDF ↗</a></td>
      </tr>`;
    }).join("");
  } catch (e) {}
}

async function loadUserProfile() {
  if (!currentUser) return;
  document.getElementById("profUserId").value = currentUser.user_id || currentUser.id;
  document.getElementById("profFullName").value = currentUser.full_name || "";
  document.getElementById("profEmail").value = currentUser.email || "";

  try {
    const res = await fetch("/api/v1/user/profile", { headers: getAuthHeaders() });
    if (res.ok) {
      const data = await res.json();
      const fp = data.financial_profile;
      if (fp) {
        document.getElementById("profFinIncome").value = fp.monthly_income;
        document.getElementById("profFinEmi").value = fp.existing_emi;
        document.getElementById("profFinSavings").value = fp.savings_balance;
      }
    }
  } catch (e) {}
}

async function handleSaveProfile(e) {
  e.preventDefault();
  const fullName = document.getElementById("profFullName").value.trim();
  try {
    const res = await fetch("/api/v1/user/profile", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeaders() },
      body: JSON.stringify({ full_name: fullName }),
    });
    if (res.ok) {
      currentUser.full_name = fullName;
      localStorage.setItem("nova_user", JSON.stringify(currentUser));
      updateUserHeaderUI();
      alert("Profile updated successfully.");
    }
  } catch (e) { alert("Failed to update profile."); }
}

async function handleSaveFinancialDefaults(e) {
  e.preventDefault();
  const monthly_income = parseFloat(document.getElementById("profFinIncome").value);
  const existing_emi = parseFloat(document.getElementById("profFinEmi").value);
  const savings_balance = parseFloat(document.getElementById("profFinSavings").value);

  try {
    const res = await fetch("/api/v1/user/financial-profile", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeaders() },
      body: JSON.stringify({ monthly_income, existing_emi, savings_balance }),
    });
    if (res.ok) {
      alert("Financial defaults saved.");
    }
  } catch (e) { alert("Failed to save financial profile."); }
}

async function handleChangePassword(e) {
  e.preventDefault();
  const current_password = document.getElementById("inputCurrentPass").value;
  const new_password = document.getElementById("inputNewPass").value;
  const confirm = document.getElementById("inputConfirmPass").value;

  if (new_password !== confirm) {
    alert("New passwords do not match.");
    return;
  }

  try {
    const res = await fetch("/api/v1/user/password", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeaders() },
      body: JSON.stringify({ current_password, new_password }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Failed to update password.");
    alert("Password updated successfully.");
    document.getElementById("inputCurrentPass").value = "";
    document.getElementById("inputNewPass").value = "";
    document.getElementById("inputConfirmPass").value = "";
  } catch (err) { alert(err.message); }
}

// Placeholder loader widgets for secondary tools
function loadAssessmentWizard() {
  const container = document.getElementById("assessmentIntakeWizardContainer");
  if (!container || container.children.length > 0) return;
  container.innerHTML = `
    <form onsubmit="handleWizardAssessmentSubmit(event)" style="display:flex;flex-direction:column;gap:16px;">
      <div class="form-grid">
        <div class="field"><label>Applicant Name</label><input type="text" id="wizName" value="${currentUser?.full_name || 'Applicant'}" required/></div>
        <div class="field"><label>Age</label><input type="number" id="wizAge" value="32" min="18" max="90" required/></div>
        <div class="field"><label>Monthly Net Income (₹)</label><input type="number" id="wizIncome" value="75000" min="1000" required/></div>
        <div class="field"><label>Existing Monthly EMI (₹)</label><input type="number" id="wizEmi" value="10000" min="0" required/></div>
        <div class="field"><label>Requested Loan Amount (₹)</label><input type="number" id="wizLoan" value="200000" min="5000" required/></div>
        <div class="field"><label>Loan Tenure (Months)</label><input type="number" id="wizDuration" value="18" min="6" max="84" required/></div>
        <div class="field"><label>Liquid Savings (₹)</label><input type="number" id="wizSavings" value="150000" min="0" required/></div>
        <div class="field"><label>Housing Asset</label><select id="wizHousing"><option value="own">Own</option><option value="rent">Rent</option><option value="free">Free</option></select></div>
      </div>
      <button type="submit" class="btn btn-primary btn-block btn-lg">Run Underwriting Risk Assessment</button>
    </form>
    <div id="wizResultBox" style="margin-top:20px;"></div>
  `;
}

async function handleWizardAssessmentSubmit(e) {
  e.preventDefault();
  const payload = {
    applicant_name: document.getElementById("wizName").value,
    age: parseInt(document.getElementById("wizAge").value),
    sex: "male",
    job: "Skilled",
    housing: document.getElementById("wizHousing").value,
    saving_accounts: "moderate",
    checking_account: "moderate",
    purpose: "car",
    monthly_income: parseFloat(document.getElementById("wizIncome").value),
    existing_emi: parseFloat(document.getElementById("wizEmi").value),
    credit_amount: parseFloat(document.getElementById("wizLoan").value),
    duration: parseInt(document.getElementById("wizDuration").value),
    savings_balance: parseFloat(document.getElementById("wizSavings").value)
  };

  try {
    const res = await fetch("/api/v1/credit/assess", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeaders() },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    const box = document.getElementById("wizResultBox");
    if (box) {
      box.innerHTML = `
        <div class="card" style="background:var(--surface-elevated);border-color:var(--primary);">
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <div>
              <div style="font-size:11px;color:var(--text-muted);text-transform:uppercase;">Nova Credit Score</div>
              <div style="font-size:36px;font-family:var(--font-mono);font-weight:800;color:var(--primary);">${data.nova_score.nova_score} / 850</div>
              <div style="font-size:14px;font-weight:700;">${data.decision_engine.decision} (${data.approval_percentage}% Approval Probability)</div>
            </div>
            <a href="/api/v1/reports/pdf/${data.assessment_id}" target="_blank" class="btn btn-primary btn-sm">Download PDF Report ↗</a>
          </div>
        </div>
      `;
    }
  } catch (err) { alert("Assessment failed."); }
}

function loadWhatIfSimulator() {
  const c = document.getElementById("simulatorContainer");
  if (!c || c.children.length > 0) return;
  c.innerHTML = `
    <div style="display:flex;flex-direction:column;gap:14px;">
      <label>Monthly Income: ₹<span id="simValIncome">75,000</span></label>
      <input type="range" id="simRangeIncome" min="20000" max="300000" step="5000" value="75000" oninput="runSimulateTrigger()"/>
      <label>Requested Credit: ₹<span id="simValLoan">200,000</span></label>
      <input type="range" id="simRangeLoan" min="50000" max="1000000" step="10000" value="200000" oninput="runSimulateTrigger()"/>
      <div id="simOutBox" class="card" style="margin-top:10px;">Move sliders to simulate risk shift...</div>
    </div>
  `;
}

async function runSimulateTrigger() {
  const inc = parseFloat(document.getElementById("simRangeIncome").value);
  const loan = parseFloat(document.getElementById("simRangeLoan").value);
  document.getElementById("simValIncome").textContent = fmt(inc);
  document.getElementById("simValLoan").textContent = fmt(loan);

  try {
    const res = await fetch("/api/v1/credit/simulate", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeaders() },
      body: JSON.stringify({ monthly_income: inc, existing_emi: 10000, savings_balance: 150000, credit_amount: loan, duration: 18, age: 32 })
    });
    const data = await res.json();
    document.getElementById("simOutBox").innerHTML = `
      <div style="font-size:12px;color:var(--text-muted);">Simulated Nova Score:</div>
      <div style="font-size:28px;font-family:var(--font-mono);font-weight:700;color:var(--primary);">${data.nova_score.nova_score} / 850</div>
      <div>Simulated Verdict: ${pillHtml(data.decision_engine.decision)} (${data.approval_percentage}% Approval Probability)</div>
    `;
  } catch (e) {}
}

function loadLoanCalculator() {
  const c = document.getElementById("calculatorContainer");
  if (!c || c.children.length > 0) return;
  c.innerHTML = `
    <div style="display:flex;flex-direction:column;gap:12px;max-width:500px;">
      <div class="field"><label>Principal Loan Amount (₹)</label><input type="number" id="calcP" value="1000000"/></div>
      <div class="field"><label>Annual Interest Rate (%)</label><input type="number" id="calcR" step="0.1" value="9.5"/></div>
      <div class="field"><label>Tenure (Years)</label><input type="number" id="calcY" value="5"/></div>
      <button onclick="runLoanCalc()" class="btn btn-primary">Calculate EMI Schedule</button>
      <div id="calcOut" style="margin-top:12px;"></div>
    </div>
  `;
}

async function runLoanCalc() {
  const p = parseFloat(document.getElementById("calcP").value);
  const r = parseFloat(document.getElementById("calcR").value);
  const y = parseInt(document.getElementById("calcY").value);
  try {
    const res = await fetch("/api/v1/loans/calculate", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeaders() },
      body: JSON.stringify({ principal: p, annual_rate: r, tenure_years: y })
    });
    const data = await res.json();
    document.getElementById("calcOut").innerHTML = `
      <div style="font-size:14px;font-weight:700;margin-bottom:6px;">Monthly EMI: <span style="color:var(--primary);font-family:var(--font-mono);">₹${fmt(data.monthly_emi)}</span></div>
      <div style="font-size:12px;color:var(--text-muted);">Total Payment: ₹${fmt(data.total_payment)} (Interest: ₹${fmt(data.total_interest)})</div>
    `;
  } catch (e) {}
}

function loadFundExplorer() {
  const c = document.getElementById("fundsContainer");
  if (!c || c.children.length > 0) return;
  c.innerHTML = `
    <div class="table-container">
      <table>
        <thead><tr><th>Fund Category</th><th>1Y Return</th><th>3Y Return</th><th>Risk Tier</th><th>Status</th></tr></thead>
        <tbody>
          <tr><td>Nova Liquid Alpha Fund</td><td style="color:var(--success);">7.4%</td><td style="color:var(--success);">8.1%</td><td><span class="pill pill-success">Low Risk</span></td><td><span class="pill pill-info">Active</span></td></tr>
          <tr><td>Nova Institutional Dynamic Credit</td><td style="color:var(--success);">11.8%</td><td style="color:var(--success);">13.2%</td><td><span class="pill pill-warning">Moderate Risk</span></td><td><span class="pill pill-info">Active</span></td></tr>
          <tr><td>Nova AI Growth Equities</td><td style="color:var(--success);">18.4%</td><td style="color:var(--success);">21.6%</td><td><span class="pill pill-danger">High Growth</span></td><td><span class="pill pill-info">Active</span></td></tr>
        </tbody>
      </table>
    </div>
  `;
}

// ─── Admin Module Controllers (/admin/*) ──────────────────────────────────────

async function loadAdminDashboard() {
  try {
    const res = await fetch("/api/v1/admin/dashboard/stats", { headers: getAuthHeaders() });
    if (!res.ok) return;
    const data = await res.json();

    document.getElementById("adm-kpi-users").textContent = data.total_users;
    document.getElementById("adm-kpi-active-users").textContent = `${data.active_users} Active Accounts`;
    document.getElementById("adm-kpi-assessments").textContent = data.total_assessments;
    document.getElementById("adm-kpi-simulations").textContent = data.total_simulations;
    document.getElementById("adm-kpi-events").textContent = data.total_activity_events;

    const tbody = document.getElementById("adm-recent-signups-body");
    if (tbody && data.recent_signups) {
      tbody.innerHTML = data.recent_signups.map(u => {
        const date = new Date(u.created_at).toLocaleDateString("en-IN");
        return `<tr>
          <td style="font-family:var(--font-mono);font-size:11px;">${u.id}</td>
          <td><strong>${u.full_name}</strong></td>
          <td style="font-family:var(--font-mono);">${u.email}</td>
          <td><span class="pill ${u.role === 'ADMIN' ? 'pill-warning' : 'pill-info'}">${u.role}</span></td>
          <td style="font-size:11px;color:var(--text-muted);">${date}</td>
        </tr>`;
      }).join("");
    }
  } catch (e) { console.error("Admin dashboard load error:", e); }
}

function debounceAdminUserSearch() {
  clearTimeout(userSearchTimer);
  userSearchTimer = setTimeout(loadAdminUsers, 300);
}

async function loadAdminUsers() {
  try {
    const searchVal = document.getElementById("admUserSearchInput")?.value || "";
    const res = await fetch(`/api/v1/admin/users?limit=50${searchVal ? '&search=' + encodeURIComponent(searchVal) : ''}`, {
      headers: getAuthHeaders()
    });
    if (!res.ok) return;
    const data = await res.json();
    const users = data.users || [];
    const tbody = document.getElementById("adm-users-table-body");
    if (!tbody) return;

    if (users.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;padding:24px;color:var(--text-muted);">No users found matching query.</td></tr>`;
      return;
    }

    tbody.innerHTML = users.map(u => {
      const created = new Date(u.created_at).toLocaleDateString("en-IN");
      const lastLogin = u.last_login_at ? new Date(u.last_login_at).toLocaleString("en-IN", { month:"short", day:"numeric", hour:"2-digit", minute:"2-digit" }) : "Never";
      const statusPill = u.is_active ? `<span class="pill pill-success">Active</span>` : `<span class="pill pill-danger">Inactive</span>`;
      return `<tr>
        <td style="font-family:var(--font-mono);font-size:11px;">${u.id}</td>
        <td><strong>${u.full_name}</strong></td>
        <td style="font-family:var(--font-mono);">${u.email}</td>
        <td><span class="pill ${u.role === 'ADMIN' ? 'pill-warning' : 'pill-info'}">${u.role}</span></td>
        <td>${statusPill}</td>
        <td style="font-size:11px;color:var(--text-muted);">${created}</td>
        <td style="font-size:11px;color:var(--text-muted);">${lastLogin}</td>
        <td>
          <button class="btn btn-secondary btn-sm" onclick="openAdminUserModal('${u.id}')">Inspect User</button>
        </td>
      </tr>`;
    }).join("");
  } catch (e) { console.error("Admin user list load error:", e); }
}

async function openAdminUserModal(userId) {
  const modal = document.getElementById("adminUserModal");
  const body = document.getElementById("admUserModalBody");
  if (modal) modal.classList.add("active");
  if (body) body.innerHTML = `<p style="color:var(--text-muted);padding:24px;text-align:center;">Fetching detailed user data...</p>`;

  try {
    const res = await fetch(`/api/v1/admin/users/${userId}`, { headers: getAuthHeaders() });
    if (!res.ok) throw new Error("Could not retrieve user drill-down.");
    const data = await res.json();
    const u = data.user;
    const fp = data.financial_profile;

    document.getElementById("admUserModalTitle").textContent = `Inspect User: ${u.full_name} (${u.id})`;

    body.innerHTML = `
      <div style="display:flex;flex-direction:column;gap:16px;margin-top:12px;">
        <div style="display:flex;justify-content:space-between;align-items:center;background:var(--surface-elevated);padding:14px;border-radius:var(--r-md);border:1px solid var(--border-dim);">
          <div>
            <div style="font-size:16px;font-weight:700;">${u.full_name} <span class="pill ${u.role === 'ADMIN' ? 'pill-warning' : 'pill-info'}">${u.role}</span></div>
            <div style="font-family:var(--font-mono);font-size:12px;color:var(--text-muted);margin-top:2px;">Email: ${u.email} | ID: ${u.id}</div>
            <div style="font-size:11px;color:var(--text-muted);margin-top:2px;">Created: ${new Date(u.created_at).toLocaleString("en-IN")}</div>
          </div>
          <div>
            ${u.id !== currentUser.id ? `
              <button class="btn ${u.is_active ? 'btn-danger' : 'btn-primary'} btn-sm" onclick="handleToggleUserStatus('${u.id}', ${!u.is_active})">
                ${u.is_active ? 'Deactivate User' : 'Activate User'}
              </button>
            ` : '<span class="pill pill-neutral">Current Account</span>'}
          </div>
        </div>

        <div class="grid-3" style="gap:10px;">
          <div class="kpi-card"><div class="kpi-lbl">Assessments</div><div class="kpi-val">${data.assessment_count}</div></div>
          <div class="kpi-card"><div class="kpi-lbl">Simulations</div><div class="kpi-val">${data.simulation_count}</div></div>
          <div class="kpi-card"><div class="kpi-lbl">Reports</div><div class="kpi-val">${data.report_count}</div></div>
        </div>

        ${fp ? `
          <div class="card" style="background:var(--surface-elevated);">
            <div class="card-title" style="font-size:13px;">Financial Profile Summary</div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:12px;margin-top:6px;">
              <div>Income: <strong>₹${fmt(fp.monthly_income)}</strong></div>
              <div>EMI: <strong>₹${fmt(fp.existing_emi)}</strong></div>
              <div>Savings: <strong>₹${fmt(fp.savings_balance)}</strong></div>
              <div>Housing: <strong style="text-transform:capitalize;">${fp.housing_type}</strong></div>
            </div>
          </div>
        ` : ''}

        <div class="card" style="background:var(--surface-elevated);">
          <div class="card-title" style="font-size:13px;">Recent Credit Assessment History</div>
          <div class="table-container" style="margin-top:8px;">
            <table>
              <thead><tr><th>Date</th><th>Loan</th><th>Nova Score</th><th>Risk Tier</th><th>Verdict</th></tr></thead>
              <tbody>
                ${data.recent_assessments.length === 0 ? '<tr><td colspan="5" style="text-align:center;color:var(--text-muted);padding:12px;">No assessments run.</td></tr>' :
                  data.recent_assessments.map(r => `
                    <tr>
                      <td style="font-size:11px;color:var(--text-muted);">${new Date(r.timestamp).toLocaleDateString("en-IN")}</td>
                      <td style="font-family:var(--font-mono);">₹${fmt(r.requested_loan)}</td>
                      <td style="font-family:var(--font-mono);font-weight:700;">${r.nova_score}</td>
                      <td>${r.risk_tier}</td>
                      <td>${pillHtml(r.decision)}</td>
                    </tr>
                  `).join('')}
              </tbody>
            </table>
          </div>
        </div>

        <div class="card" style="background:var(--surface-elevated);">
          <div class="card-title" style="font-size:13px;">Recent User Activity Logs</div>
          <div class="table-container" style="margin-top:8px;">
            <table>
              <thead><tr><th>Timestamp</th><th>Action</th><th>Resource</th></tr></thead>
              <tbody>
                ${data.recent_activities.length === 0 ? '<tr><td colspan="3" style="text-align:center;color:var(--text-muted);padding:12px;">No activity logged.</td></tr>' :
                  data.recent_activities.map(a => `
                    <tr>
                      <td style="font-size:11px;color:var(--text-muted);">${new Date(a.timestamp).toLocaleString("en-IN", { month:"short", day:"numeric", hour:"2-digit", minute:"2-digit" })}</td>
                      <td>${actionBadgeHtml(a.action)}</td>
                      <td style="font-family:var(--font-mono);font-size:11px;">${a.resource_type || '—'} (${a.resource_id || '—'})</td>
                    </tr>
                  `).join('')}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    `;
  } catch (err) {
    body.innerHTML = `<p style="color:var(--danger);padding:24px;text-align:center;">${err.message}</p>`;
  }
}

function closeAdminUserModal() {
  const modal = document.getElementById("adminUserModal");
  if (modal) modal.classList.remove("active");
}

async function handleToggleUserStatus(userId, newActiveStatus) {
  try {
    const res = await fetch(`/api/v1/admin/users/${userId}/status`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", ...getAuthHeaders() },
      body: JSON.stringify({ is_active: newActiveStatus })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Failed to update user status.");
    alert(data.message);
    openAdminUserModal(userId);
    loadAdminUsers();
  } catch (err) { alert(err.message); }
}

async function loadAdminActivityLogs() {
  try {
    const res = await fetch("/api/v1/admin/activity?limit=100", { headers: getAuthHeaders() });
    if (!res.ok) return;
    const data = await res.json();
    const logs = data.activity_logs || [];
    const tbody = document.getElementById("adm-activity-table-body");
    if (!tbody) return;

    if (logs.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:24px;color:var(--text-muted);">No activity events recorded yet.</td></tr>`;
      return;
    }

    tbody.innerHTML = logs.map(l => {
      const date = new Date(l.timestamp).toLocaleString("en-IN", { month:"short", day:"numeric", hour:"2-digit", minute:"2-digit", second:"2-digit" });
      const detailsStr = l.details ? JSON.stringify(l.details) : "—";
      return `<tr>
        <td style="font-family:var(--font-mono);font-size:11px;">${l.id}</td>
        <td style="font-size:11px;color:var(--text-muted);">${date}</td>
        <td>${actionBadgeHtml(l.action)}</td>
        <td style="font-family:var(--font-mono);font-size:11px;">${l.user_id || 'SYSTEM'}</td>
        <td style="font-family:var(--font-mono);font-size:11px;">${l.user_email || 'system'}</td>
        <td style="font-family:var(--font-mono);font-size:11px;">${l.resource_type || '—'}</td>
        <td style="font-size:10px;font-family:var(--font-mono);color:var(--text-muted);max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${detailsStr}">${detailsStr}</td>
      </tr>`;
    }).join("");
  } catch (e) { console.error("Activity log load error:", e); }
}

async function loadAdminAssessments() {
  try {
    const res = await fetch("/api/v1/admin/assessments?limit=100", { headers: getAuthHeaders() });
    if (!res.ok) return;
    const data = await res.json();
    const records = data.assessments || [];
    const tbody = document.getElementById("adm-assessments-table-body");
    if (!tbody) return;

    if (records.length === 0) {
      tbody.innerHTML = `<tr><td colspan="9" style="text-align:center;padding:24px;color:var(--text-muted);">No assessments recorded across the platform.</td></tr>`;
      return;
    }

    tbody.innerHTML = records.map(r => {
      const date = new Date(r.timestamp).toLocaleString("en-IN", { month:"short", day:"numeric", hour:"2-digit", minute:"2-digit" });
      return `<tr>
        <td style="font-family:var(--font-mono);font-size:11px;">${r.id}</td>
        <td style="font-size:11px;color:var(--text-muted);">${date}</td>
        <td><strong>${r.applicant_name}</strong></td>
        <td style="font-family:var(--font-mono);font-size:11px;">${r.user_id || 'GUEST'}</td>
        <td style="font-family:var(--font-mono);">₹${fmt(r.requested_loan)}</td>
        <td style="font-family:var(--font-mono);font-weight:700;">${r.nova_score}</td>
        <td>${r.risk_tier}</td>
        <td>${pillHtml(r.decision)}</td>
        <td><a href="/api/v1/reports/pdf/${r.id}" target="_blank" class="btn btn-secondary btn-sm">PDF ↗</a></td>
      </tr>`;
    }).join("");
  } catch (e) { console.error("Admin assessments load error:", e); }
}

async function loadAdminModels() {
  const c = document.getElementById("telemetryContainer");
  if (!c) return;
  try {
    const res = await fetch("/api/v1/admin/models", { headers: getAuthHeaders() });
    if (!res.ok) return;
    const data = await res.json();
    const h = data.health || {};
    const m = data.metrics || {};

    c.innerHTML = `
      <div class="grid-2">
        <div>
          <h4 style="font-size:13px;color:var(--text-secondary);margin-bottom:8px;">Model Health Diagnostic</h4>
          <div style="font-size:12px;display:flex;flex-direction:column;gap:6px;">
            <div>Pipeline Status: <span class="pill pill-success">${h.status || 'Healthy'}</span></div>
            <div>Model Architecture: <strong>${h.model_type || 'CatBoostClassifier'}</strong></div>
            <div>Artifact Path: <code style="font-family:var(--font-mono);color:var(--primary);">${h.pipeline_path || 'models/nova_credit_pipeline.joblib'}</code></div>
            <div>SHAP Explainer: <strong>${h.explainer_status || 'Loaded'}</strong></div>
          </div>
        </div>
        <div>
          <h4 style="font-size:13px;color:var(--text-secondary);margin-bottom:8px;">Holdout Benchmark Metrics</h4>
          <div style="font-size:12px;display:flex;flex-direction:column;gap:6px;">
            <div>Holdout ROC-AUC: <strong style="font-family:var(--font-mono);color:var(--success);">${m.holdout_roc_auc?.toFixed(4) || '0.7686'}</strong></div>
            <div>Holdout PR-AUC: <strong style="font-family:var(--font-mono);">${m.holdout_pr_auc?.toFixed(4) || '0.8630'}</strong></div>
            <div>ECE Calibration Error: <strong style="font-family:var(--font-mono);">${m.calibration_ece ? (m.calibration_ece*100).toFixed(2) + '%' : '1.67%'}</strong></div>
          </div>
        </div>
      </div>
    `;
  } catch (e) {}
}

// ─── Initialize SPA Router on Document Ready ────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  routeResolver();
});
