"""
LoanLens API - Loan Document Analysis

FastAPI application for analyzing loan documents using PDF extraction + LLM.
"""

import os
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Query, Response
from fastapi.middleware.cors import CORSMiddleware

from models.schemas import (
    DocumentUploadResponse,
    SummaryResponse,
    SummaryData,
    KeyNumbers,
    Highlight,
    RedFlagsResponse,
    RedFlag,
    HiddenClausesResponse,
    HiddenClause,
    FinancialTermsResponse,
    FinancialTerm,
    TermExample,
    ChatRequest,
    ChatResponse,
    ChatReference,
    Location,
)
from services.pdf_extractor import PDFExtractor
from services.llm_analyzer import (
    analyze_for_summary, 
    generate_summary_from_regex_only,
    analyze_for_red_flags,
    generate_red_flags_from_regex_only,
    analyze_for_hidden_clauses,
    generate_hidden_clauses_from_regex_only,
    analyze_for_financial_terms,
    generate_financial_terms_from_regex_only,
    chat_with_document,
)


# ==========================================================================
# APP INITIALIZATION
# ==========================================================================

app = FastAPI(
    title="LoanLens API",
    description="AI-powered loan document analysis",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage (replace with database in production)
documents_store: dict[str, dict] = {}
summaries_store: dict[str, dict] = {}
red_flags_store: dict[str, dict] = {}
hidden_clauses_store: dict[str, dict] = {}
financial_terms_store: dict[str, dict] = {}
conversations_store: dict[str, list[dict]] = {}  # conversation_id -> list of messages

# PDF extractor instance
pdf_extractor = PDFExtractor()


# ==========================================================================
# DOCUMENT UPLOAD ENDPOINT
# ==========================================================================

@app.post("/documents", response_model=DocumentUploadResponse, status_code=201)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """
    Upload a loan document PDF for analysis.
    
    Returns a document_id to use with other endpoints.
    Triggers background processing for summary extraction.
    """
    # Validate file type
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    # Read file content
    content = await file.read()
    
    if len(content) == 0:
        raise HTTPException(status_code=422, detail="Empty file")
    
    # Generate document ID
    doc_id = f"doc_{uuid.uuid4().hex[:12]}"
    
    # Store document
    documents_store[doc_id] = {
        "id": doc_id,
        "filename": file.filename,
        "content": content,
        "uploaded_at": datetime.now(timezone.utc),
        "status": "processing"
    }
    
    # Trigger background processing
    background_tasks.add_task(process_document, doc_id)
    
    return DocumentUploadResponse(
        document_id=doc_id,
        filename=file.filename,
        uploaded_at=documents_store[doc_id]["uploaded_at"],
        status="processing"
    )


async def process_document(doc_id: str):
    """Background task to process uploaded document."""
    try:
        doc = documents_store[doc_id]
        pdf_bytes = doc["content"]
        
        # Step 1: Extract text and numeric candidates from PDF
        print(f"DEBUG: Starting PDF extraction for document {doc_id}")
        extraction = await pdf_extractor.extract_numbers(pdf_bytes)
        # #region agent log
        import json as _j2; open(r'c:\Users\bring\Desktop\loan_app\.cursor\debug.log','a').write(_j2.dumps({"hypothesisId":"H2","location":"main.py:process_document:after_extract","message":"extract_numbers returned","data":{"text_len":len(extraction.full_text)},"timestamp":__import__('time').time()})+'\n')
        # #endregion
        print(f"DEBUG: PDF extraction completed. Text length: {len(extraction.full_text)} chars")
        
        # Store extraction for later use by other endpoints
        doc["extraction"] = extraction
        
        # Step 2: Generate summary using LLM (or fallback to regex-only)
        print(f"DEBUG: Starting LLM analysis for document {doc_id}")
        # #region agent log
        import json as _j3; open(r'c:\Users\bring\Desktop\loan_app\.cursor\debug.log','a').write(_j3.dumps({"hypothesisId":"H5","location":"main.py:process_document:before_llm","message":"About to call analyze_for_summary","data":{"doc_id":doc_id},"timestamp":__import__('time').time()})+'\n')
        # #endregion
        try:
            summary_data = await analyze_for_summary(extraction, pdf_extractor)
            print(f"DEBUG: LLM analysis completed successfully for document {doc_id}")
        except Exception as llm_error:
            # Fallback to regex-only if LLM fails
            print(f"LLM analysis failed: {llm_error}, using regex fallback")
            summary_data = generate_summary_from_regex_only(extraction)
            
            if summary_data is None:
                # Provide detailed error about what's missing
                candidates = extraction.numeric_candidates
                found_items = []
                if candidates.loan_amounts:
                    found_items.append(f"loan amount ({len(candidates.loan_amounts)} found)")
                if candidates.interest_rates:
                    found_items.append(f"interest rate ({len(candidates.interest_rates)} found)")
                if candidates.term_months:
                    found_items.append(f"loan term ({len(candidates.term_months)} found)")
                
                missing_items = []
                if not candidates.loan_amounts:
                    missing_items.append("loan amount")
                if not candidates.interest_rates:
                    missing_items.append("interest rate")
                if not candidates.term_months:
                    missing_items.append("loan term")
                
                # Check if document is scanned/image-based
                doc_text_length = len(extraction.full_text.strip())
                is_scanned = doc_text_length < 100
                
                if is_scanned:
                    error_msg = (
                        f"LlamaParse extracted very little text (only {doc_text_length} characters). "
                        f"This could indicate: "
                        f"(1) The document is scanned/image-based and LlamaParse OCR didn't extract text properly, "
                        f"(2) LlamaParse API didn't return the content even though the job completed, or "
                        f"(3) The document format is not supported. "
                        f"Please check the LlamaParse dashboard to see if the job processed correctly. "
                        f"Missing required fields: {', '.join(missing_items)}."
                    )
                else:
                    error_msg = (
                        f"Insufficient data found in document. "
                        f"Found: {', '.join(found_items) if found_items else 'nothing'}. "
                        f"Missing required fields: {', '.join(missing_items)}. "
                        f"Please ensure the document contains loan amount, interest rate, and loan term information."
                    )
                raise Exception(error_msg)
        
        # Store summary
        print(f"DEBUG: Storing summary for document {doc_id}")
        summaries_store[doc_id] = {
            "status": "complete",
            "data": summary_data
        }
        print(f"DEBUG: Summary stored successfully. Status: {summaries_store[doc_id]['status']}")
        print(f"DEBUG: Verifying store - summaries_store now has {len(summaries_store)} entries: {list(summaries_store.keys())}")
        print(f"DEBUG: Verifying stored summary for {doc_id} exists: {doc_id in summaries_store}")
        if doc_id in summaries_store:
            stored_status = summaries_store[doc_id].get('status')
            has_data = 'data' in summaries_store[doc_id] and summaries_store[doc_id]['data'] is not None
            print(f"DEBUG: Stored summary status: {stored_status}, has_data: {has_data}")
        
        doc["status"] = "complete"
        print(f"DEBUG: Document {doc_id} status updated to: {doc['status']}")
        
    except Exception as e:
        print(f"Document processing failed: {e}")
        documents_store[doc_id]["status"] = "failed"
        summaries_store[doc_id] = {
            "status": "failed",
            "error": str(e)
        }


# ==========================================================================
# SUMMARY ENDPOINT
# ==========================================================================

@app.get("/documents/{document_id}/summary", response_model=SummaryResponse)
async def get_summary(document_id: str, response: Response):
    """
    Get the analyzed summary of a loan document.
    
    Returns key numbers (loan amount, interest rate, term, payments)
    and highlights about the loan terms.
    """
    # Add cache-control headers to prevent caching
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    response.headers["X-Request-Time"] = str(time.time())  # Add timestamp to help debug caching
    
    current_time = time.time()
    print(f"DEBUG: get_summary called for document {document_id} at {current_time}")
    print(f"DEBUG: summaries_store has {len(summaries_store)} entries: {list(summaries_store.keys())}")
    
    # Check document exists
    if document_id not in documents_store:
        raise HTTPException(status_code=404, detail="Document not found")
    
    doc = documents_store[document_id]
    doc_status = doc.get("status", "unknown")
    print(f"DEBUG: Document status: {doc_status}")
    
    # Check if summary is ready
    if document_id not in summaries_store:
        print(f"DEBUG: Summary not found in store for {document_id}")
        print(f"DEBUG: Document status is: {doc_status}")
        print(f"DEBUG: Available document IDs in store: {list(documents_store.keys())}")
        print(f"DEBUG: Available summary IDs in store: {list(summaries_store.keys())}")
        # If document processing failed, return failed status
        if doc_status == "failed":
            return SummaryResponse(
                document_id=document_id,
                status="failed",
                error="Document processing failed"
            )
        # Otherwise, still processing
        print(f"DEBUG: Returning processing status at {current_time}")
        return SummaryResponse(
            document_id=document_id,
            status="processing",
            data=None
        )
    
    summary = summaries_store[document_id]
    summary_status = summary.get("status", "unknown")
    print(f"DEBUG: Found summary in store for {document_id}")
    print(f"DEBUG: Summary status from store: {summary_status}")
    print(f"DEBUG: Summary keys: {list(summary.keys())}")
    print(f"DEBUG: Has 'data' key: {'data' in summary}")
    print(f"DEBUG: Data is None: {summary.get('data') is None}")
    
    if summary_status == "failed":
        print(f"DEBUG: Summary status is 'failed', returning failed response")
        return SummaryResponse(
            document_id=document_id,
            status="failed",
            error=summary.get("error", "Analysis failed")
        )
    
    # Build response from stored data
    try:
        data = summary.get("data")
        if data is None:
            print(f"ERROR: Summary data is None for {document_id} even though summary exists")
            print(f"DEBUG: Full summary object: {summary}")
            raise HTTPException(status_code=500, detail="Summary data is empty")
        
        print(f"DEBUG: Building response for {document_id}, data keys: {list(data.keys()) if data else 'None'}")
        
        # Validate data structure
        if not data:
            print(f"ERROR: Summary data is None for {document_id}")
            raise HTTPException(status_code=500, detail="Summary data is empty")
        
        if "key_numbers" not in data:
            print(f"ERROR: Missing 'key_numbers' in data for {document_id}")
            print(f"DEBUG: Data keys: {list(data.keys())}")
            raise HTTPException(status_code=500, detail="Summary data is missing key_numbers")
        
        response = SummaryResponse(
            document_id=document_id,
            status="complete",
            data=SummaryData(
                document_type=data.get("document_type", "Loan Agreement"),
                overview=data.get("overview", ""),
                key_numbers=KeyNumbers(
                    total_loan=data["key_numbers"].get("total_loan"),
                    monthly_payment=data["key_numbers"].get("monthly_payment"),
                    interest_rate=data["key_numbers"].get("interest_rate"),
                    term_months=data["key_numbers"].get("term_months"),
                    total_interest=data["key_numbers"].get("total_interest"),
                    fees=data["key_numbers"].get("fees")
                ),
                highlights=[
                    Highlight(type=h.get("type", "warning"), text=h.get("text", "")) 
                    for h in data.get("highlights", [])
                ]
            )
        )
        print(f"DEBUG: Successfully built response for {document_id} at {current_time}")
        print(f"DEBUG: Response status will be: complete")
        return response
        
    except KeyError as e:
        print(f"ERROR: Missing key in summary for {document_id}: {e}")
        print(f"DEBUG: Summary keys: {list(summary.keys())}")
        if "data" in summary:
            print(f"DEBUG: Data keys: {list(summary['data'].keys()) if summary['data'] else 'None'}")
        raise HTTPException(status_code=500, detail=f"Summary data is malformed: {str(e)}")
    except Exception as e:
        print(f"ERROR: Failed to build response for {document_id}: {type(e).__name__}: {e}")
        import traceback
        print(f"DEBUG: Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to build response: {str(e)}")


# ==========================================================================
# RED FLAGS ENDPOINT
# ==========================================================================

@app.get("/documents/{document_id}/red-flags", response_model=RedFlagsResponse)
async def get_red_flags(document_id: str, response: Response):
    """
    Get AI-detected red flags in the loan document.
    
    Red flags are unfavorable terms, unusual clauses, or potentially
    harmful conditions that the borrower should be aware of.
    """
    # Add cache-control headers to prevent caching
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    response.headers["X-Request-Time"] = str(time.time())
    
    # Check document exists
    if document_id not in documents_store:
        raise HTTPException(status_code=404, detail="Document not found")
    
    doc = documents_store[document_id]
    current_time = time.time()
    print(f"DEBUG: get_red_flags called for document {document_id} at {current_time}")
    
    # Check if extraction is ready
    if "extraction" not in doc:
        print(f"DEBUG: Extraction not ready for {document_id}, returning processing status")
        return RedFlagsResponse(
            document_id=document_id,
            status="processing",
            count=0,
            data=[]
        )
    
    # Check if we already analyzed this document
    print(f"DEBUG: red_flags_store has {len(red_flags_store)} entries: {list(red_flags_store.keys())}")
    if document_id in red_flags_store:
        print(f"DEBUG: Found red flags in store for {document_id}")
        stored = red_flags_store[document_id]
        if stored["status"] == "failed":
            return RedFlagsResponse(
                document_id=document_id,
                status="failed",
                error=stored.get("error", "Analysis failed")
            )
        return RedFlagsResponse(
            document_id=document_id,
            status="complete",
            count=stored["data"]["count"],
            data=[
                RedFlag(
                    id=rf["id"],
                    severity=rf["severity"],
                    title=rf["title"],
                    description=rf["description"],
                    location=Location(page=rf["location"]["page"], section=rf["location"]["section"]),
                    recommendation=rf["recommendation"]
                )
                for rf in stored["data"]["data"]
            ]
        )
    
    # Perform analysis on-demand
    try:
        extraction = doc["extraction"]
        try:
            result = await analyze_for_red_flags(extraction, pdf_extractor)
        except Exception as llm_error:
            print(f"LLM red flags analysis failed: {llm_error}, using regex fallback")
            result = generate_red_flags_from_regex_only(extraction)
        
        # Store for future requests
        red_flags_store[document_id] = {
            "status": "complete",
            "data": result
        }
        
        return RedFlagsResponse(
            document_id=document_id,
            status="complete",
            count=result["count"],
            data=[
                RedFlag(
                    id=rf["id"],
                    severity=rf["severity"],
                    title=rf["title"],
                    description=rf["description"],
                    location=Location(page=rf["location"]["page"], section=rf["location"]["section"]),
                    recommendation=rf["recommendation"]
                )
                for rf in result["data"]
            ]
        )
        
    except Exception as e:
        print(f"Red flags analysis failed: {e}")
        red_flags_store[document_id] = {
            "status": "failed",
            "error": str(e)
        }
        return RedFlagsResponse(
            document_id=document_id,
            status="failed",
            error=str(e)
        )


# ==========================================================================
# HIDDEN CLAUSES ENDPOINT
# ==========================================================================

@app.get("/documents/{document_id}/hidden-clauses", response_model=HiddenClausesResponse)
async def get_hidden_clauses(document_id: str, response: Response):
    """
    Get AI-detected hidden clauses in the loan document.
    
    Hidden clauses are complex legal language that is buried or easy to miss,
    translated to plain English for the borrower to understand.
    """
    # Add cache-control headers to prevent caching
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    response.headers["X-Request-Time"] = str(time.time())
    
    # Check document exists
    if document_id not in documents_store:
        raise HTTPException(status_code=404, detail="Document not found")
    
    doc = documents_store[document_id]
    current_time = time.time()
    print(f"DEBUG: get_hidden_clauses called for document {document_id} at {current_time}")
    
    # Check if extraction is ready
    if "extraction" not in doc:
        print(f"DEBUG: Extraction not ready for {document_id}, returning processing status")
        return HiddenClausesResponse(
            document_id=document_id,
            status="processing",
            count=0,
            data=[]
        )
    
    # Check if we already analyzed this document
    print(f"DEBUG: hidden_clauses_store has {len(hidden_clauses_store)} entries: {list(hidden_clauses_store.keys())}")
    if document_id in hidden_clauses_store:
        print(f"DEBUG: Found hidden clauses in store for {document_id}")
        stored = hidden_clauses_store[document_id]
        if stored["status"] == "failed":
            return HiddenClausesResponse(
                document_id=document_id,
                status="failed",
                error=stored.get("error", "Analysis failed")
            )
        return HiddenClausesResponse(
            document_id=document_id,
            status="complete",
            count=stored["data"]["count"],
            data=[
                HiddenClause(
                    id=hc["id"],
                    category=hc["category"],
                    title=hc["title"],
                    summary=hc["summary"],
                    original_text=hc["original_text"],
                    plain_english=hc["plain_english"],
                    impact=hc["impact"],
                    location=Location(page=hc["location"]["page"], section=hc["location"]["section"])
                )
                for hc in stored["data"]["data"]
            ]
        )
    
    # Perform analysis on-demand
    try:
        extraction = doc["extraction"]
        try:
            result = await analyze_for_hidden_clauses(extraction, pdf_extractor)
        except Exception as llm_error:
            print(f"LLM hidden clauses analysis failed: {llm_error}, using regex fallback")
            result = generate_hidden_clauses_from_regex_only(extraction)
        
        # Store for future requests
        hidden_clauses_store[document_id] = {
            "status": "complete",
            "data": result
        }
        
        return HiddenClausesResponse(
            document_id=document_id,
            status="complete",
            count=result["count"],
            data=[
                HiddenClause(
                    id=hc["id"],
                    category=hc["category"],
                    title=hc["title"],
                    summary=hc["summary"],
                    original_text=hc["original_text"],
                    plain_english=hc["plain_english"],
                    impact=hc["impact"],
                    location=Location(page=hc["location"]["page"], section=hc["location"]["section"])
                )
                for hc in result["data"]
            ]
        )
        
    except Exception as e:
        print(f"Hidden clauses analysis failed: {e}")
        hidden_clauses_store[document_id] = {
            "status": "failed",
            "error": str(e)
        }
        return HiddenClausesResponse(
            document_id=document_id,
            status="failed",
            error=str(e)
        )


# =========================================================================
# FINANCIAL TERMS ENDPOINT
# ==========================================================================

@app.get("/documents/{document_id}/financial-terms", response_model=FinancialTermsResponse)
async def get_financial_terms(
    document_id: str,
    response: Response,
    search: Optional[str] = Query(None, description="Filter terms by keyword")
):
    """
    Get AI-extracted financial terms from the loan document.
    
    Each term includes a plain English explanation and contextual examples
    using actual values from the document.
    
    Query Parameters:
    - search: Optional keyword to filter terms (e.g., "apr", "principal")
    """
    # Add cache-control headers to prevent caching
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    response.headers["X-Request-Time"] = str(time.time())
    
    # Check document exists
    if document_id not in documents_store:
        raise HTTPException(status_code=404, detail="Document not found")
    
    doc = documents_store[document_id]
    current_time = time.time()
    print(f"DEBUG: get_financial_terms called for document {document_id} at {current_time}")
    
    # Check if extraction is ready
    if "extraction" not in doc:
        print(f"DEBUG: Extraction not ready for {document_id}, returning processing status")
        return FinancialTermsResponse(
            document_id=document_id,
            status="processing",
            count=0,
            terms=[]
        )
    
    # Check if we already analyzed this document
    print(f"DEBUG: financial_terms_store has {len(financial_terms_store)} entries: {list(financial_terms_store.keys())}")
    if document_id in financial_terms_store:
        print(f"DEBUG: Found financial terms in store for {document_id}")
        stored = financial_terms_store[document_id]
        if stored["status"] == "failed":
            return FinancialTermsResponse(
                document_id=document_id,
                status="failed",
                error=stored.get("error", "Analysis failed")
            )
        
        terms = stored["data"]["terms"]
        
        # Apply search filter if provided
        if search:
            search_lower = search.lower()
            terms = [
                t for t in terms
                if search_lower in t["name"].lower() 
                or search_lower in t["full_name"].lower()
                or search_lower in t["short_description"].lower()
            ]
        
        return FinancialTermsResponse(
            document_id=document_id,
            status="complete",
            count=len(terms),
            terms=[
                FinancialTerm(
                    id=t["id"],
                    name=t["name"],
                    full_name=t["full_name"],
                    short_description=t["short_description"],
                    definition=t["definition"],
                    example=TermExample(
                        icon=t["example"]["icon"],
                        title=t["example"]["title"],
                        text=t["example"]["text"]
                    ),
                    your_value=t["your_value"],
                    location=Location(page=t["location"]["page"], section=t["location"]["section"])
                )
                for t in terms
            ]
        )
    
    # Perform analysis on-demand
    try:
        extraction = doc["extraction"]
        try:
            result = await analyze_for_financial_terms(extraction, pdf_extractor)
        except Exception as llm_error:
            print(f"LLM financial terms analysis failed: {llm_error}, using regex fallback")
            result = generate_financial_terms_from_regex_only(extraction)
        
        # Store for future requests
        financial_terms_store[document_id] = {
            "status": "complete",
            "data": result
        }
        
        terms = result["terms"]
        
        # Apply search filter if provided
        if search:
            search_lower = search.lower()
            terms = [
                t for t in terms
                if search_lower in t["name"].lower() 
                or search_lower in t["full_name"].lower()
                or search_lower in t["short_description"].lower()
            ]
        
        return FinancialTermsResponse(
            document_id=document_id,
            status="complete",
            count=len(terms),
            terms=[
                FinancialTerm(
                    id=t["id"],
                    name=t["name"],
                    full_name=t["full_name"],
                    short_description=t["short_description"],
                    definition=t["definition"],
                    example=TermExample(
                        icon=t["example"]["icon"],
                        title=t["example"]["title"],
                        text=t["example"]["text"]
                    ),
                    your_value=t["your_value"],
                    location=Location(page=t["location"]["page"], section=t["location"]["section"])
                )
                for t in terms
            ]
        )
        
    except Exception as e:
        print(f"Financial terms analysis failed: {e}")
        financial_terms_store[document_id] = {
            "status": "failed",
            "error": str(e)
        }
        return FinancialTermsResponse(
            document_id=document_id,
            status="failed",
            error=str(e)
        )


# ==========================================================================
# CHAT ENDPOINT
# ==========================================================================

@app.post("/documents/{document_id}/chat", response_model=ChatResponse)
async def chat_with_document_endpoint(document_id: str, request: ChatRequest):
    """
    Chat with the loan document - ask questions and get answers.
    
    Maintains conversation context via conversation_id for follow-up questions.
    If no conversation_id is provided, a new conversation is started.
    """
    # Check document exists
    if document_id not in documents_store:
        raise HTTPException(status_code=404, detail="Document not found")
    
    doc = documents_store[document_id]
    
    # Check if extraction is ready
    if "extraction" not in doc:
        raise HTTPException(
            status_code=422, 
            detail="Document is still being processed. Please wait and try again."
        )
    
    # Get or create conversation ID
    conversation_id = request.conversation_id
    if not conversation_id:
        conversation_id = f"conv_{uuid.uuid4().hex[:12]}"
    
    # Get conversation history
    conversation_history = conversations_store.get(conversation_id, [])
    
    try:
        extraction = doc["extraction"]
        
        # Get existing analysis results for context (red flags, hidden clauses, summary)
        analysis_context = {}
        if document_id in summaries_store:
            analysis_context["summary"] = summaries_store[document_id].get("data", {})
        if document_id in red_flags_store:
            analysis_context["red_flags"] = red_flags_store[document_id].get("data", {})
        if document_id in hidden_clauses_store:
            analysis_context["hidden_clauses"] = hidden_clauses_store[document_id].get("data", {})
        
        # Call chat function
        result = await chat_with_document(
            extraction,
            pdf_extractor,
            request.message,
            conversation_history,
            analysis_context
        )
        
        # Store this exchange in conversation history
        conversation_entry = {
            "message": request.message,
            "response": result["response"],
            "references": result["references"]
        }
        conversation_history.append(conversation_entry)
        conversations_store[conversation_id] = conversation_history
        
        # Build response
        return ChatResponse(
            document_id=document_id,
            conversation_id=conversation_id,
            response=result["response"],
            references=[
                ChatReference(
                    clause_id=ref.get("clause_id"),
                    page=ref["page"],
                    section=ref["section"]
                )
                for ref in result["references"]
            ]
        )
        
    except Exception as e:
        print(f"Chat failed: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"AI service unavailable: {str(e)}"
        )


# ==========================================================================
# HEALTH CHECK
# ==========================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "documents_count": len(documents_store)
    }



