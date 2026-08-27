from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any


VALID_HOUSING = {"own", "rent", "free"}
VALID_SAVINGS = {"none", "little", "moderate", "quite rich", "rich"}
VALID_CHECKING = {"none", "little", "moderate", "rich"}
VALID_PURPOSES = {"car", "furniture/equipment", "radio/tv", "domestic appliances", "repairs", "education", "business", "vacation/others"}
VALID_GENDERS = {"male", "female"}


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
    principal: float = Field(1000000.0, gt=0, le=100000000)
    annual_rate: float = Field(9.5, ge=1.0, le=45.0)
    tenure_years: int = Field(5, ge=1, le=30)


# Auth Schemas
class UserLoginRequest(BaseModel):
    email: str
    password: str


class UserRegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    full_name: str
    role: str
