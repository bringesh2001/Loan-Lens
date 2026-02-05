"""
Pydantic models for LoanLens API responses.
Matches the schemas defined in API_DESIGN.md
"""

from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field


# ==========================================================================
# DOCUMENT UPLOAD
# ==========================================================================

class DocumentUploadResponse(BaseModel):
    """Response after uploading a PDF document."""
    document_id: str = Field(..., example="doc_abc123xyz")
    filename: str = Field(..., example="loan_agreement.pdf")
    uploaded_at: datetime
    status: Literal["processing", "complete", "failed"] = "processing"


# ==========================================================================
# SUMMARY RESPONSE
# ==========================================================================

class KeyNumbers(BaseModel):
    """Core financial numbers extracted from the loan document."""
    total_loan: float = Field(..., description="Principal loan amount", example=25000.00)
    monthly_payment: float = Field(..., description="Monthly payment amount", example=562.14)
    interest_rate: float = Field(..., description="Annual interest rate as percentage", example=12.50)
    term_months: int = Field(..., description="Loan term in months", example=60)
    total_interest: float = Field(..., description="Total interest over loan lifetime", example=8728.40)
    fees: Optional[float] = Field(None, description="Total fees if found")


class Highlight(BaseModel):
    """A key highlight about the loan terms."""
    type: Literal["positive", "negative", "warning"]
    text: str = Field(..., example="High Interest Rate")


class SummaryData(BaseModel):
    """The summary analysis data."""
    document_type: str = Field(..., example="Personal Loan Agreement")
    overview: str = Field(
        ..., 
        description="Plain English summary of the loan",
        example="This is a standard Personal Loan Agreement for $25,000..."
    )
    key_numbers: KeyNumbers
    highlights: list[Highlight]


class SummaryResponse(BaseModel):
    """Complete summary endpoint response."""
    document_id: str
    status: Literal["complete", "processing", "failed"]
    data: Optional[SummaryData] = None
    error: Optional[str] = None


# ==========================================================================
# RED FLAGS RESPONSE
# ==========================================================================

class Location(BaseModel):
    """Location of an item in the document."""
    page: int
    section: str


class RedFlag(BaseModel):
    """An AI-detected red flag in the loan document."""
    id: str = Field(..., example="rf_001")
    severity: Literal["high", "medium", "low"]
    title: str = Field(..., example="Excessive Late Payment Fee")
    description: str = Field(..., description="Why this is problematic")
    location: Location
    recommendation: str = Field(..., description="Actionable advice")


class RedFlagsResponse(BaseModel):
    """Complete red flags endpoint response."""
    document_id: str
    status: Literal["complete", "processing", "failed"]
    count: int = 0
    data: list[RedFlag] = []
    error: Optional[str] = None


# ==========================================================================
# HIDDEN CLAUSES RESPONSE
# ==========================================================================

class HiddenClause(BaseModel):
    """An AI-detected hidden or complex clause."""
    id: str = Field(..., example="hc_001")
    category: str = Field(..., example="prepayment", description="Category like prepayment, arbitration, fees")
    title: str = Field(..., example="Prepayment Penalty")
    summary: str = Field(..., description="1-line summary")
    original_text: str = Field(..., description="Exact text from document")
    plain_english: str = Field(..., description="Simple language translation")
    impact: Literal["high", "medium", "low"]
    location: Location


class HiddenClausesResponse(BaseModel):
    """Complete hidden clauses endpoint response."""
    document_id: str
    status: Literal["complete", "processing", "failed"]
    count: int = 0
    data: list[HiddenClause] = []
    error: Optional[str] = None


# ==========================================================================
# FINANCIAL TERMS RESPONSE
# ==========================================================================

class TermExample(BaseModel):
    """Example usage of a financial term."""
    icon: str = Field(..., example="💡")
    title: str = Field(..., example="Simple Example")
    text: str = Field(..., description="Example using values from the document")


class FinancialTerm(BaseModel):
    """An AI-extracted financial term with explanation."""
    id: str = Field(..., example="term_001")
    name: str = Field(..., example="APR")
    full_name: str = Field(..., example="Annual Percentage Rate")
    short_description: str
    definition: str = Field(..., description="Plain English explanation")
    example: TermExample
    your_value: str = Field(..., description="Value from this document", example="13.2%")
    location: Location


class FinancialTermsResponse(BaseModel):
    """Complete financial terms endpoint response."""
    document_id: str
    status: Literal["complete", "processing", "failed"]
    count: int = 0
    terms: list[FinancialTerm] = []
    error: Optional[str] = None


# ==========================================================================
# CHAT RESPONSE
# ==========================================================================

class ChatReference(BaseModel):
    """Reference to a clause in the document."""
    clause_id: Optional[str] = None
    page: int
    section: str


class ChatRequest(BaseModel):
    """Chat request body."""
    message: str = Field(..., example="Can I pay off this loan early without penalty?")
    conversation_id: Optional[str] = Field(None, description="For maintaining context")


class ChatResponse(BaseModel):
    """Chat endpoint response."""
    document_id: str
    conversation_id: str
    response: str
    references: list[ChatReference] = []

