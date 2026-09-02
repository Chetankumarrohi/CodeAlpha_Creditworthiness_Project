from pydantic import BaseModel, Field, field_validator, EmailStr
from typing import Optional, List, Dict, Any


VALID_HOUSING = {"own", "rent", "free"}
VALID_SAVINGS = {"none", "little", "moderate", "quite rich", "rich"}
VALID_CHECKING = {"none", "little", "moderate", "rich"}
VALID_PURPOSES = {"car", "furniture/equipment", "radio/tv", "domestic appliances", "repairs", "education", "business", "vacation/others"}
VALID_GENDERS = {"male", "female"}


# ─── Assessment & Simulation Schemas ──────────────────────────────────────────

class AssessmentRequest(BaseModel):
    applicant_name: str = Field("Alex Morgan", min_length=2, max_length=100, description="Full legal name of credit applicant")
    age: int = Field(32, ge=18, le=90, description="Applicant age in years (18-90)")
    sex: str = Field("male", description="Gender (male/female)")
    job: str = Field("Skilled", description="Job category (Unskilled, Skilled, Highly Skilled, Management)")
    housing: str = Field("own", description="Housing status (own, rent, free)")
    saving_accounts: str = Field("moderate", description="Savings balance tier")
    checking_account: str = Field("moderate", description="Checking account standing")
    purpose: str = Field("car", description="Loan purpose")
    monthly_income: float = Field(75000.0, gt=0, le=10000000, description="Monthly net income (₹)")
    existing_emi: float = Field(10000.0, ge=0, le=5000000, description="Existing monthly debt obligations (₹)")
    credit_amount: float = Field(200000.0, ge=1000, le=50000000, description="Requested credit amount (₹)")
    duration: int = Field(18, ge=6, le=84, description="Loan tenure in months (6-84)")
    savings_balance: float = Field(150000.0, ge=0, description="Liquid savings balance (₹)")

    @field_validator("housing")
    def validate_housing(cls, v):
        val = v.lower().strip()
        if val not in VALID_HOUSING:
            raise ValueError(f"Invalid housing status '{v}'. Allowed: {sorted(VALID_HOUSING)}")
        return val

    @field_validator("saving_accounts")
    def validate_savings(cls, v):
        val = v.lower().strip()
        if val not in VALID_SAVINGS:
            raise ValueError(f"Invalid savings status '{v}'. Allowed: {sorted(VALID_SAVINGS)}")
        return val

    @field_validator("checking_account")
    def validate_checking(cls, v):
        val = v.lower().strip()
        if val not in VALID_CHECKING:
            raise ValueError(f"Invalid checking status '{v}'. Allowed: {sorted(VALID_CHECKING)}")
        return val

    @field_validator("sex")
    def validate_sex(cls, v):
        val = v.lower().strip()
        if val not in VALID_GENDERS:
            raise ValueError(f"Invalid gender '{v}'. Allowed: {sorted(VALID_GENDERS)}")
        return val


class SimulationRequest(BaseModel):
    monthly_income: float = Field(75000.0, gt=0, le=10000000)
    existing_emi: float = Field(10000.0, ge=0, le=5000000)
    savings_balance: float = Field(150000.0, ge=0)
    credit_amount: float = Field(200000.0, ge=1000, le=50000000)
    duration: int = Field(18, ge=6, le=84)
    age: int = Field(32, ge=18, le=90)


class LoanEmiRequest(BaseModel):
    principal: float = Field(1000000.0, ge=0, le=100000000)
    annual_rate: float = Field(9.5, ge=0.0, le=100.0)
    tenure_years: Optional[int] = Field(None, ge=1, le=40)
    tenure_months: Optional[int] = Field(None, ge=1, le=480)
    loan_type: Optional[str] = Field("Personal Loan")
    processing_fee_val: Optional[float] = Field(0.0, ge=0.0)
    processing_fee_type: Optional[str] = Field("percentage")
    down_payment: Optional[float] = Field(0.0, ge=0.0)
    start_date: Optional[str] = Field(None)


class LoanAffordabilityRequest(BaseModel):
    monthly_income: float = Field(0.0, ge=0.0)
    proposed_emi: float = Field(0.0, ge=0.0)
    existing_emi: Optional[float] = Field(0.0, ge=0.0)
    housing_rent: Optional[float] = Field(0.0, ge=0.0)
    other_fixed_obligations: Optional[float] = Field(0.0, ge=0.0)
    essential_expenses: Optional[float] = Field(0.0, ge=0.0)
    dependents: Optional[int] = Field(0, ge=0)


class TenureOptimizeRequest(BaseModel):
    principal: float = Field(1000000.0, ge=0.0)
    annual_rate: float = Field(9.5, ge=0.0)
    down_payment: Optional[float] = Field(0.0, ge=0.0)
    processing_fee_val: Optional[float] = Field(0.0, ge=0.0)
    processing_fee_type: Optional[str] = Field("percentage")
    monthly_income: Optional[float] = Field(0.0, ge=0.0)
    existing_fixed_obligations: Optional[float] = Field(0.0, ge=0.0)
    target_tenure_months: Optional[int] = Field(36, ge=1)


class LoanPrepaymentRequest(BaseModel):
    principal: float = Field(1000000.0, ge=0.0)
    annual_rate: float = Field(9.5, ge=0.0)
    tenure_months: int = Field(36, ge=1)
    prepayment_amount: Optional[float] = Field(0.0, ge=0.0)
    prepayment_month: Optional[int] = Field(12, ge=1)
    strategy: Optional[str] = Field("reduce_tenure")  # "reduce_tenure" | "reduce_emi"
    extra_monthly_payment: Optional[float] = Field(0.0, ge=0.0)
    start_date: Optional[str] = Field(None)


class LoanOfferItem(BaseModel):
    offer_name: str = Field("Offer A")
    principal: float = Field(1000000.0, ge=0.0)
    annual_rate: float = Field(9.5, ge=0.0)
    tenure_months: int = Field(36, ge=1)
    processing_fee: Optional[float] = Field(0.0, ge=0.0)
    processing_fee_type: Optional[str] = Field("percentage")
    other_upfront_fees: Optional[float] = Field(0.0, ge=0.0)
    down_payment: Optional[float] = Field(0.0, ge=0.0)
    prepayment_notes: Optional[str] = Field(None)


class LoanCompareRequest(BaseModel):
    offers: List[LoanOfferItem] = Field(default_factory=list)
    monthly_income: Optional[float] = Field(0.0, ge=0.0)
    existing_fixed_obligations: Optional[float] = Field(0.0, ge=0.0)


class LoanScenarioCreateRequest(BaseModel):
    scenario_name: str = Field("My Loan Plan")
    loan_type: str = Field("Personal Loan")
    principal: float = Field(..., ge=0.0)
    annual_rate: float = Field(..., ge=0.0)
    tenure_months: int = Field(..., ge=1)
    processing_fee: Optional[float] = Field(0.0, ge=0.0)
    down_payment: Optional[float] = Field(0.0, ge=0.0)
    monthly_emi: float = Field(..., ge=0.0)
    total_interest: float = Field(..., ge=0.0)
    total_repayment: float = Field(..., ge=0.0)
    effective_total_cost: float = Field(..., ge=0.0)
    foir: Optional[float] = Field(0.0, ge=0.0)
    affordability_result: Optional[str] = Field("Comfortable")
    inputs: Optional[Dict[str, Any]] = Field(default_factory=dict)
    outputs: Optional[Dict[str, Any]] = Field(default_factory=dict)



# ─── Auth & User Account Schemas ──────────────────────────────────────────────

class UserLoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=6, max_length=128)
    remember_me: Optional[bool] = Field(True)


class UserRegisterRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=8, max_length=128, description="Minimum 8 characters")
    full_name: Optional[str] = Field(None)
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    dob: Optional[str] = Field(None, max_length=32)
    gender: Optional[str] = Field(None, max_length=32)
    phone_number: Optional[str] = Field(None, max_length=32)


class EmailVerifyRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    code: str = Field(..., min_length=6, max_length=6)


class ResendVerificationRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)


class TwoFactorVerifyRequest(BaseModel):
    temp_token: str
    code: str = Field(..., min_length=4, max_length=20)  # can be 6-digit TOTP or recovery code XXXX-XXXX
    is_recovery_code: Optional[bool] = False


class TwoFactorSetupResponse(BaseModel):
    secret: str
    otpauth_uri: str
    qr_code_data_url: str


class TwoFactorConfirmRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=6)


class TwoFactorDisableRequest(BaseModel):
    password: Optional[str] = None
    code: Optional[str] = None


class GoogleAuthRequest(BaseModel):
    id_token: Optional[str] = None
    code: Optional[str] = None
    email: Optional[str] = None
    full_name: Optional[str] = None
    provider_user_id: Optional[str] = None


class GoogleAuthUrlResponse(BaseModel):
    auth_url: str
    state: str


class AuthTokenResponse(BaseModel):
    access_token: Optional[str] = None
    token_type: str = "bearer"
    user_id: Optional[str] = None
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[str] = "USER"   # "USER" | "ADMIN"
    expires_in_minutes: int = 120
    requires_2fa: bool = False
    temp_token: Optional[str] = None
    two_factor_method: Optional[str] = None
    requires_verification: bool = False
    message: Optional[str] = None


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    is_active: bool
    email_verified: bool
    two_factor_enabled: bool = False
    two_factor_method: Optional[str] = "totp"
    created_at: str
    last_login_at: Optional[str] = None


class UserSessionResponse(BaseModel):
    id: str
    device_info: str
    ip_address: str
    last_active_at: str
    expires_at: str
    is_current: bool = False


class SecuritySettingsResponse(BaseModel):
    two_factor_enabled: bool
    two_factor_method: Optional[str]
    has_google_linked: bool
    active_sessions: List[UserSessionResponse]


class UserProfileUpdateRequest(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(..., min_length=6)
    new_password: str = Field(..., min_length=8, max_length=128)


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    email: str
    reset_token: str
    new_password: str = Field(..., min_length=8, max_length=128)


class UserStatusUpdateRequest(BaseModel):
    is_active: bool


# ─── Financial Profile Schema ─────────────────────────────────────────────────

class FinancialProfileRequest(BaseModel):
    monthly_income: Optional[float] = Field(50000.0, gt=0)
    existing_emi: Optional[float] = Field(0.0, ge=0)
    savings_balance: Optional[float] = Field(100000.0, ge=0)
    housing_type: Optional[str] = Field("own")
    employment_status: Optional[str] = Field("skilled")
    credit_purpose: Optional[str] = Field("personal")


# ─── Admin Inspection Schemas ─────────────────────────────────────────────────

class UserDetailAdminResponse(BaseModel):
    user: UserResponse
    financial_profile: Optional[Dict[str, Any]] = None
    assessment_count: int
    simulation_count: int
    report_count: int
    recent_assessments: List[Dict[str, Any]]
    recent_simulations: List[Dict[str, Any]]
    recent_activities: List[Dict[str, Any]]
