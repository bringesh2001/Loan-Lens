LoanLens – Loan Document Analyzer
=================================

This repository contains:
- A **FastAPI backend** for analyzing loan PDFs (summary, red flags, hidden clauses, financial terms, chat).
- A **vanilla JavaScript frontend** in `frontend/` that consumes the FastAPI APIs.

---

Backend – FastAPI
-----------------

### 1. Prerequisites

- Python 3.11+ (3.13 is supported)

### 2. Create virtualenv and install dependencies

```bash
cd Loan-Lens
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure environment

Create a `.env` file in the project root:

```env
LLAMA_CLOUD_API_KEY=your_llama_parse_key_here
GROQ_API_KEY=your_groq_key_here
```

- Without these keys the backend still runs, but AI features will fall back to limited regex behaviour.

### 4. Run backend

```bash
uvicorn main:app --reload --port 8000
```

- API base URL (used by the frontend) is `http://127.0.0.1:8000`.
- OpenAPI/Swagger docs: `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/health`

### 5. High‑level API flow

1. `POST /documents` – upload a PDF, receive `document_id`.
2. `GET /documents/{document_id}/summary` – loan summary + key numbers.
3. `GET /documents/{document_id}/red-flags` – AI-detected red flags.
4. `GET /documents/{document_id}/hidden-clauses` – AI-detected hidden/complex clauses.
5. `GET /documents/{document_id}/financial-terms` – extracted financial terms.
6. `POST /documents/{document_id}/chat` – chat with the document.

All request/response schemas live in `models/schemas.py` and are documented in `API_DESIGN.md`.

---

Frontend – Vanilla JS SPA
-------------------------

The frontend lives entirely under:

- `frontend/`

Key pieces:

- `frontend/index.html` – entry HTML.
- `frontend/main.js` – app bootstrap.
- `frontend/router/router.js` – client‑side routing (`/`, `/upload`, `/analysis`, `/results`).
- `frontend/services/*.js` – HTTP + API service layer for calling FastAPI.
- `frontend/state/store.js` – minimal global state (current document, analysis results, UI loading/error).
- `frontend/styles/global.css` – global styles and layout shell.

### 1. Run frontend (simple static dev server)

In a second terminal **with the backend still running**:

```bash
cd Loan-Lens/frontend
python -m http.server 5173
```

Then open:

- `http://localhost:5173`

> Note: The frontend expects the backend at `http://127.0.0.1:8000`.  
> If you change the backend host/port, update `frontend/config/env.js`.

### 2. Frontend architecture (high level)

- **Routing**: HTML5 History API, defined in `frontend/router/router.js`.
- **Services**:
  - `http.service.js` – base fetch wrapper (timeouts, error handling).
  - `api.service.js` – one function per backend endpoint (upload, summary, red flags, etc.).
  - `pdf.service.js` / `llm.service.js` – domain‑level helpers built on top of `api.service.js`.
- **State**:
  - `store.js` holds current `document_id`, uploaded filename, and analysis results for use across pages.

Component/page directories are scaffolded under:

- `frontend/components/` – reusable UI pieces (buttons, loader, layout, feature components).
- `frontend/pages/` – route‑level pages (`home`, `upload`, `analysis`, `results`).

---

Typical Developer Workflow
--------------------------

1. **Start backend**
   ```bash
   cd Loan-Lens
   source .venv/bin/activate
   uvicorn main:app --reload --port 8000
   ```
2. **Start frontend dev server**
   ```bash
   cd Loan-Lens/frontend
   python -m http.server 5173
   ```
3. **Open app**
   - Visit `http://localhost:5173` in the browser.
4. **Upload and analyze a PDF**
   - Use the upload UI (or `POST /documents` in Swagger) to get a `document_id`.
   - Navigate through analysis/results views to explore summary, red flags, clauses, and terms.

---

Notes
-----

- Persistence is currently **in‑memory only** (Python dicts in `main.py`). Restarting the backend clears all uploaded documents and analysis results.
- For production use, you would typically:
  - Persist PDFs to blob storage or disk.
  - Store document metadata and analysis results in a database.
  - Replace the simple static server with a proper bundler/build pipeline for the frontend if needed.

