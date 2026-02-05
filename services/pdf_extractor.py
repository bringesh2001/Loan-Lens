"""
PDF Text Extraction and Number Parsing Service

This module handles:
1. Extracting raw text from PDF documents
2. Rule-based parsing to find numeric candidates (loan amount, interest rate, term, fees)
3. Preparing structured data for LLM disambiguation
"""

import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional
from io import BytesIO

import pdfplumber


@dataclass
class NumericCandidate:
    """A potential numeric value found in the document."""
    value: float
    raw_text: str
    page: int
    context: str  # surrounding text for LLM reference


@dataclass
class ExtractedNumbers:
    """All numeric candidates extracted via regex from the PDF."""
    loan_amounts: list[NumericCandidate] = field(default_factory=list)
    interest_rates: list[NumericCandidate] = field(default_factory=list)
    term_months: list[NumericCandidate] = field(default_factory=list)
    monthly_payments: list[NumericCandidate] = field(default_factory=list)
    fees: list[NumericCandidate] = field(default_factory=list)


@dataclass
class PDFExtraction:
    """Complete extraction result from a PDF."""
    full_text: str
    text_by_page: dict[int, str]
    numeric_candidates: ExtractedNumbers


class PDFExtractor:
    """
    Extracts text and numeric values from loan document PDFs.
    
    Two-phase approach:
    1. Rule-based regex parsing to find candidate values
    2. Results passed to LLM for disambiguation and calculation
    """
    
    # ==========================================================================
    # REGEX PATTERNS FOR LOAN DOCUMENT NUMBERS
    # ==========================================================================
    
    # Currency amounts - supports multiple formats:
    # - US/Western: $25,000 or $25,000.00
    # - Indian: Rs 25,00,000 or ₹25,00,000 or RS 25,00,000 (lakhs/crores)
    # - Plain numbers: 25000 or 25000.00
    CURRENCY_PATTERN = r'(?:RS\.?|Rs\.?|₹|\$)?\s*([\d,]+(?:\.\d{2})?)'
    
    # Percentage values: 12.5% or 12.5 percent
    PERCENT_PATTERN = r'(\d+(?:\.\d+)?)\s*(?:%|percent)'
    
    # Term/duration: 60 months, 5 years, 36-month
    TERM_PATTERN = r'(\d+)\s*[-\s]?(?:months?|mos?\.?)|(\d+)\s*[-\s]?(?:years?|yrs?\.?)'
    
    # Keywords that indicate specific value types
    LOAN_KEYWORDS = [
        r'loan\s*amount', r'principal', r'amount\s*financed', 
        r'total\s*loan', r'borrowing', r'credit\s*amount',
        r'loan\s*sanctioned', r'sanctioned\s*amount'
    ]
    
    INTEREST_KEYWORDS = [
        r'interest\s*rate', r'annual\s*percentage\s*rate', r'apr',
        r'rate\s*of\s*interest', r'fixed\s*rate', r'variable\s*rate'
    ]
    
    PAYMENT_KEYWORDS = [
        r'monthly\s*payment', r'payment\s*amount', r'installment',
        r'periodic\s*payment', r'emi', r'monthly\s*installment'
    ]
    
    TERM_KEYWORDS = [
        r'loan\s*term', r'repayment\s*period', r'tenor', r'duration',
        r'maturity', r'term\s*of\s*loan'
    ]
    
    FEE_KEYWORDS = [
        r'processing\s*fee', r'origination\s*fee', r'late\s*fee',
        r'prepayment\s*penalty', r'service\s*charge', r'closing\s*cost'
    ]
    
    def __init__(self):
        # Compile regex patterns for efficiency
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Pre-compile regex patterns for better performance."""
        # Build context-aware patterns: keyword + nearby currency/percent
        self.loan_amount_pattern = self._build_keyword_value_pattern(
            self.LOAN_KEYWORDS, self.CURRENCY_PATTERN
        )
        self.interest_rate_pattern = self._build_keyword_value_pattern(
            self.INTEREST_KEYWORDS, self.PERCENT_PATTERN
        )
        self.payment_pattern = self._build_keyword_value_pattern(
            self.PAYMENT_KEYWORDS, self.CURRENCY_PATTERN
        )
        self.term_pattern = re.compile(
            r'(?:' + '|'.join(self.TERM_KEYWORDS) + r')[^0-9]*' + self.TERM_PATTERN,
            re.IGNORECASE
        )
        self.fee_pattern = self._build_keyword_value_pattern(
            self.FEE_KEYWORDS, self.CURRENCY_PATTERN
        )
        
        # Standalone patterns for fallback detection
        self.standalone_currency = re.compile(self.CURRENCY_PATTERN)
        self.standalone_percent = re.compile(self.PERCENT_PATTERN, re.IGNORECASE)
        self.standalone_term = re.compile(self.TERM_PATTERN, re.IGNORECASE)
    
    def _build_keyword_value_pattern(
        self, keywords: list[str], value_pattern: str
    ) -> re.Pattern:
        """Build a regex that matches: keyword ... value (within ~50 chars)."""
        keyword_group = '|'.join(keywords)
        # Match keyword, then up to 50 chars of non-newline, then the value
        pattern = rf'(?:{keyword_group})[^\n]{{0,50}}?{value_pattern}'
        return re.compile(pattern, re.IGNORECASE)
    
    # ==========================================================================
    # PDF TEXT EXTRACTION
    # ==========================================================================
    
    def extract_text(self, pdf_bytes: bytes) -> tuple[str, dict[int, str]]:
        """
        Extract text from PDF, returning full text and per-page breakdown.
        
        Args:
            pdf_bytes: Raw PDF file content
            
        Returns:
            Tuple of (full_text, {page_num: page_text})
        """
        text_by_page = {}
        full_text_parts = []
        
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                page_text = page.extract_text() or ""
                text_by_page[page_num] = page_text
                full_text_parts.append(f"--- PAGE {page_num} ---\n{page_text}")
        
        full_text = "\n\n".join(full_text_parts)
        return full_text, text_by_page
    
    # ==========================================================================
    # NUMBER EXTRACTION METHODS
    # ==========================================================================
    
    def extract_numbers(self, pdf_bytes: bytes) -> PDFExtraction:
        """
        Main extraction method: gets text and finds all numeric candidates.
        
        Args:
            pdf_bytes: Raw PDF file content
            
        Returns:
            PDFExtraction with full text, per-page text, and numeric candidates
        """
        full_text, text_by_page = self.extract_text(pdf_bytes)
        
        candidates = ExtractedNumbers()
        
        # Process each page to maintain location info
        for page_num, page_text in text_by_page.items():
            self._extract_from_page(page_text, page_num, candidates)
        
        return PDFExtraction(
            full_text=full_text,
            text_by_page=text_by_page,
            numeric_candidates=candidates
        )
    
    def _extract_from_page(
        self, 
        page_text: str, 
        page_num: int, 
        candidates: ExtractedNumbers
    ):
        """Extract numeric candidates from a single page."""
        
        # 1. Loan amounts (keyword + currency)
        for match in self.loan_amount_pattern.finditer(page_text):
            value = self._parse_currency(match.group(1))
            if value and 1000 <= value <= 10_000_000:  # Reasonable loan range
                candidates.loan_amounts.append(NumericCandidate(
                    value=value,
                    raw_text=match.group(0),
                    page=page_num,
                    context=self._get_context(page_text, match.start(), match.end())
                ))
        
        # 2. Interest rates (keyword + percentage)
        for match in self.interest_rate_pattern.finditer(page_text):
            value = float(match.group(1))
            if 0 < value <= 50:  # Reasonable interest rate range
                candidates.interest_rates.append(NumericCandidate(
                    value=value,
                    raw_text=match.group(0),
                    page=page_num,
                    context=self._get_context(page_text, match.start(), match.end())
                ))
        
        # 3. Monthly payments (keyword + currency)
        for match in self.payment_pattern.finditer(page_text):
            value = self._parse_currency(match.group(1))
            if value and 50 <= value <= 100_000:  # Reasonable payment range
                candidates.monthly_payments.append(NumericCandidate(
                    value=value,
                    raw_text=match.group(0),
                    page=page_num,
                    context=self._get_context(page_text, match.start(), match.end())
                ))
        
        # 4. Loan term
        for match in self.term_pattern.finditer(page_text):
            months_val = match.group(1)
            years_val = match.group(2)
            
            if months_val:
                value = int(months_val)
            elif years_val:
                value = int(years_val) * 12
            else:
                continue
                
            if 6 <= value <= 480:  # 6 months to 40 years
                candidates.term_months.append(NumericCandidate(
                    value=float(value),
                    raw_text=match.group(0),
                    page=page_num,
                    context=self._get_context(page_text, match.start(), match.end())
                ))
        
        # 5. Fees (keyword + currency)
        for match in self.fee_pattern.finditer(page_text):
            value = self._parse_currency(match.group(1))
            if value and 0 < value <= 50_000:  # Reasonable fee range
                candidates.fees.append(NumericCandidate(
                    value=value,
                    raw_text=match.group(0),
                    page=page_num,
                    context=self._get_context(page_text, match.start(), match.end())
                ))
    
    def _parse_currency(self, raw: str) -> Optional[float]:
        """Parse a currency string like '$25,000.00' or 'Rs 25,00,000' to float."""
        try:
            # Remove all currency symbols and formatting
            cleaned = raw.upper()
            for char in ['$', '₹', 'RS', 'RS.', ',', ' ']:
                cleaned = cleaned.replace(char, '')
            cleaned = cleaned.strip('.')
            return float(Decimal(cleaned))
        except:
            return None
    
    def _get_context(self, text: str, start: int, end: int, window: int = 100) -> str:
        """Get surrounding text context for a match."""
        ctx_start = max(0, start - window)
        ctx_end = min(len(text), end + window)
        context = text[ctx_start:ctx_end]
        
        # Clean up whitespace
        context = ' '.join(context.split())
        
        if ctx_start > 0:
            context = "..." + context
        if ctx_end < len(text):
            context = context + "..."
            
        return context
    
    # ==========================================================================
    # UTILITY METHODS FOR LLM INTEGRATION
    # ==========================================================================
    
    def prepare_for_llm(self, extraction: PDFExtraction) -> dict:
        """
        Prepare extracted data in a format suitable for LLM prompting.
        
        Returns a dict with:
        - document_text: Full text (possibly truncated for token limits)
        - numeric_candidates: Structured candidates with context
        """
        # Truncate text if too long (adjust based on your model's context window)
        max_chars = 15000
        doc_text = extraction.full_text
        if len(doc_text) > max_chars:
            doc_text = doc_text[:max_chars] + "\n\n[... document truncated ...]"
        
        candidates = extraction.numeric_candidates
        
        return {
            "document_text": doc_text,
            "candidates": {
                "loan_amounts": [
                    {"value": c.value, "page": c.page, "context": c.context}
                    for c in candidates.loan_amounts
                ],
                "interest_rates": [
                    {"value": c.value, "page": c.page, "context": c.context}
                    for c in candidates.interest_rates
                ],
                "term_months": [
                    {"value": int(c.value), "page": c.page, "context": c.context}
                    for c in candidates.term_months
                ],
                "monthly_payments": [
                    {"value": c.value, "page": c.page, "context": c.context}
                    for c in candidates.monthly_payments
                ],
                "fees": [
                    {"value": c.value, "page": c.page, "context": c.context}
                    for c in candidates.fees
                ]
            }
        }


# ==========================================================================
# STANDALONE CALCULATION UTILITIES
# ==========================================================================

def calculate_monthly_payment(principal: float, annual_rate: float, term_months: int) -> float:
    """
    Calculate fixed monthly payment using standard amortization formula.
    
    PMT = P * [r(1+r)^n] / [(1+r)^n - 1]
    
    Where:
    - P = principal (loan amount)
    - r = monthly interest rate (annual rate / 12 / 100)
    - n = number of payments (term in months)
    """
    if annual_rate == 0:
        return principal / term_months
    
    monthly_rate = annual_rate / 12 / 100
    n = term_months
    
    numerator = monthly_rate * ((1 + monthly_rate) ** n)
    denominator = ((1 + monthly_rate) ** n) - 1
    
    return principal * (numerator / denominator)


def calculate_total_interest(principal: float, monthly_payment: float, term_months: int) -> float:
    """Calculate total interest paid over the life of the loan."""
    total_paid = monthly_payment * term_months
    return total_paid - principal

