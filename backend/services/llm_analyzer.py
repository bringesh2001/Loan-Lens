"""
LLM-Based Document Analysis Service

This module handles:
1. Taking regex-extracted candidates and getting LLM to pick the correct values
2. Generating summary, highlights, and document type classification
3. Computing derived values (monthly payment, total interest)

Uses Groq Cloud API (qwen/qwen3-32b) with JSON mode for structured output.
Pydantic models define the expected output schemas and are injected into prompts.
"""

import json
import os
import asyncio
from typing import List, Optional, Literal
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from services.pdf_extractor import (
    PDFExtraction, 
    calculate_monthly_payment, 
    calculate_total_interest
)

# Load environment variables from .env file
load_dotenv()


# ==========================================================================
# PYDANTIC MODELS FOR LLM STRUCTURED OUTPUT
# ==========================================================================
# These models define the expected JSON structure. Their JSON schemas are
# injected into prompts, and JSON mode guarantees valid JSON syntax.

# --- Shared ---
class LLMLocation(BaseModel):
    page: int
    section: str


# --- Summary Extraction ---
class SummaryKeyNumbers(BaseModel):
    total_loan: float = Field(description="Principal loan amount")
    interest_rate: float = Field(description="Annual interest rate as percentage")
    term_months: int = Field(description="Loan term in months")
    monthly_payment: Optional[float] = Field(None, description="Monthly payment if stated, otherwise null")
    fees: Optional[float] = Field(None, description="Total fees if found, otherwise null")


class SummaryHighlight(BaseModel):
    type: Literal["positive", "negative", "warning"]
    text: str = Field(description="Short highlight statement")


class SummaryConfidence(BaseModel):
    loan_amount: Literal["high", "medium", "low"]
    interest_rate: Literal["high", "medium", "low"]
    term: Literal["high", "medium", "low"]


class SummaryExtractionResponse(BaseModel):
    document_type: str = Field(description="Type of loan document (e.g., Personal Loan Agreement, Mortgage, Auto Loan)")
    overview: str = Field(description="2-3 sentence plain English summary of the loan for a non-expert")
    key_numbers: SummaryKeyNumbers
    highlights: List[SummaryHighlight] = Field(description="3-5 key highlights about the loan terms")
    confidence: SummaryConfidence


# --- Red Flags ---
class RedFlagItem(BaseModel):
    severity: Literal["high", "medium", "low"] = Field(description="Severity based on financial impact to borrower")
    title: str = Field(description="Short, clear title for the red flag")
    description: str = Field(description="Explanation of why this is problematic for the borrower")
    location: LLMLocation
    recommendation: str = Field(description="Specific, actionable advice for the borrower")


class RedFlagsLLMResponse(BaseModel):
    red_flags: List[RedFlagItem] = Field(description="List of red flags found in the document")


# --- Hidden Clauses ---
class HiddenClauseItem(BaseModel):
    category: str = Field(description="Category: prepayment, arbitration, fees, liability, default, insurance, modification, etc.")
    title: str = Field(description="Short, clear title for the clause")
    summary: str = Field(description="One-line summary of what this clause means")
    original_text: str = Field(description="Exact text extracted from the document (can be abbreviated with ...)")
    plain_english: str = Field(description="Translation to simple, plain English that anyone can understand")
    impact: Literal["high", "medium", "low"] = Field(description="Impact level on the borrower")
    location: LLMLocation


class HiddenClausesLLMResponse(BaseModel):
    hidden_clauses: List[HiddenClauseItem] = Field(description="List of hidden or complex clauses found in the document")


# --- Financial Terms ---
class TermExampleItem(BaseModel):
    icon: Literal["\U0001f4a1", "\u26a0\ufe0f", "\u2705"] = Field(description="Icon: lightbulb for info, warning for caution, checkmark for positive")
    title: str = Field(description="Short title for the example, max 5 words")
    text: str = Field(description="Example using actual values from this document, max 25 words")


class FinancialTermItem(BaseModel):
    name: str = Field(description="Term name as it appears in the document (e.g., APR, MCLR, EMI)")
    full_name: str = Field(description="Expanded name if abbreviated (e.g., Annual Percentage Rate)")
    short_description: str = Field(description="One-line summary, max 15 words")
    definition: str = Field(description="Plain English explanation for a non-expert borrower, max 30 words")
    example: TermExampleItem
    your_value: str = Field(description="The actual value of this term in the document (e.g., '13.2%', '$500', '60 months')")
    location: LLMLocation


class FinancialTermsLLMResponse(BaseModel):
    terms: List[FinancialTermItem] = Field(description="List of 5-8 most important financial terms found in the document")


# ==========================================================================
# GROQ API HELPERS
# ==========================================================================

def _get_groq_client():
    """Create and return an async Groq client with API key from environment."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY environment variable not set")
    from groq import AsyncGroq
    return AsyncGroq(api_key=api_key)


def _extract_json_from_response(text: str) -> str:
    """
    Extract clean JSON from LLM response.
    Handles cases where thinking models prefix output with <think>...</think> tags.
    """
    # Strip thinking tags if present (qwen3 may include them)
    if "<think>" in text:
        think_end = text.rfind("</think>")
        if think_end != -1:
            text = text[think_end + len("</think>"):].strip()
    
    # Strip markdown code fences if the model wraps JSON in ```json ... ```
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json) and last line (```)
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()
    
    return text


async def call_llm(
    system_prompt: str, 
    user_prompt: str, 
    response_schema=None
) -> dict:
    """
    Call Groq API (qwen/qwen3-32b) and return parsed JSON response.
    
    Uses JSON mode for guaranteed valid JSON. When a Pydantic response_schema
    is provided, its JSON schema is injected into the system prompt to guide
    the output structure.
    
    Args:
        system_prompt: Instructions for the model (system message)
        user_prompt: The actual query/task
        response_schema: Optional Pydantic model class — its JSON schema is 
                         injected into the prompt to guide output structure
        
    Returns:
        Parsed JSON response as dict
        
    Raises:
        RuntimeError: If API key not set or rate limit exceeded
        ValueError: If response cannot be parsed as JSON
    """
    # #region agent log
    open(r'c:\Users\bring\Desktop\loan_app\.cursor\debug.log','a').write(json.dumps({"hypothesisId":"H3","location":"llm_analyzer.py:call_llm:entry","message":"call_llm entered","data":{"prompt_len":len(user_prompt),"has_schema":response_schema is not None},"timestamp":__import__('time').time()})+'\n')
    # #endregion
    client = _get_groq_client()
    # #region agent log
    open(r'c:\Users\bring\Desktop\loan_app\.cursor\debug.log','a').write(json.dumps({"hypothesisId":"H3","location":"llm_analyzer.py:call_llm:after_client","message":"AsyncGroq client created successfully","data":{},"timestamp":__import__('time').time()})+'\n')
    # #endregion
    
    # If schema provided, inject its JSON schema into the system prompt
    effective_system_prompt = system_prompt
    if response_schema:
        schema_json = json.dumps(response_schema.model_json_schema(), indent=2)
        effective_system_prompt += (
            "\n\nYou MUST respond with valid JSON matching this exact schema:\n"
            f"{schema_json}\n"
            "Do NOT include any text outside the JSON object."
        )
    
    messages = [
        {"role": "system", "content": effective_system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    try:
        print(f"DEBUG: Calling Groq API (qwen/qwen3-32b) with prompt length: {len(user_prompt)} chars", flush=True)
        # #region agent log
        open(r'c:\Users\bring\Desktop\loan_app\.cursor\debug.log','a').write(json.dumps({"hypothesisId":"H4","location":"llm_analyzer.py:call_llm:before_api_call","message":"About to call Groq API","data":{"model":"qwen/qwen3-32b","msg_count":len(messages),"sys_prompt_len":len(effective_system_prompt)},"timestamp":__import__('time').time()})+'\n')
        # #endregion
        
        # Native async call — no run_in_executor needed with AsyncGroq
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model="qwen/qwen3-32b",
                messages=messages,
                temperature=0.1,
                max_completion_tokens=8192,
                top_p=0.95,
                # NOTE: response_format=json_object is NOT used here because
                # Qwen3 is a "thinking" model that may emit <think> tags before
                # the JSON, which breaks json_object enforcement. We handle
                # JSON extraction manually via _extract_json_from_response.
                stream=False,
            ),
            timeout=120.0
        )
        
        print(f"DEBUG: Groq API call completed successfully", flush=True)
    except asyncio.TimeoutError:
        print("ERROR: Groq API call timed out after 120 seconds", flush=True)
        raise RuntimeError(
            "Groq API call timed out after 120 seconds. "
            "The document may be too large or the API is slow. "
            "Try again or use a smaller document."
        )
    except Exception as e:
        error_str = str(e)
        print(f"ERROR: Groq API call failed: {error_str[:500]}", flush=True)
        # Check for rate limit errors
        if "rate_limit" in error_str.lower() or "429" in error_str:
            raise RuntimeError(
                "Groq API rate limit exceeded. "
                "Please wait and try again. Error: " + error_str[:200]
            )
        raise
    
    # Extract the response text
    text = response.choices[0].message.content.strip()
    
    # Clean up any thinking tags or code fences
    text = _extract_json_from_response(text)
    
    print(f"DEBUG: Groq response length: {len(text)} chars", flush=True)
    if len(text) < 2000:
        print(f"DEBUG: Full response: {text}", flush=True)
    else:
        print(f"DEBUG: Response preview (first 500): {text[:500]}", flush=True)
    
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"ERROR: JSON parse failed: {e}", flush=True)
        print(f"DEBUG: Response text: {text[:1000]}", flush=True)
        raise ValueError(f"Could not parse JSON from response. Error: {e}")


# ==========================================================================
# PROMPT TEMPLATES
# ==========================================================================

SUMMARY_SYSTEM_PROMPT = """You are a financial document analyst specializing in loan agreements. 
Your task is to extract key numbers and generate a summary for non-expert borrowers.

IMPORTANT GUIDELINES:
1. Use the provided numeric candidates as reference - they were extracted via regex and may contain false positives
2. If NO candidates are provided (all lists are empty), you MUST extract values directly from the document text
3. Search the entire document text for loan amount, interest rate, and loan term - they may be in tables, different sections, or use different terminology
4. Verify values by checking the context around each candidate or finding
5. If multiple candidates exist for the same field, pick the one that appears in the most authoritative context
6. Look for variations like: "Loan Amount/Limit", "Rate Interest", "EMI period", "tenure", "disbursement amount"
7. For interest rates, look for patterns like "X% p.a.", "X% per annum", "X% compounded monthly"
8. If a value is not clearly stated, use null rather than guessing
9. Generate highlights that help a borrower understand the implications of this loan
10. Compare values against typical industry standards when assessing positive/negative/warning

CRITICAL: Even if regex found nothing, you MUST extract the required fields (total_loan, interest_rate, term_months) from the document text. Do not return null for all three required fields unless the document truly contains no loan information.

For highlights:
- "positive": Fixed rates, no prepayment penalty, reasonable fees
- "negative": High interest rates (>10% for personal loans), large fees, strict terms
- "warning": Prepayment penalties, variable rates, balloon payments, arbitration clauses"""


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


FINANCIAL_TERMS_SYSTEM_PROMPT = """You are a financial educator specializing in making loan documents understandable.
Your task is to identify FINANCIAL TERMS that borrowers might not understand and explain them in plain English.

WHAT TO LOOK FOR:
1. **Common Loan Terms**: APR, Principal, Interest Rate, EMI, MCLR, Tenure, Collateral
2. **Fees & Charges**: Processing Fee, Origination Fee, Late Fee, Prepayment Penalty
3. **Legal Terms**: Default, Acceleration, Arbitration, Foreclosure, Lien
4. **Payment Terms**: Amortization, Balloon Payment, Grace Period, Moratorium
5. **Rate Types**: Fixed Rate, Variable Rate, Floating Rate, Prime Rate

IMPORTANT GUIDELINES:
1. Only extract THE MOST IMPORTANT 5-8 terms that actually appear in THIS document
2. Prioritize terms that are most confusing or impactful to borrowers
3. Keep short_description under 15 words
4. Keep definition under 30 words - be concise!
5. Keep example text under 25 words
6. Use appropriate icons: lightbulb for informational, warning for cautions, checkmark for positive

If no financial terms are found, return an empty array."""


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


# ==========================================================================
# PROMPT BUILDERS
# ==========================================================================

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
    
    candidates_section = "\n".join(candidates_text) if candidates_text else "No numeric candidates found via regex - YOU MUST extract values directly from the document text below."
    
    # Add emphasis if no candidates found
    extraction_instruction = ""
    if not candidates_text:
        extraction_instruction = """
IMPORTANT: No regex candidates were found. You MUST extract the required values (total_loan, interest_rate, term_months) directly from the document text.
Look carefully through the entire document text for:
- Loan amount (may be labeled as "Loan Amount", "Loan Amount/Limit", "Principal", "Sanctioned Amount", etc.)
- Interest rate (may be labeled as "Rate of Interest", "Interest Rate", "Rate Interest", "% p.a.", etc.)
- Loan term (may be labeled as "Term", "Tenure", "EMI Period", "Repayment Period", "Duration", etc.)
Even if the format is unusual or in a table, extract the values."""
    
    return f"""Analyze this loan document and extract the key numbers.

=== EXTRACTED NUMERIC CANDIDATES ===
{candidates_section}
{extraction_instruction}

=== FULL DOCUMENT TEXT ===
{llm_input["document_text"]}

=== TASK ===
1. Carefully read the ENTIRE document text above
2. Extract the required values: loan amount, interest rate, and loan term
3. Look for these values even if they're in tables, different sections, or use alternative terminology
4. If you find the values, return them as numbers (not null)
5. Note monthly payment if explicitly stated (don't calculate yet)
6. Generate an overview and highlights for a borrower
7. Assess your confidence in each extracted value

You must extract at least loan amount, interest rate, and term_months from the document. Do not return null for all three unless the document truly contains no loan information."""


# ==========================================================================
# MAIN ANALYSIS FUNCTIONS
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
        RuntimeError: If GROQ_API_KEY is not set
    """
    # Prepare data for LLM
    llm_input = extractor.prepare_for_llm(extraction)
    
    # Build prompt (no JSON formatting instructions needed - schema handles it)
    user_prompt = build_summary_prompt(llm_input)
    
    # Call LLM with structured output schema
    llm_result = await call_llm(
        SUMMARY_SYSTEM_PROMPT, 
        user_prompt, 
        response_schema=SummaryExtractionResponse
    )
    
    # Calculate derived values if not provided by document
    key_numbers = llm_result.get("key_numbers", {})
    
    # Validate required fields are not None
    total_loan = key_numbers.get("total_loan")
    interest_rate = key_numbers.get("interest_rate")
    term_months = key_numbers.get("term_months")
    
    if total_loan is None or interest_rate is None or term_months is None:
        # Log what candidates were available to help debug
        candidates_info = {
            "loan_amounts": len(llm_input["candidates"]["loan_amounts"]),
            "interest_rates": len(llm_input["candidates"]["interest_rates"]),
            "term_months": len(llm_input["candidates"]["term_months"]),
        }
        print(f"LLM extraction failed. Available candidates: {candidates_info}", flush=True)
        print(f"LLM returned key_numbers: {key_numbers}", flush=True)
        print(f"Full LLM response keys: {list(llm_result.keys())}", flush=True)
        
        # LLM didn't extract required fields, raise error to trigger fallback
        raise ValueError(
            f"LLM failed to extract required fields: "
            f"total_loan={total_loan}, interest_rate={interest_rate}, term_months={term_months}. "
            f"Candidates available: {candidates_info}"
        )
    
    # Ensure term_months is an integer
    term_months = int(term_months)
    
    # Calculate monthly payment if not in document
    if key_numbers.get("monthly_payment") is None:
        key_numbers["monthly_payment"] = round(
            calculate_monthly_payment(
                total_loan,
                interest_rate,
                term_months
            ), 
            2
        )
    
    # Always calculate total interest
    key_numbers["total_interest"] = round(
        calculate_total_interest(
            total_loan,
            key_numbers["monthly_payment"],
            term_months
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
    
    # Simplified prompt - no JSON formatting rules needed, schema handles it
    prompt = f"""Analyze this loan document for red flags - terms that are unfavorable or potentially harmful to the borrower.

=== DOCUMENT TEXT ===
{llm_input["document_text"]}

=== TASK ===
1. Carefully read the entire document
2. Identify any terms that are unfavorable to the borrower
3. Compare fees, rates, and terms against industry standards
4. For each red flag, provide severity, a clear title, why it's problematic, the page and section location, and actionable recommendation

If no red flags are found, return an empty list."""

    result = await call_llm(
        RED_FLAGS_SYSTEM_PROMPT, 
        prompt, 
        response_schema=RedFlagsLLMResponse
    )
    
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
    
    # Simplified prompt - no JSON formatting rules needed, schema handles it
    prompt = f"""Analyze this loan document for hidden clauses - complex legal language that borrowers might miss or not understand.

=== DOCUMENT TEXT ===
{llm_input["document_text"]}

=== TASK ===
1. Carefully read the entire document
2. Identify clauses that are written in complex legal language, buried in dense paragraphs, easy to overlook, or could have significant impact on the borrower
3. For each hidden clause, provide the category, a clear title, one-line summary, the original text from the document (abbreviate with ... if long), a plain English translation, impact level, and page/section location

If no hidden clauses are found, return an empty list."""

    result = await call_llm(
        HIDDEN_CLAUSES_SYSTEM_PROMPT, 
        prompt, 
        response_schema=HiddenClausesLLMResponse
    )
    
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
    
    # Simplified prompt - no JSON formatting rules needed, schema handles it
    prompt = f"""Analyze this loan document and extract the 5-8 MOST IMPORTANT financial/legal terms that need explanation.

=== DOCUMENT TEXT ===
{llm_input["document_text"]}

=== TASK ===
1. Scan the document for financial terminology
2. Identify the 5-8 MOST IMPORTANT terms that borrowers might not understand
3. For each term, provide the term name as it appears, full expanded name, a concise one-line summary, plain English definition, a contextual example using actual values from THIS document, the actual value from the document, and page/section location
4. Limit to 5-8 most important terms only. Keep all text fields brief."""

    result = await call_llm(
        FINANCIAL_TERMS_SYSTEM_PROMPT, 
        prompt, 
        response_schema=FinancialTermsLLMResponse
    )
    
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
        # Provide diagnostic information about what was found
        found = []
        if candidates.loan_amounts:
            found.append(f"{len(candidates.loan_amounts)} loan amount(s)")
        if candidates.interest_rates:
            found.append(f"{len(candidates.interest_rates)} interest rate(s)")
        if candidates.term_months:
            found.append(f"{len(candidates.term_months)} term(s)")
        if candidates.monthly_payments:
            found.append(f"{len(candidates.monthly_payments)} monthly payment(s)")
        if candidates.fees:
            found.append(f"{len(candidates.fees)} fee(s)")
        
        missing = []
        if not candidates.loan_amounts:
            missing.append("loan amount")
        if not candidates.interest_rates:
            missing.append("interest rate")
        if not candidates.term_months:
            missing.append("loan term")
        
        print(f"Regex extraction insufficient: Found {', '.join(found) if found else 'nothing'}. Missing: {', '.join(missing)}", flush=True)
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
            "recommendation": "Set GROQ_API_KEY for comprehensive red flag detection."
        })
    
    return {
        "count": len(red_flags),
        "data": red_flags,
        "_meta": {"source": "regex_only"}
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
            "plain_english": "To find hidden clauses in your loan document, please enable AI analysis by setting the GROQ_API_KEY.",
            "impact": "low",
            "location": {"page": 1, "section": "General"}
        }],
        "_meta": {"source": "regex_only"}
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
            "definition": "To extract and explain financial terms from your loan document, please enable AI analysis by setting the GROQ_API_KEY environment variable.",
            "example": {
                "icon": "\u26a0\ufe0f",
                "title": "Limited Analysis",
                "text": "Set GROQ_API_KEY to get detailed explanations of terms like APR, Principal, EMI, and more."
            },
            "your_value": "N/A",
            "location": {"page": 1, "section": "General"}
        }],
        "_meta": {"source": "regex_only"}
    }


# ==========================================================================
# CHAT WITH DOCUMENT
# ==========================================================================

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
        analysis_context: Previously computed analysis (summary, red flags, etc.)
        
    Returns:
        Dict with response and references
    """
    client = _get_groq_client()
    
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
    
    full_prompt = f"""{context}

=== CURRENT QUESTION ===
{message}

Please answer this question about the loan document. Be specific, cite page numbers and sections when referencing the document, and use plain English."""

    try:
        # For chat, we use plain text output (no structured JSON)
        messages = [
            {"role": "system", "content": CHAT_SYSTEM_PROMPT},
            {"role": "user", "content": full_prompt}
        ]
        
        # Native async call with AsyncGroq
        response = await client.chat.completions.create(
            model="qwen/qwen3-32b",
            messages=messages,
            temperature=0.7,  # Slightly higher for more natural conversation
            max_completion_tokens=2048,
            top_p=0.95,
            stream=False,
        )
        
        response_text = response.choices[0].message.content
        
        # Strip thinking tags if present
        if "<think>" in response_text:
            think_end = response_text.rfind("</think>")
            if think_end != -1:
                response_text = response_text[think_end + len("</think>"):].strip()
        
        return {
            "response": response_text,
            "references": []
        }
    except Exception as e:
        # Fallback response
        return {
            "response": f"I apologize, but I'm having trouble processing your question right now. Please try rephrasing it or check that your GROQ_API_KEY is set correctly. Error: {str(e)}",
            "references": []
        }
