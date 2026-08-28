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
    if (pageTitle) pageTitle.textContent = "Loan Intelligence";
    loadLoanIntelligence();
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
    if (headerSub) headerSub.textContent = "Sign in to access your Nova workspace.";
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

// ─── LOAN INTELLIGENCE MODULE ──────────────────────────────────────────────────

let liCurrentPlannerData = null;
let liChartBreakdownInstance = null;
let liChartTradeOffInstance = null;

function loadLoanIntelligence() {
  const container = document.getElementById("loanIntelligenceContainer") || document.getElementById("calculatorContainer");
  if (!container) return;

  container.innerHTML = `
    <div class="li-workspace">
      <!-- Top Header -->
      <div class="li-header">
        <h2 class="li-title">Loan Intelligence</h2>
        <p class="li-subtitle">Plan around your finances, not just the EMI. Compare repayment strategies, understand affordability and optimize the true cost of borrowing.</p>
      </div>

      <!-- 5 Workspace Tabs Navigation -->
      <div class="li-tabs-container">
        <button class="li-tab-btn active" id="liTabBtnPlanner" onclick="switchLiTab('planner')">
          <i data-lucide="calculator"></i><span>Planner</span>
        </button>
        <button class="li-tab-btn" id="liTabBtnAffordability" onclick="switchLiTab('affordability')">
          <i data-lucide="shield-check"></i><span>Affordability</span>
        </button>
        <button class="li-tab-btn" id="liTabBtnCompare" onclick="switchLiTab('compare')">
          <i data-lucide="git-compare"></i><span>Compare Loans</span>
        </button>
        <button class="li-tab-btn" id="liTabBtnPrepayment" onclick="switchLiTab('prepayment')">
          <i data-lucide="zap"></i><span>Prepayment Lab</span>
        </button>
        <button class="li-tab-btn" id="liTabBtnAmortization" onclick="switchLiTab('amortization')">
          <i data-lucide="table"></i><span>Amortization</span>
        </button>
      </div>

      <!-- TAB 1: PLANNER -->
      <div id="liTabPlanner" class="li-tab-content">
        <div class="li-split-grid">
          <!-- Left: Input Form Card -->
          <div class="card" style="margin:0;">
            <div class="card-title" style="font-size:15px;margin-bottom:14px;">Loan Parameters</div>
            <form onsubmit="event.preventDefault(); runLoanPlannerCalc();">
              <div class="form-grid" style="grid-template-columns:1fr 1fr;gap:12px;">
                <div class="field span-2">
                  <label>Loan Type</label>
                  <select id="liLoanType" class="form-control" style="width:100%;padding:8px 12px;background:var(--bg-input);border:1px solid var(--border-dim);color:var(--text-primary);border-radius:6px;">
                    <option value="Personal Loan">Personal Loan</option>
                    <option value="Home Loan" selected>Home Loan</option>
                    <option value="Car Loan">Car Loan</option>
                    <option value="Education Loan">Education Loan</option>
                    <option value="Business Loan">Business Loan</option>
                    <option value="Other">Other</option>
                  </select>
                </div>
                <div class="field span-2">
                  <label>Principal Loan Amount (₹)</label>
                  <input type="number" id="liPrincipal" value="2500000" min="1000" step="10000" required style="font-family:var(--font-mono);font-weight:600;"/>
                </div>
                <div class="field">
                  <label>Interest Rate (% p.a.)</label>
                  <input type="number" id="liRate" value="8.5" min="0" max="100" step="0.1" required style="font-family:var(--font-mono);"/>
                </div>
                <div class="field">
                  <label>Tenure</label>
                  <div style="display:flex;gap:4px;">
                    <input type="number" id="liTenureVal" value="20" min="1" max="480" required style="font-family:var(--font-mono);flex:1;"/>
                    <select id="liTenureUnit" style="width:80px;background:var(--bg-input);border:1px solid var(--border-dim);color:var(--text-primary);border-radius:6px;font-size:12px;">
                      <option value="years" selected>Years</option>
                      <option value="months">Months</option>
                    </select>
                  </div>
                </div>
                <div class="field">
                  <label>Processing Fee</label>
                  <div style="display:flex;gap:4px;">
                    <input type="number" id="liFeeVal" value="0.5" min="0" step="0.1" style="font-family:var(--font-mono);flex:1;"/>
                    <select id="liFeeType" style="width:60px;background:var(--bg-input);border:1px solid var(--border-dim);color:var(--text-primary);border-radius:6px;font-size:12px;">
                      <option value="percentage" selected>%</option>
                      <option value="flat">₹</option>
                    </select>
                  </div>
                </div>
                <div class="field">
                  <label>Down Payment (₹)</label>
                  <input type="number" id="liDownPayment" value="500000" min="0" step="10000" style="font-family:var(--font-mono);"/>
                </div>
                <div class="field span-2">
                  <label>Loan Start Date</label>
                  <input type="date" id="liStartDate" style="font-family:var(--font-mono);"/>
                </div>
              </div>
              <div style="display:flex;gap:10px;margin-top:16px;">
                <button type="submit" class="btn btn-primary" style="flex:1;"><i data-lucide="play"></i><span>Calculate & Analyze</span></button>
                <button type="button" onclick="saveCurrentScenario()" class="btn btn-secondary" title="Save Scenario"><i data-lucide="bookmark"></i><span>Save</span></button>
              </div>
            </form>
          </div>

          <!-- Right: Hero Results Card & Compact Metrics -->
          <div style="display:flex;flex-direction:column;gap:16px;">
            <div class="li-hero-card">
              <div style="display:flex;justify-content:space-between;align-items:flex-start;">
                <div>
                  <span class="li-hero-emi-label">Monthly EMI Commitment</span>
                  <div class="li-hero-emi-value" id="liResEmi">₹0</div>
                </div>
                <div id="liResHealthBadge"></div>
              </div>
              <div class="li-metrics-grid">
                <div class="li-metric-box">
                  <span class="li-metric-lbl">Net Principal</span>
                  <span class="li-metric-val" id="liResNetP">₹0</span>
                </div>
                <div class="li-metric-box">
                  <span class="li-metric-lbl">Total Interest</span>
                  <span class="li-metric-val" id="liResInterest" style="color:#F59E0B;">₹0</span>
                </div>
                <div class="li-metric-box">
                  <span class="li-metric-lbl">Total Repayment</span>
                  <span class="li-metric-val" id="liResRepayment">₹0</span>
                </div>
                <div class="li-metric-box">
                  <span class="li-metric-lbl">Processing Fee</span>
                  <span class="li-metric-val" id="liResFee">₹0</span>
                </div>
                <div class="li-metric-box">
                  <span class="li-metric-lbl">Effective Total Cost</span>
                  <span class="li-metric-val" id="liResCost">₹0</span>
                </div>
                <div class="li-metric-box">
                  <span class="li-metric-lbl">Interest/Principal</span>
                  <span class="li-metric-val" id="liResRatio">0%</span>
                </div>
                <div class="li-metric-box" style="grid-column:span 2;">
                  <span class="li-metric-lbl">Loan End Date</span>
                  <span class="li-metric-val" id="liResEndDate" style="font-size:13px;">—</span>
                </div>
              </div>
            </div>

            <!-- Nova Loan Insight Banner -->
            <div class="li-insight-box">
              <i data-lucide="sparkles" class="li-insight-icon"></i>
              <div>
                <strong style="font-size:12px;text-transform:uppercase;color:var(--primary);letter-spacing:0.04em;">Nova Loan Insight</strong>
                <p class="li-insight-text" id="liResInsight">Run calculation to generate deterministic financial insight.</p>
              </div>
            </div>
          </div>
        </div>

        <!-- Interactive Repayment Breakdown & Chart Section -->
        <div class="card" style="margin-top:20px;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;flex-wrap:wrap;gap:8px;">
            <div>
              <div class="card-title" style="font-size:15px;margin:0;">Principal vs Interest Repayment Timeline</div>
              <p class="card-sub" style="margin:2px 0 0 0;">Visualize how every monthly or yearly payment reduces loan principal over time.</p>
            </div>
            <div class="li-segmented-control">
              <button class="li-segment-btn active" id="liChartToggleMonthly" onclick="toggleRepaymentChartView('monthly')">Monthly</button>
              <button class="li-segment-btn" id="liChartToggleYearly" onclick="toggleRepaymentChartView('yearly')">Yearly</button>
            </div>
          </div>
          <div class="li-chart-wrapper">
            <canvas id="liRepaymentCanvas"></canvas>
          </div>
        </div>

        <!-- Smart Tenure Optimizer Section -->
        <div class="card" style="margin-top:20px;">
          <div class="card-title" style="font-size:15px;">Smart Tenure Optimizer</div>
          <p class="card-sub" style="margin-bottom:12px;">Dynamic tenure scenarios comparing monthly commitment against total interest overhead.</p>
          <div class="table-container">
            <table>
              <thead>
                <tr>
                  <th>Tenure</th>
                  <th>Monthly EMI</th>
                  <th>Total Interest</th>
                  <th>Modeled FOIR</th>
                  <th>Health Rating</th>
                  <th>Tag / Recommendation</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody id="liTenureOptimizerBody">
                <tr><td colspan="7" style="text-align:center;padding:16px;color:var(--text-muted);">Calculating tenure matrix...</td></tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- EMI vs Interest Trade-Off Section -->
        <div class="card" style="margin-top:20px;">
          <div class="card-title" style="font-size:15px;">EMI vs Interest Trade-Off Analysis</div>
          <p class="card-sub" style="margin-bottom:10px;">As tenure increases, monthly EMI drops but cumulative interest increases exponentially.</p>
          <div class="li-chart-wrapper" style="height:220px;">
            <canvas id="liTradeOffCanvas"></canvas>
          </div>
        </div>

        <!-- Saved Scenarios Ledger -->
        <div class="card" style="margin-top:20px;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
            <div class="card-title" style="font-size:15px;margin:0;">My Saved Loan Scenarios</div>
            <button onclick="loadUserLoanScenarios()" class="btn btn-ghost btn-sm"><i data-lucide="refresh-cw"></i><span>Refresh</span></button>
          </div>
          <div class="table-container">
            <table>
              <thead>
                <tr>
                  <th>Scenario Name</th>
                  <th>Type</th>
                  <th>Principal</th>
                  <th>Rate</th>
                  <th>Tenure</th>
                  <th>EMI</th>
                  <th>Affordability</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody id="liScenariosBody">
                <tr><td colspan="8" style="text-align:center;padding:16px;color:var(--text-muted);">Loading saved scenarios...</td></tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- TAB 2: AFFORDABILITY -->
      <div id="liTabAffordability" class="li-tab-content" style="display:none;">
        <div class="li-split-grid">
          <div class="card" style="margin:0;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
              <div class="card-title" style="font-size:15px;margin:0;">Income & Obligation Inputs</div>
              <button class="btn btn-secondary btn-sm" onclick="autoFillAffordabilityFromProfile()"><i data-lucide="user-check"></i><span>Auto-fill from Profile</span></button>
            </div>
            <form onsubmit="event.preventDefault(); runAffordabilityCalc();">
              <div class="form-grid" style="grid-template-columns:1fr 1fr;gap:12px;">
                <div class="field span-2">
                  <label>Monthly Net Income (₹)</label>
                  <input type="number" id="liAffIncome" value="85000" min="0" step="5000" required style="font-family:var(--font-mono);"/>
                </div>
                <div class="field span-2">
                  <label>Proposed New Loan EMI (₹)</label>
                  <input type="number" id="liAffProposedEmi" value="23500" min="0" step="1000" required style="font-family:var(--font-mono);"/>
                </div>
                <div class="field">
                  <label>Existing Monthly EMIs (₹)</label>
                  <input type="number" id="liAffExistingEmi" value="10000" min="0" step="1000" style="font-family:var(--font-mono);"/>
                </div>
                <div class="field">
                  <label>Rent / Housing Expense (₹)</label>
                  <input type="number" id="liAffRent" value="15000" min="0" step="1000" style="font-family:var(--font-mono);"/>
                </div>
                <div class="field">
                  <label>Other Fixed Obligations (₹)</label>
                  <input type="number" id="liAffOtherFixed" value="3000" min="0" step="500" style="font-family:var(--font-mono);"/>
                </div>
                <div class="field">
                  <label>Essential Monthly Living (₹)</label>
                  <input type="number" id="liAffEssentials" value="18000" min="0" step="1000" style="font-family:var(--font-mono);"/>
                </div>
              </div>
              <button type="submit" class="btn btn-primary btn-block" style="margin-top:16px;"><i data-lucide="shield-check"></i><span>Analyze Affordability</span></button>
            </form>
          </div>

          <div style="display:flex;flex-direction:column;gap:16px;">
            <div class="card" style="margin:0;">
              <div class="card-title" style="font-size:15px;margin-bottom:14px;">Affordability & Debt Burden Metrics</div>
              <div class="grid-2" style="gap:12px;">
                <div class="li-metric-box">
                  <span class="li-metric-lbl">Existing FOIR</span>
                  <span class="li-metric-val" id="liAffExistingFoir">0%</span>
                </div>
                <div class="li-metric-box">
                  <span class="li-metric-lbl">New Modeled FOIR</span>
                  <span class="li-metric-val" id="liAffNewFoir" style="color:var(--primary);">0%</span>
                </div>
                <div class="li-metric-box">
                  <span class="li-metric-lbl">EMI-to-Income Ratio</span>
                  <span class="li-metric-val" id="liAffEmiRatio">0%</span>
                </div>
                <div class="li-metric-box">
                  <span class="li-metric-lbl">Disposable Income (Before)</span>
                  <span class="li-metric-val" id="liAffDispBefore">₹0</span>
                </div>
                <div class="li-metric-box">
                  <span class="li-metric-lbl">Disposable Income (After)</span>
                  <span class="li-metric-val" id="liAffDispAfter">₹0</span>
                </div>
                <div class="li-metric-box">
                  <span class="li-metric-lbl">Repayment Buffer</span>
                  <span class="li-metric-val" id="liAffRepayCap">₹0</span>
                </div>
              </div>
            </div>

            <!-- Health Assessment Card -->
            <div class="card" style="margin:0;" id="liAffHealthCard">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
                <div class="card-title" style="font-size:15px;margin:0;">Loan Health Assessment</div>
                <span id="liAffHealthPill"></span>
              </div>
              <p style="font-size:13px;color:var(--text-primary);line-height:1.5;margin:0;" id="liAffExplanation">Run affordability analysis to calculate status.</p>
              <div style="margin-top:12px;font-size:11px;color:var(--text-muted);display:flex;gap:12px;">
                <span>🟢 Comfortable: ≤35%</span>
                <span>🔵 Manageable: 35–45%</span>
                <span>🟡 Stretched: 45–55%</span>
                <span>🔴 High Burden: >55%</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- TAB 3: COMPARE LOANS -->
      <div id="liTabCompare" class="li-tab-content" style="display:none;">
        <div class="card" style="margin-bottom:20px;">
          <div class="card-title" style="font-size:15px;margin-bottom:12px;">Multi-Offer Loan Comparison Lab</div>
          <p class="card-sub" style="margin-bottom:16px;">Compare up to 3 loan offers side-by-side to evaluate interest overhead, fees, and true borrowing cost.</p>

          <div class="grid-3" style="gap:16px;">
            <!-- Offer 1 -->
            <div style="background:var(--bg-card);border:1px solid var(--border-dim);padding:14px;border-radius:8px;">
              <strong style="font-size:13px;color:var(--primary);">Offer 1 (Default)</strong>
              <div style="display:flex;flex-direction:column;gap:8px;margin-top:10px;">
                <input type="text" id="liCmpName1" value="HDFC Bank" placeholder="Lender Name" class="form-control" style="font-size:12px;"/>
                <input type="number" id="liCmpP1" value="2000000" placeholder="Loan Amount (₹)" class="form-control" style="font-size:12px;font-family:var(--font-mono);"/>
                <input type="number" id="liCmpR1" value="8.4" step="0.1" placeholder="Rate (%)" class="form-control" style="font-size:12px;font-family:var(--font-mono);"/>
                <input type="number" id="liCmpT1" value="36" placeholder="Tenure (Months)" class="form-control" style="font-size:12px;font-family:var(--font-mono);"/>
                <input type="number" id="liCmpF1" value="0.5" step="0.1" placeholder="Processing Fee (%)" class="form-control" style="font-size:12px;font-family:var(--font-mono);"/>
              </div>
            </div>

            <!-- Offer 2 -->
            <div style="background:var(--bg-card);border:1px solid var(--border-dim);padding:14px;border-radius:8px;">
              <strong style="font-size:13px;color:#60A5FA;">Offer 2</strong>
              <div style="display:flex;flex-direction:column;gap:8px;margin-top:10px;">
                <input type="text" id="liCmpName2" value="ICICI Bank" placeholder="Lender Name" class="form-control" style="font-size:12px;"/>
                <input type="number" id="liCmpP2" value="2000000" placeholder="Loan Amount (₹)" class="form-control" style="font-size:12px;font-family:var(--font-mono);"/>
                <input type="number" id="liCmpR2" value="8.9" step="0.1" placeholder="Rate (%)" class="form-control" style="font-size:12px;font-family:var(--font-mono);"/>
                <input type="number" id="liCmpT2" value="48" placeholder="Tenure (Months)" class="form-control" style="font-size:12px;font-family:var(--font-mono);"/>
                <input type="number" id="liCmpF2" value="0.25" step="0.1" placeholder="Processing Fee (%)" class="form-control" style="font-size:12px;font-family:var(--font-mono);"/>
              </div>
            </div>

            <!-- Offer 3 -->
            <div style="background:var(--bg-card);border:1px solid var(--border-dim);padding:14px;border-radius:8px;">
              <strong style="font-size:13px;color:#F59E0B;">Offer 3</strong>
              <div style="display:flex;flex-direction:column;gap:8px;margin-top:10px;">
                <input type="text" id="liCmpName3" value="SBI Loan" placeholder="Lender Name" class="form-control" style="font-size:12px;"/>
                <input type="number" id="liCmpP3" value="2000000" placeholder="Loan Amount (₹)" class="form-control" style="font-size:12px;font-family:var(--font-mono);"/>
                <input type="number" id="liCmpR3" value="8.6" step="0.1" placeholder="Rate (%)" class="form-control" style="font-size:12px;font-family:var(--font-mono);"/>
                <input type="number" id="liCmpT3" value="36" placeholder="Tenure (Months)" class="form-control" style="font-size:12px;font-family:var(--font-mono);"/>
                <input type="number" id="liCmpF3" value="0.0" step="0.1" placeholder="Processing Fee (%)" class="form-control" style="font-size:12px;font-family:var(--font-mono);"/>
              </div>
            </div>
          </div>

          <button onclick="runLoanComparison()" class="btn btn-primary" style="margin-top:16px;"><i data-lucide="git-compare"></i><span>Compare All Offers</span></button>
        </div>

        <div class="card" id="liCmpResultsCard" style="display:none;">
          <div class="card-title" style="font-size:15px;margin-bottom:12px;">Side-by-Side Comparison Matrix</div>
          <div class="table-container">
            <table>
              <thead>
                <tr>
                  <th>Metric</th>
                  <th id="liCmpCol1">Offer 1</th>
                  <th id="liCmpCol2">Offer 2</th>
                  <th id="liCmpCol3">Offer 3</th>
                </tr>
              </thead>
              <tbody id="liCmpTableBody"></tbody>
            </table>
          </div>
          <div class="li-insight-box" style="margin-top:14px;">
            <i data-lucide="info" class="li-insight-icon"></i>
            <p class="li-insight-text" id="liCmpSummaryNote"></p>
          </div>
        </div>
      </div>

      <!-- TAB 4: PREPAYMENT LAB -->
      <div id="liTabPrepayment" class="li-tab-content" style="display:none;">
        <div class="li-split-grid">
          <!-- Left: Prepayment Inputs -->
          <div class="card" style="margin:0;">
            <div class="card-title" style="font-size:15px;margin-bottom:14px;">Prepayment Simulation Parameters</div>
            <form onsubmit="event.preventDefault(); runPrepaymentSimulation();">
              <div class="form-grid" style="grid-template-columns:1fr 1fr;gap:12px;">
                <div class="field span-2">
                  <label>Loan Amount (₹)</label>
                  <input type="number" id="liPrepP" value="1500000" required style="font-family:var(--font-mono);"/>
                </div>
                <div class="field">
                  <label>Rate (% p.a.)</label>
                  <input type="number" id="liPrepR" value="9.0" step="0.1" required style="font-family:var(--font-mono);"/>
                </div>
                <div class="field">
                  <label>Tenure (Months)</label>
                  <input type="number" id="liPrepT" value="60" required style="font-family:var(--font-mono);"/>
                </div>
                
                <div class="field span-2" style="border-top:1px solid var(--border-dim);padding-top:10px;margin-top:4px;">
                  <strong style="font-size:12px;color:var(--primary);text-transform:uppercase;">One-Time Lump Sum Prepayment</strong>
                </div>
                <div class="field">
                  <label>Prepay Amount (₹)</label>
                  <input type="number" id="liPrepAmt" value="200000" step="10000" style="font-family:var(--font-mono);"/>
                </div>
                <div class="field">
                  <label>Prepay Month</label>
                  <input type="number" id="liPrepMonth" value="12" min="1" max="360" style="font-family:var(--font-mono);"/>
                </div>
                <div class="field span-2">
                  <label>Strategy</label>
                  <select id="liPrepStrategy" class="form-control" style="width:100%;padding:8px;background:var(--bg-input);border:1px solid var(--border-dim);color:var(--text-primary);border-radius:6px;">
                    <option value="reduce_tenure" selected>Reduce Tenure (Payoff loan faster)</option>
                    <option value="reduce_emi">Reduce EMI (Lower monthly payment)</option>
                  </select>
                </div>

                <div class="field span-2" style="border-top:1px solid var(--border-dim);padding-top:10px;margin-top:4px;">
                  <strong style="font-size:12px;color:#F59E0B;text-transform:uppercase;">Pay Extra Every Month</strong>
                </div>
                <div class="field span-2">
                  <label>Extra Monthly EMI (₹)</label>
                  <input type="number" id="liPrepExtraMonthly" value="2000" step="500" style="font-family:var(--font-mono);"/>
                  <div class="li-chips-group">
                    <button type="button" class="li-chip" onclick="setExtraEmiChip(500)">+₹500</button>
                    <button type="button" class="li-chip" onclick="setExtraEmiChip(1000)">+₹1,000</button>
                    <button type="button" class="li-chip active" onclick="setExtraEmiChip(2000)">+₹2,000</button>
                    <button type="button" class="li-chip" onclick="setExtraEmiChip(5000)">+₹5,000</button>
                  </div>
                </div>
              </div>
              <button type="submit" class="btn btn-primary btn-block" style="margin-top:16px;"><i data-lucide="zap"></i><span>Simulate Prepayment Impact</span></button>
            </form>
          </div>

          <!-- Right: Prepayment Results -->
          <div style="display:flex;flex-direction:column;gap:16px;">
            <div class="card" style="margin:0;">
              <div class="card-title" style="font-size:15px;margin-bottom:14px;">Prepayment Savings Summary</div>
              <div class="grid-2" style="gap:12px;">
                <div class="li-metric-box">
                  <span class="li-metric-lbl">Total Interest Saved</span>
                  <span class="li-metric-val" id="liPrepResInterestSaved" style="color:#10B981;font-size:18px;">₹0</span>
                </div>
                <div class="li-metric-box">
                  <span class="li-metric-lbl">Months Saved</span>
                  <span class="li-metric-val" id="liPrepResMonthsSaved" style="color:#60A5FA;font-size:18px;">0 Months</span>
                </div>
                <div class="li-metric-box">
                  <span class="li-metric-lbl">Original Payoff Date</span>
                  <span class="li-metric-val" id="liPrepResOrigDate">—</span>
                </div>
                <div class="li-metric-box">
                  <span class="li-metric-lbl">New Payoff Date</span>
                  <span class="li-metric-val" id="liPrepResNewDate" style="color:var(--primary);">—</span>
                </div>
                <div class="li-metric-box">
                  <span class="li-metric-lbl">Total Repayment (Before)</span>
                  <span class="li-metric-val" id="liPrepResTotalBefore">₹0</span>
                </div>
                <div class="li-metric-box">
                  <span class="li-metric-lbl">Total Repayment (After)</span>
                  <span class="li-metric-val" id="liPrepResTotalAfter">₹0</span>
                </div>
              </div>
            </div>

            <div class="li-insight-box">
              <i data-lucide="trending-down" class="li-insight-icon"></i>
              <div>
                <strong style="font-size:12px;text-transform:uppercase;color:var(--primary);letter-spacing:0.04em;">Acceleration Narrative</strong>
                <p class="li-insight-text" id="liPrepNarrative">Run prepayment simulation to generate analysis.</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- TAB 5: AMORTIZATION -->
      <div id="liTabAmortization" class="li-tab-content" style="display:none;">
        <div class="card">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;flex-wrap:wrap;gap:8px;">
            <div>
              <div class="card-title" style="font-size:15px;margin:0;">Amortization Schedule Ledger</div>
              <p class="card-sub" style="margin:2px 0 0 0;">Complete line-item breakdown of principal, interest, and closing balance.</p>
            </div>
            <div style="display:flex;gap:10px;align-items:center;">
              <div class="li-segmented-control">
                <button class="li-segment-btn active" id="liAmortToggleMonthly" onclick="toggleAmortizationView('monthly')">Monthly</button>
                <button class="li-segment-btn" id="liAmortToggleYearly" onclick="toggleAmortizationView('yearly')">Yearly Summary</button>
              </div>
              <button onclick="exportAmortizationCsv()" class="btn btn-secondary btn-sm"><i data-lucide="download"></i><span>Export CSV</span></button>
            </div>
          </div>

          <div class="table-container">
            <table>
              <thead>
                <tr>
                  <th id="liAmortColPeriod">Period</th>
                  <th>Opening Balance</th>
                  <th>Monthly EMI</th>
                  <th>Principal Paid</th>
                  <th>Interest Paid</th>
                  <th>Extra Payment</th>
                  <th>Closing Balance</th>
                </tr>
              </thead>
              <tbody id="liAmortTableBody">
                <tr><td colspan="7" style="text-align:center;padding:20px;color:var(--text-muted);">Run loan planner calculation to view schedule.</td></tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- Disclaimer Footer -->
      <div class="li-disclaimer">
        <i data-lucide="info"></i>
        <span><strong>Disclaimer:</strong> Loan calculations and affordability indicators are estimates based on the information provided. Actual lender rates, fees, eligibility and repayment terms may differ.</span>
      </div>
    </div>
  `;

  if (window.lucide) window.lucide.createIcons();

  // Set default start date to today
  const startDateInput = document.getElementById("liStartDate");
  if (startDateInput && !startDateInput.value) {
    startDateInput.value = new Date().toISOString().split("T")[0];
  }

  // Initial calculation
  runLoanPlannerCalc();
}

function switchLiTab(tabName) {
  const tabs = ["planner", "affordability", "compare", "prepayment", "amortization"];
  tabs.forEach(t => {
    const btn = document.getElementById("liTabBtn" + t.charAt(0).toUpperCase() + t.slice(1));
    const content = document.getElementById("liTab" + t.charAt(0).toUpperCase() + t.slice(1));
    if (btn) btn.classList.toggle("active", t === tabName);
    if (content) content.style.display = (t === tabName) ? "block" : "none";
  });

  if (window.lucide) window.lucide.createIcons();

  if (tabName === "planner" && liCurrentPlannerData) {
    renderRepaymentChart(liCurrentPlannerData.schedule, "monthly");
  } else if (tabName === "affordability") {
    runAffordabilityCalc();
  } else if (tabName === "compare") {
    runLoanComparison();
  } else if (tabName === "prepayment") {
    runPrepaymentSimulation();
  } else if (tabName === "amortization" && liCurrentPlannerData) {
    renderAmortizationTable(liCurrentPlannerData.schedule, "monthly");
  }
}

async function runLoanPlannerCalc() {
  const principal = parseFloat(document.getElementById("liPrincipal").value) || 0;
  const rate = parseFloat(document.getElementById("liRate").value) || 0;
  const tenureVal = parseInt(document.getElementById("liTenureVal").value) || 1;
  const tenureUnit = document.getElementById("liTenureUnit").value;
  const feeVal = parseFloat(document.getElementById("liFeeVal").value) || 0;
  const feeType = document.getElementById("liFeeType").value;
  const downPayment = parseFloat(document.getElementById("liDownPayment").value) || 0;
  const startDate = document.getElementById("liStartDate").value;
  const loanType = document.getElementById("liLoanType").value;

  const tenure_months = tenureUnit === "years" ? tenureVal * 12 : tenureVal;

  try {
    const res = await fetch("/api/v1/loans/calculate", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeaders() },
      body: JSON.stringify({
        principal,
        annual_rate: rate,
        tenure_months,
        loan_type: loanType,
        processing_fee_val: feeVal,
        processing_fee_type: feeType,
        down_payment: downPayment,
        start_date: startDate
      })
    });

    if (!res.ok) return;
    const data = await res.json();
    liCurrentPlannerData = data;

    // Update UI elements
    document.getElementById("liResEmi").textContent = "₹" + fmt(data.monthly_emi);
    document.getElementById("liResNetP").textContent = "₹" + fmt(data.net_principal);
    document.getElementById("liResInterest").textContent = "₹" + fmt(data.total_interest);
    document.getElementById("liResRepayment").textContent = "₹" + fmt(data.total_payment);
    document.getElementById("liResFee").textContent = "₹" + fmt(data.processing_fee);
    document.getElementById("liResCost").textContent = "₹" + fmt(data.effective_total_cost);
    document.getElementById("liResRatio").textContent = data.interest_to_principal_ratio.toFixed(1) + "%";
    document.getElementById("liResEndDate").textContent = data.end_date;
    document.getElementById("liResInsight").textContent = data.nova_insight;

    renderRepaymentChart(data.schedule, "monthly");
    renderAmortizationTable(data.schedule, "monthly");
    loadTenureOptimizer(principal, rate, downPayment, feeVal, feeType, tenure_months);
    loadUserLoanScenarios();
  } catch (e) {
    console.error("Loan planner calc error:", e);
  }
}

function toggleRepaymentChartView(mode) {
  document.getElementById("liChartToggleMonthly").classList.toggle("active", mode === "monthly");
  document.getElementById("liChartToggleYearly").classList.toggle("active", mode === "yearly");
  if (liCurrentPlannerData) {
    const dataList = (mode === "yearly") ? liCurrentPlannerData.yearly_schedule : liCurrentPlannerData.schedule;
    renderRepaymentChart(dataList, mode);
  }
}

function renderRepaymentChart(scheduleData, viewMode) {
  const canvas = document.getElementById("liRepaymentCanvas");
  if (!canvas || !window.Chart) return;

  if (liChartBreakdownInstance) {
    liChartBreakdownInstance.destroy();
  }

  const labels = scheduleData.map(item => viewMode === "yearly" ? `Year ${item.year}` : `M${item.month}`);
  const principalPaid = scheduleData.map(item => item.principal_paid);
  const interestPaid = scheduleData.map(item => item.interest_paid);
  const balance = scheduleData.map(item => item.closing_balance);

  const ctx = canvas.getContext("2d");
  liChartBreakdownInstance = new window.Chart(ctx, {
    type: "bar",
    data: {
      labels: labels,
      datasets: [
        {
          label: "Principal Paid (₹)",
          data: principalPaid,
          backgroundColor: "rgba(59, 130, 246, 0.7)",
          borderColor: "#3B82F6",
          borderWidth: 1,
          stack: "Stack 0"
        },
        {
          label: "Interest Paid (₹)",
          data: interestPaid,
          backgroundColor: "rgba(245, 158, 11, 0.7)",
          borderColor: "#F59E0B",
          borderWidth: 1,
          stack: "Stack 0"
        },
        {
          label: "Outstanding Balance (₹)",
          data: balance,
          type: "line",
          borderColor: "#10B981",
          borderWidth: 2,
          pointRadius: 0,
          fill: false,
          yAxisID: "y"
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { labels: { color: "#94A3B8", font: { size: 11 } } },
        tooltip: {
          callbacks: {
            label: function(ctx) {
              return `${ctx.dataset.label}: ₹${fmt(ctx.raw)}`;
            }
          }
        }
      },
      scales: {
        x: { ticks: { color: "#64748B", font: { size: 10 }, maxTicksLimit: 15 }, grid: { color: "rgba(255,255,255,0.05)" } },
        y: { ticks: { color: "#64748B", font: { size: 10 } }, grid: { color: "rgba(255,255,255,0.05)" } }
      }
    }
  });
}

async function loadTenureOptimizer(principal, rate, downPayment, feeVal, feeType, targetTenure) {
  try {
    const res = await fetch("/api/v1/loans/optimize-tenure", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeaders() },
      body: JSON.stringify({
        principal,
        annual_rate: rate,
        down_payment: downPayment,
        processing_fee_val: feeVal,
        processing_fee_type: feeType,
        target_tenure_months: targetTenure
      })
    });
    if (!res.ok) return;
    const data = await res.json();
    const tbody = document.getElementById("liTenureOptimizerBody");
    if (!tbody) return;

    tbody.innerHTML = data.scenarios.map(s => {
      let tagsHtml = s.tags.map(t => {
        if (t === "Lowest Total Cost") return `<span class="li-tag li-tag-cost">${t}</span>`;
        if (t === "Lowest EMI") return `<span class="li-tag li-tag-emi">${t}</span>`;
        if (t === "Balanced Option") return `<span class="li-tag li-tag-balanced">★ ${t}</span>`;
        return `<span class="pill pill-neutral">${t}</span>`;
      }).join(" ");

      const healthBadge = `<span class="pill pill-${s.badge_color}">${s.health_status}</span>`;

      return `
        <tr style="${s.tenure_months === targetTenure ? 'background:rgba(59,130,246,0.08);' : ''}">
          <td><strong>${s.tenure_display}</strong></td>
          <td style="font-family:var(--font-mono);font-weight:700;">₹${fmt(s.monthly_emi)}</td>
          <td style="font-family:var(--font-mono);color:#F59E0B;">₹${fmt(s.total_interest)}</td>
          <td style="font-family:var(--font-mono);">${s.foir.toFixed(1)}%</td>
          <td>${healthBadge}</td>
          <td>${tagsHtml}</td>
          <td>
            <button class="btn btn-ghost btn-sm" onclick="selectOptimizedTenure(${s.tenure_months})">Select</button>
          </td>
        </tr>
      `;
    }).join("");

    renderTradeOffChart(data.scenarios);
  } catch (e) {}
}

function selectOptimizedTenure(months) {
  document.getElementById("liTenureVal").value = months;
  document.getElementById("liTenureUnit").value = "months";
  runLoanPlannerCalc();
}

function renderTradeOffChart(scenarios) {
  const canvas = document.getElementById("liTradeOffCanvas");
  if (!canvas || !window.Chart) return;

  if (liChartTradeOffInstance) {
    liChartTradeOffInstance.destroy();
  }

  const labels = scenarios.map(s => s.tenure_display);
  const emis = scenarios.map(s => s.monthly_emi);
  const interests = scenarios.map(s => s.total_interest);

  const ctx = canvas.getContext("2d");
  liChartTradeOffInstance = new window.Chart(ctx, {
    type: "line",
    data: {
      labels: labels,
      datasets: [
        {
          label: "Monthly EMI (₹)",
          data: emis,
          borderColor: "#3B82F6",
          backgroundColor: "rgba(59, 130, 246, 0.1)",
          yAxisID: "yEMI",
          tension: 0.3,
          fill: true
        },
        {
          label: "Total Interest Paid (₹)",
          data: interests,
          borderColor: "#F59E0B",
          backgroundColor: "rgba(245, 158, 11, 0.1)",
          yAxisID: "yInterest",
          tension: 0.3,
          fill: true
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: "#94A3B8", font: { size: 11 } } }
      },
      scales: {
        x: { ticks: { color: "#64748B", font: { size: 10 } }, grid: { color: "rgba(255,255,255,0.05)" } },
        yEMI: { type: "linear", position: "left", title: { display: true, text: "EMI (₹)", color: "#3B82F6" }, ticks: { color: "#64748B" } },
        yInterest: { type: "linear", position: "right", title: { display: true, text: "Total Interest (₹)", color: "#F59E0B" }, ticks: { color: "#64748B" }, grid: { drawOnChartArea: false } }
      }
    }
  });
}

async function saveCurrentScenario() {
  if (!liCurrentPlannerData) return;
  const name = prompt("Enter a scenario name to save:", `${document.getElementById("liLoanType").value} Plan`);
  if (!name) return;

  try {
    const res = await fetch("/api/v1/loans/scenarios", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeaders() },
      body: JSON.stringify({
        scenario_name: name,
        loan_type: document.getElementById("liLoanType").value,
        principal: liCurrentPlannerData.net_principal,
        annual_rate: parseFloat(document.getElementById("liRate").value),
        tenure_months: liCurrentPlannerData.tenure_months,
        processing_fee: liCurrentPlannerData.processing_fee,
        down_payment: liCurrentPlannerData.down_payment,
        monthly_emi: liCurrentPlannerData.monthly_emi,
        total_interest: liCurrentPlannerData.total_interest,
        total_repayment: liCurrentPlannerData.total_payment,
        effective_total_cost: liCurrentPlannerData.effective_total_cost,
        foir: 0.0,
        affordability_result: "Comfortable",
        inputs: {
          principal: liCurrentPlannerData.gross_loan_amount,
          annual_rate: parseFloat(document.getElementById("liRate").value),
          tenure_months: liCurrentPlannerData.tenure_months
        },
        outputs: {
          monthly_emi: liCurrentPlannerData.monthly_emi,
          total_interest: liCurrentPlannerData.total_interest
        }
      })
    });
    if (res.ok) {
      alert("Scenario saved successfully!");
      loadUserLoanScenarios();
    }
  } catch (e) {}
}

async function loadUserLoanScenarios() {
  const tbody = document.getElementById("liScenariosBody");
  if (!tbody) return;
  try {
    const res = await fetch("/api/v1/loans/scenarios", { headers: getAuthHeaders() });
    if (!res.ok) return;
    const data = await res.json();
    if (data.scenarios.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;padding:16px;color:var(--text-muted);">No saved scenarios yet. Click 'Save' in the planner above.</td></tr>`;
      return;
    }
    tbody.innerHTML = data.scenarios.map(s => `
      <tr>
        <td><strong>${s.scenario_name}</strong></td>
        <td>${s.loan_type}</td>
        <td style="font-family:var(--font-mono);">₹${fmt(s.principal)}</td>
        <td style="font-family:var(--font-mono);">${s.annual_rate}%</td>
        <td style="font-family:var(--font-mono);">${s.tenure_months}M</td>
        <td style="font-family:var(--font-mono);font-weight:700;color:var(--primary);">₹${fmt(s.monthly_emi)}</td>
        <td><span class="pill pill-success">${s.affordability_result}</span></td>
        <td>
          <button class="btn btn-ghost btn-sm" onclick="applySavedScenario(${s.principal}, ${s.annual_rate}, ${s.tenure_months}, '${s.loan_type}')">Load</button>
          <button class="btn btn-ghost btn-sm" style="color:var(--danger);" onclick="deleteSavedScenario('${s.id}')">Delete</button>
        </td>
      </tr>
    `).join("");
  } catch (e) {}
}

function applySavedScenario(principal, rate, tenureMonths, loanType) {
  document.getElementById("liPrincipal").value = principal;
  document.getElementById("liRate").value = rate;
  document.getElementById("liTenureVal").value = tenureMonths;
  document.getElementById("liTenureUnit").value = "months";
  if (document.getElementById("liLoanType")) document.getElementById("liLoanType").value = loanType;
  runLoanPlannerCalc();
}

async function deleteSavedScenario(id) {
  if (!confirm("Are you sure you want to delete this saved scenario?")) return;
  try {
    const res = await fetch(`/api/v1/loans/scenarios/${id}`, {
      method: "DELETE",
      headers: getAuthHeaders()
    });
    if (res.ok) {
      loadUserLoanScenarios();
    }
  } catch (e) {}
}

async function runAffordabilityCalc() {
  const income = parseFloat(document.getElementById("liAffIncome").value) || 0;
  const proposedEmi = parseFloat(document.getElementById("liAffProposedEmi").value) || 0;
  const existingEmi = parseFloat(document.getElementById("liAffExistingEmi").value) || 0;
  const rent = parseFloat(document.getElementById("liAffRent").value) || 0;
  const otherFixed = parseFloat(document.getElementById("liAffOtherFixed").value) || 0;
  const essentials = parseFloat(document.getElementById("liAffEssentials").value) || 0;

  try {
    const res = await fetch("/api/v1/loans/affordability", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeaders() },
      body: JSON.stringify({
        monthly_income: income,
        proposed_emi: proposedEmi,
        existing_emi: existingEmi,
        housing_rent: rent,
        other_fixed_obligations: otherFixed,
        essential_expenses: essentials
      })
    });
    if (!res.ok) return;
    const data = await res.json();

    document.getElementById("liAffExistingFoir").textContent = data.existing_foir.toFixed(1) + "%";
    document.getElementById("liAffNewFoir").textContent = data.new_foir.toFixed(1) + "%";
    document.getElementById("liAffEmiRatio").textContent = data.emi_to_income_ratio.toFixed(1) + "%";
    document.getElementById("liAffDispBefore").textContent = "₹" + fmt(data.disposable_income_before);
    document.getElementById("liAffDispAfter").textContent = "₹" + fmt(data.disposable_income_after);
    document.getElementById("liAffRepayCap").textContent = "₹" + fmt(data.repayment_capacity);
    document.getElementById("liAffExplanation").textContent = data.explanation;

    document.getElementById("liAffHealthPill").className = `pill pill-${data.badge_color}`;
    document.getElementById("liAffHealthPill").textContent = data.health_status;
  } catch (e) {}
}

async function autoFillAffordabilityFromProfile() {
  try {
    const res = await fetch("/api/v1/user/profile", { headers: getAuthHeaders() });
    if (!res.ok) return;
    const data = await res.json();
    if (data.financial_profile) {
      document.getElementById("liAffIncome").value = data.financial_profile.monthly_income;
      document.getElementById("liAffExistingEmi").value = data.financial_profile.existing_emi;
      if (liCurrentPlannerData) {
        document.getElementById("liAffProposedEmi").value = liCurrentPlannerData.monthly_emi;
      }
      runAffordabilityCalc();
    }
  } catch (e) {}
}

async function runLoanComparison() {
  const o1 = {
    offer_name: document.getElementById("liCmpName1").value,
    principal: parseFloat(document.getElementById("liCmpP1").value) || 0,
    annual_rate: parseFloat(document.getElementById("liCmpR1").value) || 0,
    tenure_months: parseInt(document.getElementById("liCmpT1").value) || 36,
    processing_fee: parseFloat(document.getElementById("liCmpF1").value) || 0
  };
  const o2 = {
    offer_name: document.getElementById("liCmpName2").value,
    principal: parseFloat(document.getElementById("liCmpP2").value) || 0,
    annual_rate: parseFloat(document.getElementById("liCmpR2").value) || 0,
    tenure_months: parseInt(document.getElementById("liCmpT2").value) || 36,
    processing_fee: parseFloat(document.getElementById("liCmpF2").value) || 0
  };
  const o3 = {
    offer_name: document.getElementById("liCmpName3").value,
    principal: parseFloat(document.getElementById("liCmpP3").value) || 0,
    annual_rate: parseFloat(document.getElementById("liCmpR3").value) || 0,
    tenure_months: parseInt(document.getElementById("liCmpT3").value) || 36,
    processing_fee: parseFloat(document.getElementById("liCmpF3").value) || 0
  };

  try {
    const res = await fetch("/api/v1/loans/compare", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeaders() },
      body: JSON.stringify({ offers: [o1, o2, o3] })
    });
    if (!res.ok) return;
    const data = await res.json();
    const offers = data.offers;

    document.getElementById("liCmpResultsCard").style.display = "block";
    document.getElementById("liCmpCol1").textContent = offers[0]?.offer_name || "Offer 1";
    document.getElementById("liCmpCol2").textContent = offers[1]?.offer_name || "Offer 2";
    document.getElementById("liCmpCol3").textContent = offers[2]?.offer_name || "Offer 3";

    const rows = [
      { label: "Loan Amount", key: "gross_principal", prefix: "₹" },
      { label: "Interest Rate", key: "annual_rate", suffix: "%" },
      { label: "Tenure", key: "tenure_months", suffix: " Months" },
      { label: "Monthly EMI", key: "monthly_emi", prefix: "₹", bold: true },
      { label: "Total Interest", key: "total_interest", prefix: "₹" },
      { label: "Processing Fee", key: "total_fees", prefix: "₹" },
      { label: "Effective Total Cost", key: "effective_total_cost", prefix: "₹", bold: true },
      { label: "Modeled FOIR", key: "foir", suffix: "%" }
    ];

    let tbodyHtml = rows.map(r => {
      let cells = offers.map(o => {
        let val = o[r.key];
        if (r.prefix) val = r.prefix + fmt(val);
        else if (r.suffix) val = val + r.suffix;
        return `<td style="${r.bold ? 'font-weight:700;color:var(--primary);' : ''}">${val}</td>`;
      }).join("");
      return `<tr><td><strong>${r.label}</strong></td>${cells}</tr>`;
    }).join("");

    // Highlights Row
    let highlightsCells = offers.map(o => {
      let tags = o.highlights.map(h => `<span class="li-tag li-tag-cost" style="margin-right:2px;">${h}</span>`).join(" ");
      return `<td>${tags || '—'}</td>`;
    }).join("");
    tbodyHtml += `<tr style="background:rgba(255,255,255,0.02);"><td><strong>Best Highlights</strong></td>${highlightsCells}</tr>`;

    document.getElementById("liCmpTableBody").innerHTML = tbodyHtml;
    document.getElementById("liCmpSummaryNote").textContent = data.summary_note;
  } catch (e) {}
}

async function runPrepaymentSimulation() {
  const p = parseFloat(document.getElementById("liPrepP").value) || 0;
  const r = parseFloat(document.getElementById("liPrepR").value) || 0;
  const t = parseInt(document.getElementById("liPrepT").value) || 36;
  const amt = parseFloat(document.getElementById("liPrepAmt").value) || 0;
  const month = parseInt(document.getElementById("liPrepMonth").value) || 12;
  const strat = document.getElementById("liPrepStrategy").value;
  const extraMonthly = parseFloat(document.getElementById("liPrepExtraMonthly").value) || 0;

  try {
    const res = await fetch("/api/v1/loans/prepayment", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeaders() },
      body: JSON.stringify({
        principal: p,
        annual_rate: r,
        tenure_months: t,
        prepayment_amount: amt,
        prepayment_month: month,
        strategy: strat,
        extra_monthly_payment: extraMonthly
      })
    });
    if (!res.ok) return;
    const data = await res.json();

    document.getElementById("liPrepResInterestSaved").textContent = "₹" + fmt(data.interest_saved);
    document.getElementById("liPrepResMonthsSaved").textContent = data.months_saved + " Months";
    document.getElementById("liPrepResOrigDate").textContent = data.original_end_date;
    document.getElementById("liPrepResNewDate").textContent = data.new_end_date;
    document.getElementById("liPrepResTotalBefore").textContent = "₹" + fmt(data.original_total_repayment);
    document.getElementById("liPrepResTotalAfter").textContent = "₹" + fmt(data.new_total_repayment);
    document.getElementById("liPrepNarrative").textContent = data.narrative;
  } catch (e) {}
}

function setExtraEmiChip(amount) {
  document.getElementById("liPrepExtraMonthly").value = amount;
  runPrepaymentSimulation();
}

function toggleAmortizationView(mode) {
  document.getElementById("liAmortToggleMonthly").classList.toggle("active", mode === "monthly");
  document.getElementById("liAmortToggleYearly").classList.toggle("active", mode === "yearly");
  if (liCurrentPlannerData) {
    const list = (mode === "yearly") ? liCurrentPlannerData.yearly_schedule : liCurrentPlannerData.schedule;
    renderAmortizationTable(list, mode);
  }
}

function renderAmortizationTable(schedule, mode) {
  const tbody = document.getElementById("liAmortTableBody");
  const thPeriod = document.getElementById("liAmortColPeriod");
  if (!tbody) return;

  if (thPeriod) thPeriod.textContent = (mode === "yearly") ? "Year" : "Month";

  if (!schedule || schedule.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:20px;">No schedule data.</td></tr>`;
    return;
  }

  tbody.innerHTML = schedule.map(item => `
    <tr>
      <td><strong>${mode === "yearly" ? 'Year ' + item.year : 'Month ' + item.month}</strong></td>
      <td style="font-family:var(--font-mono);">₹${fmt(item.opening_balance)}</td>
      <td style="font-family:var(--font-mono);font-weight:700;">₹${fmt(item.emi || item.total_emi)}</td>
      <td style="font-family:var(--font-mono);color:var(--primary);">₹${fmt(item.principal_paid)}</td>
      <td style="font-family:var(--font-mono);color:#F59E0B;">₹${fmt(item.interest_paid)}</td>
      <td style="font-family:var(--font-mono);">₹${fmt(item.extra_payment || 0)}</td>
      <td style="font-family:var(--font-mono);">₹${fmt(item.closing_balance)}</td>
    </tr>
  `).join("");
}

function exportAmortizationCsv() {
  if (!liCurrentPlannerData || !liCurrentPlannerData.schedule) {
    alert("Please calculate a loan plan first.");
    return;
  }

  let csvContent = "data:text/csv;charset=utf-8,";
  csvContent += "Month,Opening Balance,EMI,Principal Paid,Interest Paid,Closing Balance\n";

  liCurrentPlannerData.schedule.forEach(row => {
    csvContent += `${row.month},${row.opening_balance},${row.emi},${row.principal_paid},${row.interest_paid},${row.closing_balance}\n`;
  });

  const encodedUri = encodeURI(csvContent);
  const link = document.createElement("a");
  link.setAttribute("href", encodedUri);
  link.setAttribute("download", `Amortization_Schedule_${liCurrentPlannerData.net_principal}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
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
