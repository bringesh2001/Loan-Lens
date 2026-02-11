# 🔍 Loan Lens

**AI-powered loan document analyzer** — Upload any loan agreement PDF and get instant insights: key financials, red flags, hidden clauses, financial term explanations, and an interactive chat to ask questions about your document.

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| **Summary & Key Numbers** | Extracts loan amount, interest rate, term, monthly payment, total interest, and fees |
| **Red Flags** | AI-detected unfavorable terms, unusual clauses, or risky conditions |
| **Hidden Clauses** | Complex legal language translated to plain English with impact analysis |
| **Financial Terms Glossary** | Jargon explained with definitions and document-specific examples |
| **Document Chat** | Ask questions about your loan in natural language with cited references |
| **PDF Highlighting** | Click any clause → exact text highlighted in the PDF viewer with toggle support |
| **Smart Currency Detection** | Auto-detects ₹/$/€/£ from the document and formats with correct locale grouping |

---

## 🛠 Tech Stack

### Backend
- **FastAPI** — async Python API framework
- **LlamaParse** — PDF text extraction
- **Groq** — LLM inference (Qwen 3)
- **Pydantic v2** — request/response validation

### Frontend
- **React 18** + **TypeScript**
- **Vite** — build tooling
- **TailwindCSS** + **shadcn/ui** — styling & components
- **TanStack Query** — server state management
- **react-pdf** — in-app PDF rendering with text layer highlighting
- **React Router** — client-side routing

---

## 📁 Project Structure

```
loan_app/
├── backend/
│   ├── main.py              # FastAPI app + all endpoints
│   ├── models/
│   │   └── schemas.py       # Pydantic request/response models
│   ├── services/
│   │   ├── pdf_extractor.py # PDF parsing + numeric extraction
│   │   └── llm_analyzer.py  # LLM prompts + regex fallbacks
│   ├── requirements.txt
│   └── .env                 # API keys (not committed)
├── frontend/
│   ├── src/
│   │   ├── components/      # React components
│   │   ├── context/         # DocumentContext (global state)
│   │   ├── lib/             # API client, types, utilities
│   │   └── main.tsx
│   ├── package.json
│   └── index.html
├── API_DESIGN.md             # API endpoint documentation
└── README.md
```

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.10+**
- **Node.js 18+** (or [Bun](https://bun.sh))
- **Groq API key** — [Get one free](https://console.groq.com)
- **LlamaParse API key** — [Get one free](https://cloud.llamaindex.ai)

### 1. Clone the repo

```bash
git clone https://github.com/bringesh2001/Loan-Lens.git
cd Loan-Lens
```

### 2. Backend setup

```bash
# Create and activate virtual environment
python -m venv loan_env
# Windows PowerShell:
.\loan_env\Scripts\Activate.ps1
# macOS/Linux:
# source loan_env/bin/activate

# Install dependencies
pip install -r backend/requirements.txt
```

Create `backend/.env` with your API keys:

```env
GROQ_API_KEY=your_groq_api_key
LLAMA_CLOUD_API_KEY=your_llamaparse_api_key
```

Start the backend:

```bash
cd backend
uvicorn main:app --reload
```

The API will be available at **http://localhost:8000** — docs at **/docs**.

### 3. Frontend setup

```bash
cd frontend
npm install    # or: bun install
npm run dev    # or: bun run dev
```

The app will be available at **http://localhost:8080**.

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/documents` | Upload a PDF for analysis |
| `GET` | `/documents/{id}/summary` | Get key numbers & highlights |
| `GET` | `/documents/{id}/red-flags` | Get detected red flags |
| `GET` | `/documents/{id}/hidden-clauses` | Get hidden clause analysis |
| `GET` | `/documents/{id}/financial-terms` | Get financial term explanations |
| `POST` | `/documents/{id}/chat` | Chat with the document |

See [API_DESIGN.md](./API_DESIGN.md) for full request/response schemas.

---

## 📄 License

This project is for educational and personal use.
