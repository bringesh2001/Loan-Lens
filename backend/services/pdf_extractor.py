"""
PDF Text Extraction and Number Parsing Service

This module handles:
1. Extracting raw text from PDF documents using LlamaParse
2. Rule-based regex parsing to find initial numeric candidates (loan amount, interest rate, term, fees)
3. Preparing structured data for LLM (Gemini) disambiguation and final parsing
"""

import re
import os
import asyncio
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional
from io import BytesIO

import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


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
    1. LlamaParse for text extraction from PDFs
    2. Rule-based regex parsing to find initial numeric candidates
    3. Results passed to LLM (Gemini) for intelligent disambiguation and final parsing
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
    # Expanded to handle more document formats and terminology
    LOAN_KEYWORDS = [
        r'loan\s*amount', r'principal', r'amount\s*financed', 
        r'total\s*loan', r'borrowing', r'credit\s*amount',
        r'loan\s*sanctioned', r'sanctioned\s*amount', r'loan\s*sanction',
        r'disbursement\s*amount', r'loan\s*value', r'amount\s*of\s*loan',
        r'loan\s*sum', r'principal\s*amount', r'loan\s*principal',
        r'loan\s*amount/limit', r'loan\s*limit', r'limit', r'amount/limit',
        r'loan\s*amount\s*limit', r'sanction\s*amount', r'loan\s*sum\s*sanctioned'
    ]
    
    INTEREST_KEYWORDS = [
        r'interest\s*rate', r'annual\s*percentage\s*rate', r'apr',
        r'rate\s*of\s*interest', r'fixed\s*rate', r'variable\s*rate',
        r'interest', r'roi', r'annual\s*rate', r'yearly\s*rate',
        r'rate\s*%', r'interest\s*%', r'rate\s*interest',
        r'%?\s*p\.a\.', r'per\s*annum', r'p\.a\.', r'pa\s*compounded'
    ]
    
    PAYMENT_KEYWORDS = [
        r'monthly\s*payment', r'payment\s*amount', r'installment',
        r'periodic\s*payment', r'emi', r'monthly\s*installment',
        r'equated\s*monthly', r'emi\s*amount', r'monthly\s*emi',
        r'payment\s*per\s*month', r'monthly\s*repayment'
    ]
    
    TERM_KEYWORDS = [
        r'loan\s*term', r'repayment\s*period', r'tenor', r'duration',
        r'maturity', r'term\s*of\s*loan', r'emi\s*period',
        r'repayment\s*term', r'loan\s*duration', r'tenure',
        r'term\s*months', r'period\s*months', r'number\s*of\s*months',
        r'number\s*of\s*payments', r'payment\s*term'
    ]
    
    FEE_KEYWORDS = [
        r'processing\s*fee', r'origination\s*fee', r'late\s*fee',
        r'prepayment\s*penalty', r'service\s*charge', r'closing\s*cost',
        r'processing\s*charges', r'upfront\s*charge', r'processing\s*charge',
        r'fee', r'charges', r'cost'
    ]
    
    def __init__(self):
        # Compile regex patterns for efficiency (used as fallback)
        self._compile_patterns()
        # Store last result for structured data access
        self._last_result: Optional[dict] = None
    
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
            r'(?:' + '|'.join(self.TERM_KEYWORDS) + r').{0,150}?' + self.TERM_PATTERN,
            re.IGNORECASE | re.DOTALL
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
        """Build a regex that matches: keyword ... value (within ~150 chars, including newlines)."""
        keyword_group = '|'.join(keywords)
        # Match keyword, then up to 150 chars (including newlines — re.DOTALL makes . match \n),
        # then the value. Using .{0,150}? instead of (?:[^\n]|\n[^\n]*){0,150}? to avoid
        # catastrophic backtracking from nested quantifiers.
        pattern = rf'(?:{keyword_group}).{{0,150}}?{value_pattern}'
        return re.compile(pattern, re.IGNORECASE | re.DOTALL)
    
    # ==========================================================================
    # PDF TEXT EXTRACTION USING LLAMAPARSE
    # ==========================================================================
    
    async def extract_text(self, pdf_bytes: bytes) -> tuple[str, dict[int, str]]:
        """
        Extract text from PDF using LlamaParse, returning full text and per-page breakdown.
        Also stores result for structured data extraction.
        
        Args:
            pdf_bytes: Raw PDF file content
            
        Returns:
            Tuple of (full_text, {page_num: page_text})
            
        Raises:
            RuntimeError: If LLAMA_CLOUD_API_KEY is not set or parsing fails
        """
        api_key = os.environ.get("LLAMA_CLOUD_API_KEY")
        if not api_key:
            raise RuntimeError("LLAMA_CLOUD_API_KEY environment variable not set")
        
        # Upload and parse using LlamaParse API v2 with structured extraction
        job_id = await self._upload_and_parse(pdf_bytes, api_key)
        
        # Poll for job completion
        try:
            result = await self._wait_for_completion(job_id, api_key)
            print(f"DEBUG: Got result from _wait_for_completion, keys: {list(result.keys()) if result else 'None'}")
            # Store result for structured data access
            self._last_result = result
        except RuntimeError as e:
            # If job completed but no content, try to get at least the status
            print(f"DEBUG: RuntimeError from _wait_for_completion: {e}")
            self._last_result = {}
            # Return empty result so we can see what happened
            return "", {1: ""}
        
        # Extract text from result
        print(f"DEBUG: About to call _extract_text_from_result with result type: {type(result)}")
        full_text, text_by_page = self._extract_text_from_result(result)
        print(f"DEBUG: After _extract_text_from_result, full_text length: {len(full_text)}, pages: {len(text_by_page)}")
        
        return full_text, text_by_page
    
    async def _upload_and_parse(self, pdf_bytes: bytes, api_key: str) -> str:
        """Upload PDF and start parsing job. Returns job_id."""
        url = "https://api.cloud.llamaindex.ai/api/v2/parse/upload"
        
        configuration = {
            "tier": "cost_effective",
            "version": "latest",
            "processing_options": {
                "ocr_parameters": {
                    "languages": ["en"]  # Add more languages if needed
                }
            },
            "output_options": {
                "markdown": {
                    "tables": {
                        "output_tables_as_markdown": True
                    }
                }
            },
            "processing_control": {
                "timeouts": {
                    "base_in_seconds": 300,
                    "extra_time_per_page_in_seconds": 30
                }
            }
        }
        
        import json
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            # Multipart form data: file and configuration as JSON string
            files = {"file": ("document.pdf", pdf_bytes, "application/pdf")}
            data = {"configuration": json.dumps(configuration)}
            headers = {"Authorization": f"Bearer {api_key}"}
            
            try:
                response = await client.post(url, files=files, data=data, headers=headers)
                response.raise_for_status()
                
                result = response.json()
                job_id = result.get("id") or result.get("job_id")
                if not job_id:
                    raise RuntimeError(f"Unexpected response format. Expected 'id' or 'job_id' field. Got: {result}")
                print(f"LlamaParse job created: {job_id}")
                return job_id
            except httpx.HTTPStatusError as e:
                error_detail = e.response.text
                raise RuntimeError(f"LlamaParse upload failed: {e.response.status_code} - {error_detail}")
            except Exception as e:
                raise RuntimeError(f"Failed to upload to LlamaParse: {str(e)}")
    
    async def _wait_for_completion(self, job_id: str, api_key: str, max_wait: int = 600) -> dict:
        """
        Poll for job completion. Returns parsed result.
        
        Args:
            job_id: LlamaParse job ID
            api_key: API key for authentication
            max_wait: Maximum time to wait in seconds (default 10 minutes)
        """
        # Use expand parameter to get full result content
        url = f"https://api.cloud.llamaindex.ai/api/v2/parse/{job_id}?expand=markdown,text,items"
        headers = {"Authorization": f"Bearer {api_key}"}
        
        start_time = time.time()
        poll_interval = 3  # Start with 3 second intervals
        last_status = None
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            while time.time() - start_time < max_wait:
                try:
                    response = await client.get(url, headers=headers)
                    response.raise_for_status()
                    
                    result = response.json()
                    
                    # LlamaParse v2 API returns status nested in 'job' object
                    job_info = result.get("job", {})
                    status = job_info.get("status", "").upper() if job_info.get("status") else None
                    
                    # Fallback to top-level status if job object doesn't have it
                    if not status:
                        status = (result.get("status") or result.get("job_status") or result.get("state") or "").upper()
                    
                    # Log status changes
                    if status != last_status:
                        print(f"LlamaParse job {job_id} status: {status}")
                        last_status = status
                    
                    if status in ["SUCCESS", "COMPLETED", "DONE"]:
                        print(f"LlamaParse job {job_id} completed successfully")
                        # Check if content is already in the response
                        has_markdown = bool(result.get("markdown"))
                        has_text = bool(result.get("text"))
                        has_items = bool(result.get("items"))
                        print(f"DEBUG: Content check - markdown={has_markdown}, text={has_text}, items={has_items}")
                        if has_markdown or has_text or result.get("markdown_full") or result.get("text_full") or has_items:
                            print(f"DEBUG: Returning result with content. Keys: {list(result.keys())}")
                            return result
                        
                        # Log the response structure for debugging
                        print(f"Response keys: {list(result.keys())}")
                        if "result_content_metadata" in result:
                            print(f"result_content_metadata: {result.get('result_content_metadata')}")
                        
                        # Content not in status response, try fetching with expand parameter
                        print("Content not in status response, attempting to fetch with expand parameter...")
                        content_result = await self._fetch_result_content(job_id, api_key)
                        if content_result and (content_result.get("markdown") or content_result.get("text") or content_result.get("items")):
                            return content_result
                        
                        # If still no content, wait a moment and try the status endpoint again with expand
                        print("Waiting for content to become available...")
                        await asyncio.sleep(2)
                        expand_url = f"https://api.cloud.llamaindex.ai/api/v2/parse/{job_id}?expand=markdown,text,items"
                        response = await client.get(expand_url, headers=headers)
                        response.raise_for_status()
                        final_result = response.json()
                        if final_result.get("markdown") or final_result.get("text") or final_result.get("markdown_full") or final_result.get("text_full") or final_result.get("items"):
                            return final_result
                        
                        # Last resort: raise error with helpful message
                        raise RuntimeError(
                            f"LlamaParse job {job_id} completed but content is not available. "
                            f"This may indicate an issue with the LlamaParse API or the document. "
                            f"Please check the job status at https://cloud.llamaindex.ai/ "
                            f"or try uploading the document again."
                        )
                    elif status in ["FAILED", "ERROR"]:
                        error = job_info.get("error_message") or result.get("error") or result.get("message") or "Unknown error"
                        raise RuntimeError(f"LlamaParse job failed: {error}")
                    elif status in ["PENDING", "PROCESSING", "IN_PROGRESS", "QUEUED", "RUNNING"]:
                        # Job is still processing, continue polling
                        elapsed = time.time() - start_time
                        if elapsed % 30 < poll_interval:  # Log every ~30 seconds
                            print(f"LlamaParse job {job_id} still processing... ({elapsed:.0f}s elapsed)")
                    else:
                        # Unknown status, log it
                        print(f"LlamaParse job {job_id} has unknown status: {status}")
                        print(f"Job info: {job_info}")
                    
                    # Adaptive polling: increase interval for long-running jobs
                    elapsed = time.time() - start_time
                    if elapsed > 60:
                        poll_interval = 5  # Poll every 5 seconds after 1 minute
                    if elapsed > 300:
                        poll_interval = 10  # Poll every 10 seconds after 5 minutes
                    
                    await asyncio.sleep(poll_interval)
                    
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 404:
                        raise RuntimeError(f"LlamaParse job {job_id} not found. It may have expired.")
                    raise RuntimeError(f"Error checking LlamaParse job status: {e.response.status_code} - {e.response.text}")
                except RuntimeError as e:
                    # Re-raise RuntimeError (these are our custom errors for completed jobs without content)
                    raise
                except Exception as e:
                    print(f"Error polling LlamaParse job: {e}")
                    await asyncio.sleep(poll_interval)
            
            # Timeout reached
            elapsed = time.time() - start_time
            raise RuntimeError(
                f"LlamaParse job timed out after {elapsed:.0f} seconds. "
                f"Job ID: {job_id}. You can check status manually at: "
                f"https://cloud.llamaindex.ai/"
            )
    
    async def _fetch_result_content(self, job_id: str, api_key: str) -> Optional[dict]:
        """
        Fetch the actual parsed content from a completed LlamaParse job.
        According to LlamaParse v2 API docs, we may need to use a different endpoint
        or query parameter to get the actual content.
        """
        headers = {"Authorization": f"Bearer {api_key}"}
        
        # Try different approaches to get content
        # Use expand parameter to request specific fields
        endpoints_to_try = [
            f"https://api.cloud.llamaindex.ai/api/v2/parse/{job_id}?expand=markdown,text,items",
            f"https://api.cloud.llamaindex.ai/api/v2/parse/{job_id}?expand=markdown",
            f"https://api.cloud.llamaindex.ai/api/v2/parse/{job_id}?expand=text",
            f"https://api.cloud.llamaindex.ai/api/v2/parse/{job_id}",
        ]
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            for endpoint in endpoints_to_try:
                try:
                    response = await client.get(endpoint, headers=headers)
                    response.raise_for_status()
                    
                    result = response.json()
                    
                    # Check if content is available in various possible locations
                    content = None
                    
                    # Check for structured extraction data first
                    extraction_data = result.get("extraction") or result.get("extracted_data") or result.get("data")
                    if extraction_data:
                        print(f"DEBUG: Found extraction data in result: {extraction_data}")
                    
                    # Check top-level fields
                    if result.get("markdown") or result.get("text"):
                        content = result.get("markdown") or result.get("text")
                    elif result.get("markdown_full") or result.get("text_full"):
                        content = result.get("markdown_full") or result.get("text_full")
                    # Check items array (structured content)
                    elif result.get("items"):
                        items = result.get("items", [])
                        # Extract text from items
                        content_parts = []
                        for item in items:
                            if item.get("type") == "text":
                                content_parts.append(item.get("text", ""))
                            elif item.get("markdown"):
                                content_parts.append(item.get("markdown"))
                        if content_parts:
                            content = "\n\n".join(content_parts)
                    
                    if content:
                        print(f"Successfully fetched content from {endpoint}")
                        # Return result with content in markdown field for consistency
                        result["markdown"] = content
                        return result
                    
                except Exception as e:
                    print(f"Error fetching from {endpoint}: {e}")
                    continue
        
        # If all endpoints fail, check if result_content_metadata has a URL to fetch
        # Sometimes LlamaParse stores content separately and provides a URL
        print("Warning: Could not fetch content from any endpoint")
        print("Note: LlamaParse job completed but content may be stored separately or not yet available")
        return None
    
    def _extract_text_from_result(self, result: dict) -> tuple[str, dict[int, str]]:
        """Extract text and structured data from LlamaParse result and split by pages."""
        text_by_page = {}
        full_text_parts = []
        
        # Debug: Log the result structure
        print(f"DEBUG: Result keys: {list(result.keys())}")
        if "job" in result:
            print(f"DEBUG: Job status: {result.get('job', {}).get('status')}")
        
        # LlamaParse v2 returns data in different formats
        # Try to get markdown/text from the result
        markdown = result.get("markdown", "")
        print(f"DEBUG: markdown type: {type(markdown)}, value preview: {str(markdown)[:100] if markdown else 'None'}")
        
        # Handle case where markdown might be a dict (nested structure)
        if isinstance(markdown, dict):
            print(f"DEBUG: markdown is dict, keys: {list(markdown.keys())}")
            # Check if it has a 'pages' array (LlamaParse v2 structure)
            if "pages" in markdown:
                pages = markdown["pages"]
                print(f"DEBUG: Found pages array with {len(pages)} pages")
                page_texts = []
                page_numbers = []
                for page in pages:
                    # Get page number if available
                    page_num = page.get("page_number", page.get("page", len(page_texts) + 1))
                    # Each page can have 'markdown' or 'text' field
                    page_md = page.get("markdown", page.get("text", ""))
                    if isinstance(page_md, str) and page_md:
                        page_texts.append(page_md)
                        page_numbers.append(page_num)
                        print(f"DEBUG: Page {page_num}: extracted {len(page_md)} chars")
                    elif isinstance(page_md, dict):
                        # Nested structure
                        page_md = page_md.get("content", page_md.get("text", page_md.get("markdown", "")))
                        if isinstance(page_md, str) and page_md:
                            page_texts.append(page_md)
                            page_numbers.append(page_num)
                            print(f"DEBUG: Page {page_num}: extracted {len(page_md)} chars from nested dict")
                if page_texts:
                    # Store page numbers for later use in text_by_page
                    markdown = "\n\n".join(page_texts)
                    print(f"DEBUG: Extracted {len(page_texts)} pages from markdown dict, total length: {len(markdown)}")
                    # Store page numbers and texts for later use in text_by_page
                    result["_extracted_pages"] = list(zip(page_numbers, page_texts))
                else:
                    markdown = ""
                    print("DEBUG: No text extracted from pages array")
            else:
                # Try other dict structures
                markdown = markdown.get("content", markdown.get("text", markdown.get("markdown", "")))
        
        # Ensure markdown is a string
        if not isinstance(markdown, str):
            markdown = ""
        
        if not markdown:
            # Try alternative fields
            text = result.get("text", "")
            if isinstance(text, dict):
                # Check if text also has pages structure
                if "pages" in text:
                    pages = text["pages"]
                    page_texts = []
                    for page in pages:
                        page_txt = page.get("text", page.get("markdown", ""))
                        if isinstance(page_txt, str) and page_txt:
                            page_texts.append(page_txt)
                    if page_texts:
                        markdown = "\n\n".join(page_texts)
                else:
                    text = text.get("content", text.get("text", ""))
            if isinstance(text, str) and text:
                markdown = text
            elif not markdown:
                # Try getting from top-level pages array
                pages = result.get("pages", [])
                if pages:
                    page_texts = []
                    for page in pages:
                        page_md = page.get("markdown", page.get("text", ""))
                        if isinstance(page_md, dict):
                            page_md = page_md.get("content", page_md.get("text", page_md.get("markdown", "")))
                        if isinstance(page_md, str) and page_md:
                            page_texts.append(page_md)
                    if page_texts:
                        markdown = "\n\n".join(page_texts)
        
        # If still no markdown, try items array
        if not markdown:
            items = result.get("items", [])
            if items:
                item_texts = []
                for item in items:
                    if isinstance(item, dict):
                        # Extract text from item
                        item_text = item.get("text", item.get("markdown", item.get("content", "")))
                        if isinstance(item_text, str) and item_text:
                            item_texts.append(item_text)
                        elif isinstance(item_text, dict):
                            # Nested structure
                            item_text = item_text.get("content", item_text.get("text", ""))
                            if isinstance(item_text, str) and item_text:
                                item_texts.append(item_text)
                if item_texts:
                    markdown = "\n\n".join(item_texts)
        
        # Final check: if markdown is still not a string, log and use empty string
        if not isinstance(markdown, str):
            print(f"Warning: Could not extract text from LlamaParse result. Result structure: {list(result.keys())}")
            print(f"DEBUG: Full result structure (first level): {[(k, type(v).__name__) for k, v in result.items()]}")
            markdown = ""
        
        print(f"DEBUG: Final markdown length: {len(markdown)} characters")
        if markdown:
            print(f"DEBUG: Markdown preview (first 500 chars): {markdown[:500]}")
            # Split by page markers if present (LlamaParse may add these)
            # Pattern: "--- Page X ---" or similar
            page_splits = re.split(r'(?:^|\n)---\s*[Pp]age\s*(\d+)\s*---\s*\n?', markdown, flags=re.MULTILINE)
            
            if len(page_splits) > 1:
                # Has page markers
                # First element is content before first page marker (usually empty)
                for i in range(1, len(page_splits), 2):
                    if i < len(page_splits):
                        page_num = int(page_splits[i])
                        page_text = page_splits[i + 1] if i + 1 < len(page_splits) else ""
                        text_by_page[page_num] = page_text.strip()
                        full_text_parts.append(f"--- PAGE {page_num} ---\n{page_text.strip()}")
            else:
                # No page markers in text, but we might have page info from the original structure
                # If markdown came from a pages array, preserve page numbers
                if "_extracted_pages" in result:
                    # Use the original page numbers and texts we extracted
                    for page_num, page_text in result["_extracted_pages"]:
                        text_by_page[page_num] = page_text
                        full_text_parts.append(f"--- PAGE {page_num} ---\n{page_text}")
                    print(f"DEBUG: Preserved original page numbers: {[p[0] for p in result['_extracted_pages']]}")
                elif isinstance(result.get("markdown"), dict) and "pages" in result.get("markdown", {}):
                    # Fallback: We already extracted from pages, so use the markdown as-is
                    # Split by paragraphs and assign to pages based on content
                    paragraphs = markdown.split('\n\n')
                    chars_per_page = 2000  # More realistic for actual documents
                    current_page = 1
                    current_text = []
                    char_count = 0
                    
                    for para in paragraphs:
                        para_len = len(para)
                        if char_count + para_len > chars_per_page and current_text:
                            # Start new page
                            page_text = '\n\n'.join(current_text)
                            text_by_page[current_page] = page_text
                            full_text_parts.append(f"--- PAGE {current_page} ---\n{page_text}")
                            current_page += 1
                            current_text = [para]
                            char_count = para_len
                        else:
                            current_text.append(para)
                            char_count += para_len
                    
                    # Add remaining text
                    if current_text:
                        page_text = '\n\n'.join(current_text)
                        text_by_page[current_page] = page_text
                        full_text_parts.append(f"--- PAGE {current_page} ---\n{page_text}")
                else:
                    # No page markers, split by approximate page breaks or treat as single page
                    # Try to split by common page break patterns
                    paragraphs = markdown.split('\n\n')
                    # Estimate pages (rough heuristic: ~500 chars per page)
                    chars_per_page = 500
                    current_page = 1
                    current_text = []
                    char_count = 0
                    
                    for para in paragraphs:
                        para_len = len(para)
                        if char_count + para_len > chars_per_page and current_text:
                            # Start new page
                            page_text = '\n\n'.join(current_text)
                            text_by_page[current_page] = page_text
                            full_text_parts.append(f"--- PAGE {current_page} ---\n{page_text}")
                            current_page += 1
                            current_text = [para]
                            char_count = para_len
                        else:
                            current_text.append(para)
                            char_count += para_len
                    
                    # Add remaining text
                    if current_text:
                        page_text = '\n\n'.join(current_text)
                        text_by_page[current_page] = page_text
                        full_text_parts.append(f"--- PAGE {current_page} ---\n{page_text}")
        else:
            # No content found
            text_by_page[1] = ""
            full_text_parts.append("--- PAGE 1 ---\n")
        
        full_text = "\n\n".join(full_text_parts)
        return full_text, text_by_page
    
    # ==========================================================================
    # NUMBER EXTRACTION METHODS
    # ==========================================================================
    
    async def extract_numbers(self, pdf_bytes: bytes) -> PDFExtraction:
        """
        Main extraction method: gets text from LlamaParse, then uses LLM for structured parsing.
        Uses regex as initial candidate finder, then LLM (Gemini) does the intelligent parsing.
        
        Args:
            pdf_bytes: Raw PDF file content
            
        Returns:
            PDFExtraction with full text, per-page text, and numeric candidates
        """
        full_text, text_by_page = await self.extract_text(pdf_bytes)
        
        candidates = ExtractedNumbers()
        
        # Use regex to find initial candidates (helps with context for LLM)
        # The LLM in llm_analyzer.py will do the final intelligent parsing
        print("Using regex-based parsing to find initial candidates (LLM will do final parsing)", flush=True)
        # #region agent log
        print(">>>DEBUGPOINT_A: BEFORE regex loop<<<", flush=True)
        import json as _j0; open(r'c:\Users\bring\Desktop\loan_app\.cursor\debug.log','a').write(_j0.dumps({"hypothesisId":"H1a","location":"pdf_extractor.py:extract_numbers:before_regex","message":"About to start regex loop","data":{"pages":len(text_by_page)},"timestamp":__import__('time').time()})+'\n')
        # #endregion
        # Process each page to maintain location info
        for page_num, page_text in text_by_page.items():
            # #region agent log
            print(f">>>DEBUGPOINT_B: Processing page {page_num}, text length: {len(page_text)}<<<", flush=True)
            # #endregion
            self._extract_from_page(page_text, page_num, candidates)
        
        # #region agent log
        print(f">>>DEBUGPOINT_C: AFTER regex loop, candidates found<<<", flush=True)
        import json as _j1; open(r'c:\Users\bring\Desktop\loan_app\.cursor\debug.log','a').write(_j1.dumps({"hypothesisId":"H1b","location":"pdf_extractor.py:extract_numbers:after_regex","message":"Regex parsing completed","data":{"loan_amounts":len(candidates.loan_amounts),"interest_rates":len(candidates.interest_rates),"term_months":len(candidates.term_months)},"timestamp":__import__('time').time()})+'\n')
        # #endregion
        # Debug: Log extraction results
        if not (candidates.loan_amounts and candidates.interest_rates and candidates.term_months):
            print(f"Extraction summary: loan_amounts={len(candidates.loan_amounts)}, "
                  f"interest_rates={len(candidates.interest_rates)}, "
                  f"term_months={len(candidates.term_months)}")
            # Log actual text content (skip page markers)
            if full_text:
                # Remove page markers and show actual content
                content_only = full_text.replace('--- PAGE', '').replace('---', '')
                preview = content_only[:2000] if len(content_only) > 2000 else content_only
                print(f"Text preview (first 2000 chars of actual content):\n{preview}")
                print(f"Total document text length: {len(full_text)} characters")
                
                # Check if text looks like it was extracted properly
                if len(full_text.strip()) < 100:
                    print("WARNING: Very little text extracted - document may be scanned/image-based")
                elif 'loan' not in full_text.lower() and 'amount' not in full_text.lower():
                    print("WARNING: No loan-related keywords found in extracted text")
            else:
                print("WARNING: No text extracted from PDF - document may be scanned/image-based")
        
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
        
        # Ensure page_text is a string (defensive check)
        if not isinstance(page_text, str):
            print(f"Warning: page_text is not a string for page {page_num}, type: {type(page_text)}")
            page_text = str(page_text) if page_text else ""
        
        # 1. Loan amounts (keyword + currency)
        # #region agent log
        print(f">>>REGEX_1: loan_amount_pattern starting<<<", flush=True)
        # #endregion
        for match in self.loan_amount_pattern.finditer(page_text):
            value = self._parse_currency(match.group(1))
            if value and 1000 <= value <= 10_000_000:  # Reasonable loan range
                candidates.loan_amounts.append(NumericCandidate(
                    value=value,
                    raw_text=match.group(0),
                    page=page_num,
                    context=self._get_context(page_text, match.start(), match.end())
                ))
        # #region agent log
        print(f">>>REGEX_1: loan_amount_pattern DONE<<<", flush=True)
        # #endregion
        
        # 2. Interest rates (keyword + percentage)
        # #region agent log
        print(f">>>REGEX_2: interest_rate_pattern starting<<<", flush=True)
        # #endregion
        for match in self.interest_rate_pattern.finditer(page_text):
            value = float(match.group(1))
            if 0 < value <= 50:  # Reasonable interest rate range
                candidates.interest_rates.append(NumericCandidate(
                    value=value,
                    raw_text=match.group(0),
                    page=page_num,
                    context=self._get_context(page_text, match.start(), match.end())
                ))
        # #region agent log
        print(f">>>REGEX_2: interest_rate_pattern DONE<<<", flush=True)
        # #endregion
        
        # 3. Monthly payments (keyword + currency)
        # #region agent log
        print(f">>>REGEX_3: payment_pattern starting<<<", flush=True)
        # #endregion
        for match in self.payment_pattern.finditer(page_text):
            value = self._parse_currency(match.group(1))
            if value and 50 <= value <= 100_000:  # Reasonable payment range
                candidates.monthly_payments.append(NumericCandidate(
                    value=value,
                    raw_text=match.group(0),
                    page=page_num,
                    context=self._get_context(page_text, match.start(), match.end())
                ))
        # #region agent log
        print(f">>>REGEX_3: payment_pattern DONE<<<", flush=True)
        # #endregion
        
        # 4. Loan term
        # #region agent log
        print(f">>>REGEX_4: term_pattern starting<<<", flush=True)
        # #endregion
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
        
        # #region agent log
        print(f">>>REGEX_4: term_pattern DONE<<<", flush=True)
        # #endregion
        
        # 5. Fees (keyword + currency)
        # #region agent log
        print(f">>>REGEX_5: fee_pattern starting<<<", flush=True)
        # #endregion
        for match in self.fee_pattern.finditer(page_text):
            value = self._parse_currency(match.group(1))
            if value and 0 < value <= 50_000:  # Reasonable fee range
                candidates.fees.append(NumericCandidate(
                    value=value,
                    raw_text=match.group(0),
                    page=page_num,
                    context=self._get_context(page_text, match.start(), match.end())
                ))
        # #region agent log
        print(f">>>REGEX_5: fee_pattern DONE<<<", flush=True)
        # #endregion
        
        # Fallback: If no keyword-based matches found, try standalone patterns
        # This helps with documents that don't use standard keywords
        if not candidates.loan_amounts:
            self._extract_standalone_loan_amounts(page_text, page_num, candidates)
        
        if not candidates.interest_rates:
            self._extract_standalone_interest_rates(page_text, page_num, candidates)
        
        if not candidates.term_months:
            self._extract_standalone_terms(page_text, page_num, candidates)
    
    def _extract_standalone_loan_amounts(
        self, page_text: str, page_num: int, candidates: ExtractedNumbers
    ):
        """Extract loan amounts without keywords - looks for large currency values."""
        # Look for currency values in reasonable loan range
        for match in self.standalone_currency.finditer(page_text):
            value = self._parse_currency(match.group(1))
            if value and 10000 <= value <= 10_000_000:  # Large amounts likely to be loans
                # Check context to avoid false positives (e.g., dates, account numbers)
                context = self._get_context(page_text, match.start(), match.end(), window=50)
                context_lower = context.lower()
                # Skip if it looks like a date, account number, or other non-loan amount
                if any(skip in context_lower for skip in ['date', 'account', 'phone', 'pin', 'id']):
                    continue
                candidates.loan_amounts.append(NumericCandidate(
                    value=value,
                    raw_text=match.group(0),
                    page=page_num,
                    context=context
                ))
    
    def _extract_standalone_interest_rates(
        self, page_text: str, page_num: int, candidates: ExtractedNumbers
    ):
        """Extract interest rates without keywords - looks for percentage values in reasonable range."""
        for match in self.standalone_percent.finditer(page_text):
            value = float(match.group(1))
            if 0.1 <= value <= 50:  # Reasonable interest rate range
                context = self._get_context(page_text, match.start(), match.end(), window=50)
                context_lower = context.lower()
                # Skip if it looks like a discount, tax rate, or other percentage
                if any(skip in context_lower for skip in ['discount', 'tax', 'gst', 'vat', 'commission']):
                    continue
                candidates.interest_rates.append(NumericCandidate(
                    value=value,
                    raw_text=match.group(0),
                    page=page_num,
                    context=context
                ))
    
    def _extract_standalone_terms(
        self, page_text: str, page_num: int, candidates: ExtractedNumbers
    ):
        """Extract loan terms without keywords - looks for month/year patterns."""
        for match in self.standalone_term.finditer(page_text):
            months_val = match.group(1)
            years_val = match.group(2)
            
            if months_val:
                value = int(months_val)
            elif years_val:
                value = int(years_val) * 12
            else:
                continue
            
            if 6 <= value <= 480:  # 6 months to 40 years
                context = self._get_context(page_text, match.start(), match.end(), window=50)
                context_lower = context.lower()
                # Skip if it looks like a date or age
                if any(skip in context_lower for skip in ['age', 'year old', 'born', 'date of']):
                    continue
                candidates.term_months.append(NumericCandidate(
                    value=float(value),
                    raw_text=match.group(0),
                    page=page_num,
                    context=context
                ))
    
    def _parse_currency(self, raw: str) -> Optional[float]:
        """
        Parse a currency string to float.
        Handles:
        - US/Western: $25,000.00 or $25,000
        - Indian: Rs 25,00,000 or ₹25,00,000 (lakhs/crores format)
        - Plain: 25000 or 25000.00
        """
        try:
            # Remove currency symbols
            cleaned = raw.upper()
            for char in ['$', '₹', 'RS', 'RS.', ' ']:
                cleaned = cleaned.replace(char, '')
            
            # Detect Indian number format (has commas in lakhs/crores pattern: 25,00,000)
            # Indian format: groups of 2 digits after first 3 digits
            # US format: groups of 3 digits
            if ',' in cleaned:
                parts = cleaned.split(',')
                # Check if it's Indian format (e.g., "25,00,000" = 3 parts, last two are 2 digits)
                if len(parts) >= 3 and len(parts[-1]) == 2 and len(parts[-2]) == 2:
                    # Indian format: remove all commas and parse
                    cleaned = cleaned.replace(',', '')
                else:
                    # US format: just remove commas
                    cleaned = cleaned.replace(',', '')
            else:
                # No commas, just remove any remaining formatting
                pass
            
            cleaned = cleaned.strip('.')
            return float(Decimal(cleaned))
        except:
            return None
    
    def _populate_from_structured_data(
        self, 
        structured_data: dict, 
        candidates: ExtractedNumbers,
        text_by_page: dict[int, str],
        full_text: str
    ):
        """Populate candidates from LlamaParse structured extraction."""
        # Helper to find page number for a value by searching text
        def find_page_for_value(value, search_text):
            if not value:
                return 1
            value_str = str(value)
            for page_num, page_text in text_by_page.items():
                if value_str in page_text:
                    return page_num
            return 1  # Default to page 1
        
        # Extract loan amount
        if "loan_amount" in structured_data and structured_data["loan_amount"] is not None:
            try:
                value = float(structured_data["loan_amount"])
                page = find_page_for_value(value, full_text)
                candidates.loan_amounts.append(NumericCandidate(
                    value=value,
                    raw_text=f"Loan Amount: {value}",
                    page=page,
                    context="Extracted via LlamaParse structured extraction"
                ))
                print(f"Extracted loan_amount: {value}")
            except (ValueError, TypeError) as e:
                print(f"Warning: Could not parse loan_amount: {structured_data.get('loan_amount')}, error: {e}")
        
        # Extract interest rate
        if "interest_rate" in structured_data and structured_data["interest_rate"] is not None:
            try:
                value = float(structured_data["interest_rate"])
                page = find_page_for_value(value, full_text)
                candidates.interest_rates.append(NumericCandidate(
                    value=value,
                    raw_text=f"Interest Rate: {value}%",
                    page=page,
                    context="Extracted via LlamaParse structured extraction"
                ))
                print(f"Extracted interest_rate: {value}")
            except (ValueError, TypeError) as e:
                print(f"Warning: Could not parse interest_rate: {structured_data.get('interest_rate')}, error: {e}")
        
        # Extract term in months
        if "term_months" in structured_data and structured_data["term_months"] is not None:
            try:
                value = int(structured_data["term_months"])
                page = find_page_for_value(value, full_text)
                candidates.term_months.append(NumericCandidate(
                    value=float(value),
                    raw_text=f"Term: {value} months",
                    page=page,
                    context="Extracted via LlamaParse structured extraction"
                ))
                print(f"Extracted term_months: {value}")
            except (ValueError, TypeError) as e:
                print(f"Warning: Could not parse term_months: {structured_data.get('term_months')}, error: {e}")
        
        # Extract monthly payment (optional)
        if "monthly_payment" in structured_data and structured_data["monthly_payment"] is not None:
            try:
                value = float(structured_data["monthly_payment"])
                page = find_page_for_value(value, full_text)
                candidates.monthly_payments.append(NumericCandidate(
                    value=value,
                    raw_text=f"Monthly Payment: {value}",
                    page=page,
                    context="Extracted via LlamaParse structured extraction"
                ))
                print(f"Extracted monthly_payment: {value}")
            except (ValueError, TypeError) as e:
                print(f"Warning: Could not parse monthly_payment: {structured_data.get('monthly_payment')}, error: {e}")
        
        # Extract fees (optional)
        if "fees" in structured_data and structured_data["fees"] is not None:
            try:
                value = float(structured_data["fees"])
                page = find_page_for_value(value, full_text)
                candidates.fees.append(NumericCandidate(
                    value=value,
                    raw_text=f"Fees: {value}",
                    page=page,
                    context="Extracted via LlamaParse structured extraction"
                ))
                print(f"Extracted fees: {value}")
            except (ValueError, TypeError) as e:
                print(f"Warning: Could not parse fees: {structured_data.get('fees')}, error: {e}")
    
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
        # Gemini 1.5 Pro supports up to 1M tokens, but we'll use a conservative limit
        # ~4 chars per token, so 100k chars ≈ 25k tokens (well within limits)
        max_chars = 100000  # Increased from 15000 to handle larger documents
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
    # Validate inputs
    if principal is None or annual_rate is None or term_months is None:
        raise ValueError("All parameters must be provided (principal, annual_rate, term_months)")
    
    if term_months <= 0:
        raise ValueError(f"term_months must be positive, got {term_months}")
    
    if principal < 0:
        raise ValueError(f"principal must be non-negative, got {principal}")
    
    if annual_rate == 0:
        return principal / term_months
    
    monthly_rate = annual_rate / 12 / 100
    n = term_months
    
    numerator = monthly_rate * ((1 + monthly_rate) ** n)
    denominator = ((1 + monthly_rate) ** n) - 1
    
    if denominator == 0:
        raise ValueError("Invalid calculation: denominator is zero")
    
    return principal * (numerator / denominator)


def calculate_total_interest(principal: float, monthly_payment: float, term_months: int) -> float:
    """Calculate total interest paid over the life of the loan."""
    # Validate inputs
    if principal is None or monthly_payment is None or term_months is None:
        raise ValueError("All parameters must be provided (principal, monthly_payment, term_months)")
    
    if term_months <= 0:
        raise ValueError(f"term_months must be positive, got {term_months}")
    
    total_paid = monthly_payment * term_months
    return total_paid - principal

