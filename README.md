# 🧠 DocIntel AI — Document Intelligence + Agentic RAG

> AI-powered document parsing, classification, and question answering with grounded citations.

![Python](https://img.shields.io/badge/Python-3.10+-blue?style=flat-square&logo=python)
![Next.js](https://img.shields.io/badge/Next.js-15-black?style=flat-square&logo=next.js)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

## 📋 Overview

DocIntel AI is a full-stack web application that:
- **Parses** messy real-world documents — scanned PDFs, handwritten pages, image-heavy reports, tables, and plain text
- **Classifies** each document using an LLM across multiple dimensions (type, topic, sensitivity, etc.)
- **Powers a chatbot** that answers questions with inline citations showing exact source pages
- **Ensures security** at every layer — encryption at rest, rate limiting, file validation, and more

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Frontend (Next.js)                 │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────┐  │
│  │  Chatbot Page │  │ Upload Page  │  │Voice Input│  │
│  │  + Citations  │  │ + Progress   │  │(Web Speech│  │
│  │  + Page Modal │  │ + WebSocket  │  │   API)    │  │
│  └──────┬───────┘  └──────┬───────┘  └───────────┘  │
└─────────┼──────────────────┼────────────────────────┘
          │ REST API         │ REST + WS
┌─────────┼──────────────────┼────────────────────────┐
│         ▼                  ▼     Backend (FastAPI)    │
│  ┌─────────────────────────────────────────────┐     │
│  │          Security Middleware Layer            │     │
│  │  Rate Limiting · CORS · Headers · Sanitize   │     │
│  └─────────────────────────────────────────────┘     │
│  ┌──────────┐ ┌───────────┐ ┌──────────────────┐    │
│  │ Document │ │ Document  │ │   Agentic RAG    │    │
│  │ Parser   │ │Classifier │ │ (Query Routing + │    │
│  │(PDF/OCR/ │ │(Gemini    │ │  Chunk Grading + │    │
│  │ Tables)  │ │ LLM)      │ │  Citation Gen)   │    │
│  └────┬─────┘ └─────┬─────┘ └────────┬─────────┘    │
│       │              │                │               │
│  ┌────▼──────────────▼────────────────▼─────────┐    │
│  │              Storage Layer                     │    │
│  │  SQLite (metadata) · ChromaDB (vectors)       │    │
│  │  AES-256 Encrypted Files · HMAC Integrity     │    │
│  └───────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────┘
```

## ✨ Features

### 1. Document Parser
- **PDF (digital)**: Text + table extraction via pdfplumber, metadata via PyMuPDF
- **PDF (scanned)**: OCR via pytesseract with image preprocessing (grayscale, binarization)
- **Images**: Direct OCR with preprocessing pipeline
- **Text files**: Chunked into pages with rendered page images
- **Tables**: Extracted as structured markdown, preserving row/column layout

### 2. Document Classifier
- Multi-dimensional classification using Google Gemini LLM
- JSON schema: `document_type`, `topic`, `content_characteristics`, `sensitivity_level`, `summary`, `key_entities`, `confidence_score`
- Rule-based fallback when LLM is unavailable

### 3. Agentic RAG
- **Query Router**: Determines if retrieval is needed or if it's conversational
- **Retriever**: ChromaDB with sentence-transformers embeddings (all-MiniLM-L6-v2)
- **Chunk Grader**: LLM evaluates each retrieved chunk for relevance
- **Generator**: Synthesizes answer with inline citations `[DocName, Page X]`
- **Hallucination Guard**: Responds honestly when no relevant content exists

### 4. Chatbot Page
- Multi-turn conversation with history
- Citations with clickable page thumbnails
- Full-page image modal on thumbnail click
- Suggestion chips for quick queries

### 5. Bulk Upload Page
- Drag & drop multiple files
- Real-time status per file: Uploading → Parsing → Classifying → Indexed
- WebSocket for live progress updates
- Classification preview when processing completes

### 6. Voice Input (Bonus)
- Real-time speech-to-text using Web Speech API
- Live transcript displayed as user speaks
- Auto-fills chat input when speech ends
- Browser compatibility detection

## 🛡️ Security Decisions

### ✅ Implemented

| Layer | Security Measure | Details |
|-------|-----------------|---------|
| **Upload** | File type validation | Magic bytes verification (not just extension) to prevent spoofing |
| **Upload** | Size limits | 50MB per file, 200MB total per request |
| **Upload** | Filename sanitization | Path traversal prevention, null byte removal, safe char whitelist |
| **Storage** | AES-256-GCM encryption | All stored files (documents + page images) encrypted at rest |
| **Storage** | HMAC-SHA256 integrity | Tamper detection on all encrypted files |
| **Storage** | Key derivation | PBKDF2 with 100K iterations, per-file unique keys |
| **API** | Rate limiting | 30 req/min uploads, 60 req/min chat, per IP |
| **API** | CORS restrictions | Whitelist only the frontend origin |
| **API** | Security headers | X-Content-Type-Options, X-Frame-Options, CSP, etc. |
| **API** | Input sanitization | Chat input length limits, null byte removal |
| **API** | Request size limits | Configurable max body size |
| **Retrieval** | No direct file access | Page images decrypted on-the-fly, never served as static files |

### 🤔 Considered but Skipped

- **User authentication (JWT)**: Out of scope for demo — would add login, sessions, per-user document isolation
- **Virus/malware scanning**: Would require ClamAV or similar; added file type validation as baseline
- **End-to-end encryption**: Would need client-side key management infrastructure
- **Content Security Policy**: Partially implemented via headers; full CSP would need nonce-based script loading

### 🔮 Would Add Given More Time

- **JWT authentication** with role-based access control
- **Audit logging** — track who accessed which documents and when
- **Document access control** — per-user or per-group document permissions
- **Encrypted vector store** — encrypt ChromaDB embeddings at rest
- **WAF (Web Application Firewall)** — for production deployment
- **Automated vulnerability scanning** in CI/CD pipeline
- **Data retention policies** — auto-delete documents after configurable period

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+**
- **Node.js 18+**
- **Tesseract OCR** — [Install guide](https://github.com/tesseract-ocr/tesseract#installing-tesseract)
  - Windows: Download from [UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki)
  - macOS: `brew install tesseract`
  - Linux: `sudo apt install tesseract-ocr`
- **Poppler** (for pdf2image) — Optional, PyMuPDF used as fallback
  - Windows: Download from [poppler releases](https://github.com/oschwartz10612/poppler-windows/releases)
  - macOS: `brew install poppler`
  - Linux: `sudo apt install poppler-utils`

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY from https://aistudio.google.com/

# Run the server
python main.py
# API will be available at http://localhost:8000
# Docs at http://localhost:8000/docs
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Configure environment
cp .env.local.example .env.local

# Run the dev server
npm run dev
# App will be available at http://localhost:3000
```

### Sample Documents

6 sample documents are included in `backend/sample_documents/` and will be automatically loaded on first startup:
1. **Financial Report** — Quarterly results with revenue tables
2. **Scientific Paper** — Academic research with benchmarks
3. **Meeting Minutes** — Board meeting with action items
4. **Employee Handbook** — HR policies with salary tables
5. **Environmental Impact Report** — Assessment with data tables
6. **Medical Research Summary** — Clinical trial results

## 🗂️ Project Structure

```
├── backend/
│   ├── main.py                 # FastAPI application entry
│   ├── config.py               # Settings & environment
│   ├── security/
│   │   ├── encryption.py       # AES-256-GCM file encryption
│   │   ├── middleware.py       # Rate limiting, headers, sanitization
│   │   └── file_validation.py  # MIME validation, magic bytes
│   ├── services/
│   │   ├── parser.py           # Document parsing (PDF/OCR/text)
│   │   ├── classifier.py      # LLM document classification
│   │   ├── embeddings.py      # ChromaDB + sentence-transformers
│   │   ├── rag_agent.py       # Agentic RAG pipeline
│   │   └── storage.py         # Encrypted file storage
│   ├── models/
│   │   ├── database.py        # SQLAlchemy models
│   │   └── schemas.py         # Pydantic schemas
│   ├── routers/
│   │   ├── upload.py          # Upload endpoints + WebSocket
│   │   ├── chat.py            # Chat/RAG endpoints
│   │   └── documents.py       # Document management
│   └── sample_documents/      # 6 included sample docs
├── frontend/
│   └── src/
│       ├── app/
│       │   ├── page.tsx       # Chatbot page
│       │   ├── upload/page.tsx # Bulk upload page
│       │   ├── layout.tsx     # Root layout
│       │   └── globals.css    # Design system
│       ├── components/
│       │   └── Navbar.tsx     # Navigation
│       └── lib/
│           └── api.ts         # API client
└── README.md
```

## 🔧 Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python, FastAPI |
| Frontend | Next.js 15, TypeScript |
| PDF Parsing | pdfplumber, PyMuPDF |
| OCR | pytesseract, Pillow |
| LLM | Google Gemini 2.0 Flash (free tier) |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| Vector Store | ChromaDB |
| RAG | LangChain |
| Database | SQLite + SQLAlchemy |
| Encryption | AES-256-GCM (cryptography library) |
| Voice | Web Speech API (browser-native) |

## 📝 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/upload` | Upload files for processing |
| GET | `/api/upload/status/{task_id}` | Check processing status |
| WS | `/ws/upload-status/{task_id}` | Real-time status updates |
| POST | `/api/chat` | Send chat message, get RAG response |
| GET | `/api/documents` | List all documents |
| GET | `/api/documents/{id}/pages/{page}/image` | Get page image |
| DELETE | `/api/documents/{id}` | Delete a document |
| GET | `/api/stats` | System statistics |
| GET | `/health` | Health check |

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
