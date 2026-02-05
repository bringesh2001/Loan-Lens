"""
LLM-Based Document Analysis Service

This module handles:
1. Taking regex-extracted candidates and getting LLM to pick the correct values
2. Generating summary, highlights, and document type classification
3. Computing derived values (monthly payment, total interest)

Uses Google Gemini API for LLM analysis.
"""

import json
import os
from typing import Optional
from dotenv import load_dotenv

from services.pdf_extractor import (
    PDFExtraction, 
    calculate_monthly_payment, 
    calculate_total_interest
)

# Load environment variables from .env file
load_dotenv()


# Lazy-loaded Gemini model (only created when needed)
_model = None


def get_gemini_model():
    """Get Gemini model, creating it lazily. Returns None if no API key."""
    global _model
    
    if _model is not None:
        return _model
    
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
    
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    _model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        generation_config={
            "temperature": 0.2,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 8192,
            "response_mime_type": "application/json",
        }
    )
    return _model


async def call_gemini(system_prompt: str, user_prompt: str) -> dict:
    """
    Call Gemini API and return parsed JSON response.
    
    Args:
        system_prompt: Instructions for the model
        user_prompt: The actual query/task
        
    Returns:
        Parsed JSON response from Gemini
    """
    model = get_gemini_model()
    if model is None:
        raise RuntimeError("GEMINI_API_KEY environment variable not set")
    
    # Combine system and user prompts (Gemini handles this differently)
    full_prompt = f"""{system_prompt}

---

{user_prompt}"""
    
    # Gemini's generate_content is synchronous, wrap for async compatibility
    import asyncio
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None, 
        lambda: model.generate_content(full_prompt)
    )
    
    # Parse JSON response
    try:
        return json.loads(response.text)
    except json.JSONDecodeError:
        # Try to extract JSON from response if it has extra text
        text = response.text
        start = text.find('{')
        end = text.rfind('}') + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
        raise ValueError(f"Could not parse JSON from response: {text[:200]}")


# ==========================================================================
# PYDANTIC-STYLE RESPONSE SCHEMA FOR LLM
# ==========================================================================

SUMMARY_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "document_type": {
            "type": "string",
            "description": "Type of loan document (e.g., Personal Loan Agreement, Mortgage, Auto Loan)"
        },
        "overview": {
            "type": "string", 
            "description": "2-3 sentence plain English summary of the loan for a non-expert"
        },
        "key_numbers": {
            "type": "object",
            "properties": {
                "total_loan": {"type": "number", "description": "Principal loan amount"},
                "interest_rate": {"type": "number", "description": "Annual interest rate as percentage"},
                "term_months": {"type": "integer", "description": "Loan term in months"},
                "monthly_payment": {"type": ["number", "null"], "description": "Monthly payment if stated, otherwise null"},
                "fees": {"type": ["number", "null"], "description": "Total fees if found, otherwise null"}
            },
            "required": ["total_loan", "interest_rate", "term_months"]
        },
        "highlights": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["positive", "negative", "warning"]},
                    "text": {"type": "string", "description": "Short highlight statement"}
                },
                "required": ["type", "text"]
            },
            "description": "3-5 key highlights about the loan terms"
        },
        "confidence": {
            "type": "object",
            "properties": {
                "loan_amount": {"type": "string", "enum": ["high", "medium", "low"]},
                "interest_rate": {"type": "string", "enum": ["high", "medium", "low"]},
                "term": {"type": "string", "enum": ["high", "medium", "low"]}
            },
            "description": "Confidence levels for extracted values"
        }
    },
    "required": ["document_type", "overview", "key_numbers", "highlights", "confidence"]
}


# ==========================================================================
# PROMPT TEMPLATES
# ==========================================================================

SUMMARY_SYSTEM_PROMPT = """You are a financial document analyst specializing in loan agreements. 
Your task is to extract key numbers and generate a summary for non-expert borrowers.

IMPORTANT GUIDELINES:
1. Use the provided numeric candidates as reference - they were extracted via regex and may contain false positives
2. Verify values by checking the context around each candidate
3. If multiple candidates exist for the same field, pick the one that appears in the most authoritative context
4. If a value is not clearly stated, use null rather than guessing
5. Generate highlights that help a borrower understand the implications of this loan
6. Compare values against typical industry standards when assessing positive/negative/warning

For highlights:
- "positive": Fixed rates, no prepayment penalty, reasonable fees
- "negative": High interest rates (>10% for personal loans), large fees, strict terms
- "warning": Prepayment penalties, variable rates, balloon payments, arbitration clauses"""


def build_summary_prompt(llm_input: dict) -> str:
    """Build the user prompt for summary extraction."""
    
    candidates = llm_input["candidates"]
    
    # Format candidates section
    candidates_text = []
    
    if candidates["loan_amounts"]:
        candidates_text.append("LOAN AMOUNT CANDIDATES:")
        for c in candidates["loan_amounts"]:
            candidates_text.append(f"  - ${c['value']:,.2f} (page {c['page']})")
            candidates_text.append(f"    Context: \"{c['context']}\"")
    
    if candidates["interest_rates"]:
        candidates_text.append("\nINTEREST RATE CANDIDATES:")
        for c in candidates["interest_rates"]:
            candidates_text.append(f"  - {c['value']}% (page {c['page']})")
            candidates_text.append(f"    Context: \"{c['context']}\"")
    
    if candidates["term_months"]:
        candidates_text.append("\nLOAN TERM CANDIDATES:")
        for c in candidates["term_months"]:
            candidates_text.append(f"  - {c['value']} months (page {c['page']})")
            candidates_text.append(f"    Context: \"{c['context']}\"")
    
    if candidates["monthly_payments"]:
        candidates_text.append("\nMONTHLY PAYMENT CANDIDATES:")
        for c in candidates["monthly_payments"]:
            candidates_text.append(f"  - ${c['value']:,.2f} (page {c['page']})")
            candidates_text.append(f"    Context: \"{c['context']}\"")
    
    if candidates["fees"]:
        candidates_text.append("\nFEE CANDIDATES:")
        for c in candidates["fees"]:
            candidates_text.append(f"  - ${c['value']:,.2f} (page {c['page']})")
            candidates_text.append(f"    Context: \"{c['context']}\"")
    
    candidates_section = "\n".join(candidates_text) if candidates_text else "No numeric candidates found via regex - extract from document text directly."
    
    return f"""Analyze this loan document and extract the key numbers.

=== EXTRACTED NUMERIC CANDIDATES ===
{candidates_section}

=== FULL DOCUMENT TEXT ===
{llm_input["document_text"]}

=== TASK ===
1. Review the candidates and document text
2. Select the correct values for: loan amount, interest rate, term
3. Note monthly payment if explicitly stated (don't calculate yet)
4. Generate an overview and highlights for a borrower
5. Assess your confidence in each extracted value

Return your analysis as JSON matching the required schema."""


# ==========================================================================
# MAIN ANALYSIS FUNCTION
# ==========================================================================

async def analyze_for_summary(extraction: PDFExtraction, extractor) -> dict:
    """
    Use LLM to analyze extracted data and produce final summary.
    
    Args:
        extraction: PDFExtraction from pdf_extractor
        extractor: PDFExtractor instance (for prepare_for_llm method)
        
    Returns:
        Complete summary response matching API_DESIGN.md schema
        
    Raises:
        RuntimeError: If GEMINI_API_KEY is not set
    """
    # Prepare data for LLM
    llm_input = extractor.prepare_for_llm(extraction)
    
    # Build prompt with JSON schema instruction
    user_prompt = build_summary_prompt(llm_input) + f"""

Return your response as a JSON object with this exact structure:
{{
    "document_type": "string - type of loan",
    "overview": "string - 2-3 sentence summary",
    "key_numbers": {{
        "total_loan": number,
        "interest_rate": number,
        "term_months": integer,
        "monthly_payment": number or null,
        "fees": number or null
    }},
    "highlights": [
        {{"type": "positive|negative|warning", "text": "string"}}
    ],
    "confidence": {{
        "loan_amount": "high|medium|low",
        "interest_rate": "high|medium|low",
        "term": "high|medium|low"
    }}
}}"""
    
    # Call Gemini
    llm_result = await call_gemini(SUMMARY_SYSTEM_PROMPT, user_prompt)
    
    # Calculate derived values if not provided by document
    key_numbers = llm_result["key_numbers"]
    
    # Calculate monthly payment if not in document
    if key_numbers.get("monthly_payment") is None:
        key_numbers["monthly_payment"] = round(
            calculate_monthly_payment(
                key_numbers["total_loan"],
                key_numbers["interest_rate"],
                key_numbers["term_months"]
            ), 
            2
        )
    
    # Always calculate total interest
    key_numbers["total_interest"] = round(
        calculate_total_interest(
            key_numbers["total_loan"],
            key_numbers["monthly_payment"],
            key_numbers["term_months"]
        ),
        2
    )
    
    return {
        "document_type": llm_result["document_type"],
        "overview": llm_result["overview"],
        "key_numbers": key_numbers,
        "highlights": llm_result["highlights"],
        "_meta": {
            "confidence": llm_result["confidence"],
            "candidates_found": {
                "loan_amounts": len(llm_input["candidates"]["loan_amounts"]),
                "interest_rates": len(llm_input["candidates"]["interest_rates"]),
                "term_months": len(llm_input["candidates"]["term_months"]),
            }
        }
    }


# ==========================================================================
# FALLBACK: PURE REGEX-BASED SUMMARY (NO LLM)
# ==========================================================================

def generate_summary_from_regex_only(extraction: PDFExtraction) -> Optional[dict]:
    """
    Generate a basic summary using only regex-extracted values.
    Use this as a fallback if LLM is unavailable.
    
    Returns None if insufficient data found.
    """
    candidates = extraction.numeric_candidates
    
    # Need at least loan amount, rate, and term
    if not (candidates.loan_amounts and candidates.interest_rates and candidates.term_months):
        return None
    
    # Take first (highest confidence) candidate for each
    loan_amount = candidates.loan_amounts[0].value
    interest_rate = candidates.interest_rates[0].value
    term_months = int(candidates.term_months[0].value)
    
    monthly_payment = round(
        calculate_monthly_payment(loan_amount, interest_rate, term_months), 
        2
    )
    total_interest = round(
        calculate_total_interest(loan_amount, monthly_payment, term_months),
        2
    )
    
    # Generate basic highlights based on heuristics
    highlights = []
    
    if interest_rate > 10:
        highlights.append({"type": "negative", "text": "High Interest Rate"})
    elif interest_rate < 6:
        highlights.append({"type": "positive", "text": "Competitive Interest Rate"})
    
    if term_months >= 60:
        highlights.append({"type": "warning", "text": "Long Repayment Term"})
    
    # Check for fees
    if candidates.fees:
        total_fees = sum(f.value for f in candidates.fees)
        if total_fees > loan_amount * 0.03:  # Fees > 3% of loan
            highlights.append({"type": "negative", "text": "High Fees"})
    
    return {
        "document_type": "Loan Agreement",
        "overview": f"This is a loan for ${loan_amount:,.2f} at {interest_rate}% interest over {term_months} months.",
        "key_numbers": {
            "total_loan": loan_amount,
            "monthly_payment": monthly_payment,
            "interest_rate": interest_rate,
            "term_months": term_months,
            "total_interest": total_interest
        },
        "highlights": highlights or [{"type": "warning", "text": "Limited analysis - LLM unavailable"}],
        "_meta": {
            "source": "regex_only",
            "confidence": "low"
        }
    }


# ==========================================================================
# RED FLAGS ANALYSIS
# ==========================================================================

RED_FLAGS_SCHEMA = {
    "type": "object",
    "properties": {
        "red_flags": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "severity": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                        "description": "Severity based on financial impact to borrower"
                    },
                    "title": {
                        "type": "string",
                        "description": "Short, clear title for the red flag"
                    },
                    "description": {
                        "type": "string",
                        "description": "Explanation of why this is problematic for the borrower"
                    },
                    "location": {
                        "type": "object",
                        "properties": {
                            "page": {"type": "integer"},
                            "section": {"type": "string"}
                        },
                        "required": ["page", "section"]
                    },
                    "recommendation": {
                        "type": "string",
                        "description": "Specific, actionable advice for the borrower"
                    }
                },
                "required": ["severity", "title", "description", "location", "recommendation"]
            },
            "description": "List of red flags found in the document"
        }
    },
    "required": ["red_flags"]
}


RED_FLAGS_SYSTEM_PROMPT = """You are a consumer protection analyst specializing in loan agreements.
Your task is to identify RED FLAGS - terms that are unfavorable, unusual, or potentially harmful to the borrower.

WHAT TO LOOK FOR:
1. **High Fees**: Origination fees > 3%, late fees > $50, excessive processing charges
2. **Penalty Clauses**: Prepayment penalties, acceleration clauses, cross-default provisions
3. **Interest Issues**: Rates above market (>15% for personal loans), variable rates without caps, compound interest
4. **Hidden Costs**: Mandatory insurance, balloon payments, fee escalation clauses
5. **Legal Concerns**: Mandatory arbitration, waiver of rights, confession of judgment
6. **Unfair Terms**: Unilateral modification rights, automatic renewal, excessive collateral requirements

SEVERITY GUIDELINES:
- "high": Could cost borrower significant money or rights (prepayment penalties, arbitration clauses, very high rates)
- "medium": Above normal but not extreme (moderately high fees, long terms, variable rates)
- "low": Minor concerns worth noting (standard but notable clauses, slight deviations from best practices)

IMPORTANT:
- Be specific about WHY something is a red flag
- Compare against industry standards when possible
- Provide actionable recommendations
- Include page numbers and section references
- If no red flags found, return an empty array"""


async def analyze_for_red_flags(extraction: PDFExtraction, extractor) -> dict:
    """
    Use LLM to analyze document for red flags.
    
    Args:
        extraction: PDFExtraction from pdf_extractor
        extractor: PDFExtractor instance
        
    Returns:
        Dict with red flags list matching API_DESIGN.md schema
    """
    llm_input = extractor.prepare_for_llm(extraction)
    
    prompt = f"""Analyze this loan document for red flags - terms that are unfavorable or potentially harmful to the borrower.

=== DOCUMENT TEXT ===
{llm_input["document_text"]}

=== TASK ===
1. Carefully read the entire document
2. Identify any terms that are unfavorable to the borrower
3. Compare fees, rates, and terms against industry standards
4. For each red flag, provide:
   - Severity (high/medium/low)
   - Clear title
   - Why it's problematic
   - Specific page and section location
   - Actionable recommendation

Return your response as a JSON object with this exact structure:
{{
    "red_flags": [
        {{
            "severity": "high|medium|low",
            "title": "string",
            "description": "string - why this is problematic",
            "location": {{"page": integer, "section": "string"}},
            "recommendation": "string - actionable advice"
        }}
    ]
}}

If no red flags are found, return {{"red_flags": []}}"""

    result = await call_gemini(RED_FLAGS_SYSTEM_PROMPT, prompt)
    
    # Add IDs to each red flag
    red_flags = []
    for i, flag in enumerate(result["red_flags"], start=1):
        red_flags.append({
            "id": f"rf_{i:03d}",
            "severity": flag["severity"],
            "title": flag["title"],
            "description": flag["description"],
            "location": flag["location"],
            "recommendation": flag["recommendation"]
        })
    
    return {
        "count": len(red_flags),
        "data": red_flags
    }


def generate_red_flags_from_regex_only(extraction: PDFExtraction) -> dict:
    """
    Generate basic red flags using regex-extracted values.
    Fallback when LLM is unavailable.
    """
    candidates = extraction.numeric_candidates
    red_flags = []
    flag_id = 1
    
    # Check for high interest rates
    for rate in candidates.interest_rates:
        if rate.value > 15:
            red_flags.append({
                "id": f"rf_{flag_id:03d}",
                "severity": "high",
                "title": "Very High Interest Rate",
                "description": f"Interest rate of {rate.value}% is significantly above typical market rates.",
                "location": {"page": rate.page, "section": "Interest Rate Section"},
                "recommendation": "Shop around for better rates or negotiate with the lender."
            })
            flag_id += 1
        elif rate.value > 10:
            red_flags.append({
                "id": f"rf_{flag_id:03d}",
                "severity": "medium",
                "title": "Above Average Interest Rate",
                "description": f"Interest rate of {rate.value}% is higher than average market rates.",
                "location": {"page": rate.page, "section": "Interest Rate Section"},
                "recommendation": "Consider comparing with other lenders before signing."
            })
            flag_id += 1
    
    # Check for high fees
    for fee in candidates.fees:
        if candidates.loan_amounts:
            loan_amount = candidates.loan_amounts[0].value
            fee_percentage = (fee.value / loan_amount) * 100
            if fee_percentage > 5:
                red_flags.append({
                    "id": f"rf_{flag_id:03d}",
                    "severity": "high",
                    "title": "Excessive Fee",
                    "description": f"Fee of ${fee.value:,.2f} represents {fee_percentage:.1f}% of the loan amount.",
                    "location": {"page": fee.page, "section": "Fees Section"},
                    "recommendation": "Negotiate lower fees or look for lenders with more reasonable fee structures."
                })
                flag_id += 1
    
    # Add warning if no LLM analysis
    if not red_flags:
        red_flags.append({
            "id": "rf_001",
            "severity": "low",
            "title": "Limited Analysis Available",
            "description": "Full AI analysis unavailable. Manual review recommended.",
            "location": {"page": 1, "section": "General"},
            "recommendation": "Set GEMINI_API_KEY for comprehensive red flag detection."
        })
    
    return {
        "count": len(red_flags),
        "data": red_flags,
        "_meta": {"source": "regex_only"}
    }


# ==========================================================================
# HIDDEN CLAUSES ANALYSIS
# ==========================================================================

HIDDEN_CLAUSES_SCHEMA = {
    "type": "object",
    "properties": {
        "hidden_clauses": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Category: prepayment, arbitration, fees, liability, default, insurance, modification, etc."
                    },
                    "title": {
                        "type": "string",
                        "description": "Short, clear title for the clause"
                    },
                    "summary": {
                        "type": "string",
                        "description": "One-line summary of what this clause means"
                    },
                    "original_text": {
                        "type": "string",
                        "description": "Exact text extracted from the document (can be abbreviated with ...)"
                    },
                    "plain_english": {
                        "type": "string",
                        "description": "Translation to simple, plain English that anyone can understand"
                    },
                    "impact": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                        "description": "Impact level on the borrower"
                    },
                    "location": {
                        "type": "object",
                        "properties": {
                            "page": {"type": "integer"},
                            "section": {"type": "string"}
                        },
                        "required": ["page", "section"]
                    }
                },
                "required": ["category", "title", "summary", "original_text", "plain_english", "impact", "location"]
            },
            "description": "List of hidden or complex clauses found in the document"
        }
    },
    "required": ["hidden_clauses"]
}


HIDDEN_CLAUSES_SYSTEM_PROMPT = """You are a legal document analyst specializing in making loan agreements understandable to everyday people.
Your task is to find HIDDEN CLAUSES - legal language that is buried, complex, or easy to miss that could affect the borrower.

WHAT TO LOOK FOR:
1. **Prepayment Terms**: Early payoff penalties, yield maintenance clauses
2. **Default Provisions**: Cross-default, acceleration clauses, cure periods
3. **Arbitration Clauses**: Mandatory arbitration, class action waivers
4. **Fee Escalation**: Late fee compounding, rate increase triggers
5. **Insurance Requirements**: Forced-place insurance, life insurance requirements
6. **Collateral Provisions**: Cross-collateralization, after-acquired property
7. **Modification Rights**: Lender's right to change terms unilaterally
8. **Liability Waivers**: Borrower waiving certain legal rights

IMPORTANT GUIDELINES:
1. Extract the ACTUAL text from the document (abbreviate long passages with ...)
2. Translate complex legal language into simple, plain English
3. Explain the REAL-WORLD impact on the borrower
4. Focus on clauses that are easy to miss or hard to understand
5. Include specific page and section references

IMPACT LEVELS:
- "high": Could significantly affect borrower's finances or rights
- "medium": Important to understand but manageable
- "low": Good to know but minor impact

If no hidden clauses are found, return an empty array."""


async def analyze_for_hidden_clauses(extraction: PDFExtraction, extractor) -> dict:
    """
    Use LLM to find hidden or complex clauses in the document.
    
    Args:
        extraction: PDFExtraction from pdf_extractor
        extractor: PDFExtractor instance
        
    Returns:
        Dict with hidden clauses list matching API_DESIGN.md schema
    """
    llm_input = extractor.prepare_for_llm(extraction)
    
    prompt = f"""Analyze this loan document for hidden clauses - complex legal language that borrowers might miss or not understand.

=== DOCUMENT TEXT ===
{llm_input["document_text"]}

=== TASK ===
1. Carefully read the entire document
2. Identify clauses that are:
   - Written in complex legal language
   - Buried in dense paragraphs
   - Easy to overlook
   - Could have significant impact on the borrower
3. For each hidden clause, provide:
   - Category (prepayment, arbitration, fees, etc.)
   - Clear title
   - One-line summary
   - The original text from the document
   - Plain English translation
   - Impact level (high/medium/low)
   - Page and section location

Return your response as a JSON object with this exact structure:
{{
    "hidden_clauses": [
        {{
            "category": "string - prepayment, arbitration, fees, liability, default, insurance, modification, etc.",
            "title": "string",
            "summary": "string - one-line summary",
            "original_text": "string - exact text from document",
            "plain_english": "string - simple translation",
            "impact": "high|medium|low",
            "location": {{"page": integer, "section": "string"}}
        }}
    ]
}}

If no hidden clauses are found, return {{"hidden_clauses": []}}"""

    result = await call_gemini(HIDDEN_CLAUSES_SYSTEM_PROMPT, prompt)
    
    # Add IDs to each hidden clause
    hidden_clauses = []
    for i, clause in enumerate(result["hidden_clauses"], start=1):
        hidden_clauses.append({
            "id": f"hc_{i:03d}",
            "category": clause["category"],
            "title": clause["title"],
            "summary": clause["summary"],
            "original_text": clause["original_text"],
            "plain_english": clause["plain_english"],
            "impact": clause["impact"],
            "location": clause["location"]
        })
    
    return {
        "count": len(hidden_clauses),
        "data": hidden_clauses
    }


def generate_hidden_clauses_from_regex_only(extraction: PDFExtraction) -> dict:
    """
    Generate placeholder hidden clauses when LLM is unavailable.
    Limited capability - just returns a warning.
    """
    # Hidden clauses require LLM for proper detection
    # Regex alone cannot meaningfully identify complex legal language
    return {
        "count": 1,
        "data": [{
            "id": "hc_001",
            "category": "general",
            "title": "Full Analysis Unavailable",
            "summary": "AI-powered clause detection requires API key.",
            "original_text": "Document text available but not analyzed.",
            "plain_english": "To find hidden clauses in your loan document, please enable AI analysis by setting the GEMINI_API_KEY.",
            "impact": "low",
            "location": {"page": 1, "section": "General"}
        }],
        "_meta": {"source": "regex_only"}
    }


# ==========================================================================
# FINANCIAL TERMS ANALYSIS
# ==========================================================================

FINANCIAL_TERMS_SCHEMA = {
    "type": "object",
    "properties": {
        "terms": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Term name (e.g., APR, MCLR, EMI, Principal)"
                    },
                    "full_name": {
                        "type": "string",
                        "description": "Expanded name if abbreviated (e.g., Annual Percentage Rate)"
                    },
                    "short_description": {
                        "type": "string",
                        "description": "One-line summary of what this term means"
                    },
                    "definition": {
                        "type": "string",
                        "description": "Plain English explanation for a non-expert borrower"
                    },
                    "example": {
                        "type": "object",
                        "properties": {
                            "icon": {"type": "string", "enum": ["💡", "⚠️", "✅"]},
                            "title": {"type": "string"},
                            "text": {"type": "string", "description": "Example using actual values from this document"}
                        },
                        "required": ["icon", "title", "text"]
                    },
                    "your_value": {
                        "type": "string",
                        "description": "The actual value of this term in the document (e.g., '13.2%', '$500', '60 months')"
                    },
                    "location": {
                        "type": "object",
                        "properties": {
                            "page": {"type": "integer"},
                            "section": {"type": "string"}
                        },
                        "required": ["page", "section"]
                    }
                },
                "required": ["name", "full_name", "short_description", "definition", "example", "your_value", "location"]
            },
            "description": "List of financial terms found in the document"
        }
    },
    "required": ["terms"]
}


FINANCIAL_TERMS_SYSTEM_PROMPT = """You are a financial educator specializing in making loan documents understandable.
Your task is to identify FINANCIAL TERMS that borrowers might not understand and explain them in plain English.

WHAT TO LOOK FOR:
1. **Common Loan Terms**: APR, Principal, Interest Rate, EMI, MCLR, Tenure, Collateral
2. **Fees & Charges**: Processing Fee, Origination Fee, Late Fee, Prepayment Penalty
3. **Legal Terms**: Default, Acceleration, Arbitration, Foreclosure, Lien
4. **Payment Terms**: Amortization, Balloon Payment, Grace Period, Moratorium
5. **Rate Types**: Fixed Rate, Variable Rate, Floating Rate, Prime Rate

IMPORTANT GUIDELINES:
1. Only extract terms that actually appear in THIS document
2. For each term, provide:
   - The term name (as it appears in the document)
   - Full expanded name if abbreviated
   - A one-line short description
   - Plain English definition (explain like the borrower has no financial background)
   - A contextual example using ACTUAL values from this specific document
   - The actual value found in the document
   - Page and section location
3. Use appropriate icons:
   - 💡 for informational/neutral examples
   - ⚠️ for warnings or important cautions
   - ✅ for positive/beneficial examples
4. Make examples relatable and specific to this loan

If no financial terms are found, return an empty array."""


async def analyze_for_financial_terms(extraction: PDFExtraction, extractor) -> dict:
    """
    Use LLM to extract and explain financial terms from the document.
    
    Args:
        extraction: PDFExtraction from pdf_extractor
        extractor: PDFExtractor instance
        
    Returns:
        Dict with financial terms list matching API_DESIGN.md schema
    """
    llm_input = extractor.prepare_for_llm(extraction)
    
    prompt = f"""Analyze this loan document and extract all financial/legal terms that need explanation.

=== DOCUMENT TEXT ===
{llm_input["document_text"]}

=== TASK ===
1. Scan the document for financial terminology
2. Identify terms that borrowers might not understand
3. For each term found, provide:
   - Term name (as it appears)
   - Full expanded name if abbreviated
   - One-line summary
   - Plain English definition
   - Contextual example using actual values from THIS document
   - The actual value from the document
   - Page and section location

Return your response as a JSON object with this exact structure:
{{
    "terms": [
        {{
            "name": "string - term as it appears (e.g., APR)",
            "full_name": "string - expanded name (e.g., Annual Percentage Rate)",
            "short_description": "string - one-line summary",
            "definition": "string - plain English explanation",
            "example": {{
                "icon": "💡|⚠️|✅",
                "title": "string",
                "text": "string - example using actual values from this document"
            }},
            "your_value": "string - actual value from document (e.g., '13.2%', '$500')",
            "location": {{"page": integer, "section": "string"}}
        }}
    ]
}}

If no terms are found, return {{"terms": []}}"""

    result = await call_gemini(FINANCIAL_TERMS_SYSTEM_PROMPT, prompt)
    
    # Add IDs to each term
    terms = []
    for i, term in enumerate(result["terms"], start=1):
        terms.append({
            "id": f"term_{i:03d}",
            "name": term["name"],
            "full_name": term["full_name"],
            "short_description": term["short_description"],
            "definition": term["definition"],
            "example": term["example"],
            "your_value": term["your_value"],
            "location": term["location"]
        })
    
    return {
        "count": len(terms),
        "terms": terms
    }


def generate_financial_terms_from_regex_only(extraction: PDFExtraction) -> dict:
    """
    Generate basic financial terms when LLM is unavailable.
    Limited capability - just returns a warning.
    """
    # Financial terms require LLM for proper extraction and explanation
    return {
        "count": 1,
        "terms": [{
            "id": "term_001",
            "name": "API Key Required",
            "full_name": "AI Analysis Unavailable",
            "short_description": "Full term extraction requires AI analysis.",
            "definition": "To extract and explain financial terms from your loan document, please enable AI analysis by setting the GEMINI_API_KEY environment variable.",
            "example": {
                "icon": "⚠️",
                "title": "Limited Analysis",
                "text": "Set GEMINI_API_KEY to get detailed explanations of terms like APR, Principal, EMI, and more."
            },
            "your_value": "N/A",
            "location": {"page": 1, "section": "General"}
        }],
        "_meta": {"source": "regex_only"}
    }


# ==========================================================================
# CHAT WITH DOCUMENT
# ==========================================================================

CHAT_SYSTEM_PROMPT = """You are a helpful assistant that answers questions about loan documents.
Your role is to help borrowers understand their loan agreement by answering questions in plain, clear language.

IMPORTANT GUIDELINES:
1. Answer questions based ONLY on the document text provided
2. If information is not in the document, say so clearly
3. Use simple, non-technical language that anyone can understand
4. When referencing specific clauses, include page numbers and section names
5. Provide examples using actual values from the document when relevant
6. Be helpful and empathetic - borrowers may be confused or concerned
7. If asked about something that could be a problem (like penalties), explain it clearly
8. Reference related clauses by their IDs if they were previously identified (e.g., hc_001, rf_001)

TONE:
- Friendly and approachable
- Clear and direct
- Supportive (this is a financial decision, people may be stressed)
- Non-judgmental"""


async def chat_with_document(
    extraction: PDFExtraction,
    extractor,
    message: str,
    conversation_history: list[dict] = None,
    analysis_context: dict = None
) -> dict:
    """
    Answer questions about the loan document using conversational AI.
    
    Args:
        extraction: PDFExtraction from pdf_extractor
        extractor: PDFExtractor instance
        message: User's question
        conversation_history: Previous messages for context (optional)
        
    Returns:
        Dict with response and references
    """
    llm_input = extractor.prepare_for_llm(extraction)
    
    # Build conversation context
    context_parts = []
    
    # Add document text
    context_parts.append(f"=== LOAN DOCUMENT TEXT ===\n{llm_input['document_text']}")
    
    # Add existing analysis results if available
    if analysis_context:
        if "summary" in analysis_context and analysis_context["summary"]:
            summary = analysis_context["summary"]
            context_parts.append("\n=== DOCUMENT SUMMARY ===")
            context_parts.append(f"Type: {summary.get('document_type', 'Unknown')}")
            context_parts.append(f"Overview: {summary.get('overview', '')}")
            if "key_numbers" in summary:
                nums = summary["key_numbers"]
                context_parts.append(f"Loan Amount: ${nums.get('total_loan', 0):,.2f}")
                context_parts.append(f"Interest Rate: {nums.get('interest_rate', 0)}%")
                context_parts.append(f"Term: {nums.get('term_months', 0)} months")
        
        if "red_flags" in analysis_context and analysis_context["red_flags"]:
            flags = analysis_context["red_flags"].get("data", [])
            if flags:
                context_parts.append("\n=== RED FLAGS IDENTIFIED ===")
                for flag in flags[:5]:  # Top 5 red flags
                    context_parts.append(f"- [{flag.get('id', '')}] {flag.get('title', '')}: {flag.get('description', '')} (Page {flag.get('location', {}).get('page', '?')})")
        
        if "hidden_clauses" in analysis_context and analysis_context["hidden_clauses"]:
            clauses = analysis_context["hidden_clauses"].get("data", [])
            if clauses:
                context_parts.append("\n=== HIDDEN CLAUSES IDENTIFIED ===")
                for clause in clauses[:5]:  # Top 5 clauses
                    context_parts.append(f"- [{clause.get('id', '')}] {clause.get('title', '')}: {clause.get('plain_english', '')} (Page {clause.get('location', {}).get('page', '?')})")
    
    # Add conversation history if available
    if conversation_history:
        context_parts.append("\n=== PREVIOUS CONVERSATION ===")
        for msg in conversation_history[-5:]:  # Last 5 messages for context
            context_parts.append(f"User: {msg.get('message', '')}")
            context_parts.append(f"Assistant: {msg.get('response', '')}")
    
    context = "\n\n".join(context_parts)
    
    prompt = f"""{context}

=== CURRENT QUESTION ===
{message}

Please answer this question about the loan document. Be specific, cite page numbers and sections when referencing the document, and use plain English."""

    try:
        # For chat, we don't need structured JSON - just text response
        model = get_gemini_model()
        if model is None:
            raise RuntimeError("GEMINI_API_KEY environment variable not set")
        
        # Create a model without JSON response format for chat
        import google.generativeai as genai
        chat_model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            generation_config={
                "temperature": 0.7,  # Slightly higher for more natural conversation
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 2048,
            }
        )
        
        full_prompt = f"""{CHAT_SYSTEM_PROMPT}

---

{context}

=== CURRENT QUESTION ===
{message}

Please answer this question about the loan document. Be specific, cite page numbers and sections when referencing the document, and use plain English."""
        
        import asyncio
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: chat_model.generate_content(full_prompt)
        )
        
        response_text = response.text
        
        # Try to extract references from the response text
        # Look for patterns like "Section X.X" or "page Y"
        references = []
        # Simple extraction - could be improved with regex
        # For now, we'll return empty references and let the LLM mention them in text
        
        return {
            "response": response_text,
            "references": references
        }
    except Exception as e:
        # Fallback response
        return {
            "response": f"I apologize, but I'm having trouble processing your question right now. Please try rephrasing it or check that your GEMINI_API_KEY is set correctly. Error: {str(e)}",
            "references": []
        }

