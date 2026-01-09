<div align="center">

# 🏥 Prior Authorization Appeal Evidence Assistant

### An agentic RAG system that automates medical prior authorization appeals
### using a 7-node LangGraph pipeline, hybrid vector search, and live FDA evidence retrieval

[![FastAPI](https://img.shields.io/badge/FastAPI-0.104-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2-FF6B6B?style=flat-square)](https://langchain-ai.github.io/langgraph)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react)](https://react.dev)
[![Pinecone](https://img.shields.io/badge/Pinecone-Vector_DB-00A67E?style=flat-square)](https://pinecone.io)
[![Gemini](https://img.shields.io/badge/Gemini-2.5-4285F4?style=flat-square&logo=google)](https://deepmind.google/gemini)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker)](https://docker.com)

**[🚀 Live Demo](https://pa-evidence-assistant.vercel.app)** · **[📖 Documentation](#architecture)** · **[⚡ Quick Start](#getting-started)**

![Demo](https://img.shields.io/badge/Status-Live-brightgreen?style=flat-square)

</div>

---

## 🔍 The Problem

Medical prior authorization denials delay care for millions of patients annually. Medical affairs (MA) teams spend **2–4 hours per appeal** manually researching payer policies, pulling FDA labels, and drafting Letters of Medical Necessity — work that is repetitive, high-stakes, and error-prone.

> **This system automates the entire evidence gathering and drafting process in under 60 seconds.**

A medical assistant pastes a denial letter and patient chart notes. The 7-node agent pipeline:
- Retrieves the exact payer policy that was applied
- Searches FDA labels and clinical guidelines for contradicting evidence  
- Scores each piece of evidence against the denial reason
- Drafts a submission-ready Letter of Medical Necessity with proper citations
- Runs a quality check to catch hallucinated citations before submission

---

## ✨ Key Features

| Feature | Description |
|---|---|
| 🤖 **7-Node LangGraph Pipeline** | Conditional routing with quality control loops |
| 🚨 **Admin Error Detection** | Catches ICD-10 mismatches before clinical pipeline runs |
| 🔍 **Hybrid Retrieval** | BM25 + Voyage AI vector search with RRF fusion |
| 🌐 **Live FDA Fallback** | Fetches any drug label from OpenFDA on demand |
| 📚 **Self-Learning Index** | Auto-ingests live fetches into Pinecone for future queries |
| ✅ **Quality Checker** | Detects hallucinated citations and fabricated FDA section numbers |
| ⚠️ **Smart Escalation** | Generates specific actionable gaps when evidence is insufficient |
| 🔒 **HIPAA Safe Harbor** | PHI scrubber strips names, DOBs, SSNs before processing |
| 📄 **PDF Export** | Professional letterhead with citations and page numbers |
| 📊 **Case Analytics** | Supabase persistence with approval tracking and outcome analytics |

---

## 🧪 Test Results

| Drug | Payer | Condition | Confidence | Outcome |
|---|---|---|---|---|
| Adalimumab (Humira) | Cigna | Rheumatoid Arthritis | 89% | ✅ Letter |
| Pembrolizumab (Keytruda) | UnitedHealthcare | NSCLC | 95% | ✅ Letter |
| Dupilumab (Dupixent) | BlueCross | Atopic Dermatitis | 95% | ✅ Letter |
| Adalimumab (Humira) | UnitedHealthcare | Pediatric JIA | 95% | ✅ Letter |
| Tezepelumab (Tezspire) | Cigna | Severe Asthma | 95% | ✅ Letter + Live Fetch |
| Ustekinumab (Stelara) | Anthem | Psoriasis | 88–92% | ✅ Letter |
| Semaglutide (Ozempic) | Aetna | Type 2 Diabetes | 72–88% | ✅ Letter |
| Adalimumab (Humira) | Aetna | Wrong ICD-10 (M54.5) | N/A | ✅ Admin Error Caught |
| Apixaban + Rivaroxaban | Aetna | Dual Anticoagulant | 10% | ✅ Correct Escalation |
| Natalizumab (Tysabri) | Humana | MS — No Context | 15%→80% | ✅ Escalation → Letter |

---

## 🏗️ Architecture

### 7-Node LangGraph Pipeline
```
Denial Letter + Patient Context
│
▼
┌─────────────────────┐
│    denial_reader    │  ── Extract drug, payer, policy, denial reason
└──────────┬──────────┘     + regex fallbacks for payer/drug extraction
           │
           ▼
┌─────────────────────────┐
│  admin_error_checker    │  ── ICD-10 mismatch, wrong policy, duplicate PA
└──────────┬──────────────┘
           │
     is_admin_error? ──── YES ──→ AdminErrorCard (pipeline stops)
           │ NO
           ▼
┌─────────────────────┐
│  policy_retriever   │  ── Payer-filtered Pinecone query
└──────────┬──────────┘     Falls back to semantic if payer not found
           │
           ▼
┌──────────────────────┐
│ evidence_retriever   │  ── Hybrid BM25 + vector search
└──────────┬───────────┘     Live OpenFDA fallback if 0 drug-specific chunks
           │                 Auto-ingests to Pinecone (self-learning)
           ▼
┌──────────────────────────┐
│  contradiction_finder    │  ── Per-chunk LLM scoring (0.0–1.0)
└──────────┬───────────────┘     Computes overall confidence score
           │
     confidence >= 0.72? ── NO ──→ escalation_node
           │ YES                  (specific gaps + re-draft flow)
           ▼
┌─────────────────────┐
│   appeal_drafter    │  ── Structured Letter of Medical Necessity
└──────────┬──────────┘     [Per treating physician] + [FDA Label: X] citations
           │
           ▼
┌─────────────────────┐
│  quality_checker    │  ── Detects hallucinated citations
└──────────┬──────────┘     Loops back to drafter if quality < 0.70 (max 2x)
           │
           ▼
  Submission-Ready PDF
```

### Two-Tier Retrieval Strategy
```
Query arrives for drug X
│
▼
Pinecone vector search (Voyage AI voyage-3)
↕
BM25 keyword search on candidate set
↕
RRF fusion (k=60)
│
├── Drug-specific chunks found ──→ Use them (< 0.5s)
│
└── No drug-specific chunks
           │
           ▼
    Live OpenFDA API fetch (~2s)
    + PubMed abstract fetch
           │
           ▼
    Auto-ingest to Pinecone
    (next query hits index directly)
```

---

## 🛠️ Tech Stack

### Backend
| Technology | Purpose |
|---|---|
| **FastAPI + Python 3.12** | REST API with SSE streaming |
| **LangGraph 0.2** | Agentic pipeline with conditional routing |
| **Google Gemini 2.5 Flash/Pro** | LLM for all agent nodes |
| **Voyage AI voyage-3** | Text embeddings for Pinecone |
| **Pinecone** | Vector database for FDA labels and guidelines |
| **Redis (Upstash)** | Semantic query caching |
| **Supabase (PostgreSQL)** | Appeal case persistence and analytics |
| **OpenFDA API** | Live drug label fetching |
| **PubMed E-utilities** | Clinical literature abstracts |

### Frontend
| Technology | Purpose |
|---|---|
| **React 18 + Vite** | UI framework |
| **Zustand** | Global state management |
| **Recharts** | Analytics charts |
| **jsPDF** | Client-side PDF generation |
| **SSE (EventSource)** | Real-time pipeline progress streaming |

### Infrastructure
| Technology | Purpose |
|---|---|
| **Docker Compose** | Local development orchestration |
| **Render** | Backend hosting |
| **Vercel** | Frontend hosting |
| **Upstash** | Managed Redis |

---

## 🚀 Getting Started

### Prerequisites

- Docker and Docker Compose
- API keys for: Gemini, Pinecone, Voyage AI, Supabase

### Setup
```bash
# Clone the repository
git clone https://github.com/lohith2/PA-Evidence-Assistant.git
cd PA-Evidence-Assistant

# Create environment file
cp .env.example .env
# Fill in your API keys

# Start all services
docker compose up --build

# Run data ingestion (first time only)
docker compose exec backend python -m ingestion.ingest

# Open the app
open http://localhost:3000
```

### Environment Variables
```env
GEMINI_API_KEY=your-gemini-key
PINECONE_API_KEY=your-pinecone-key
PINECONE_INDEX=your-index-name
VOYAGE_API_KEY=your-voyage-key
DATABASE_URL=your-supabase-postgres-url
REDIS_URL=redis://localhost:6379
CORS_ORIGINS=http://localhost:3000
```

---

## 📁 Project Structure
```
PA-Evidence-Assistant/
├── backend/
│   ├── agent/
│   │   ├── nodes.py          # 7 LangGraph nodes
│   │   ├── graph.py          # Pipeline wiring + conditional edges
│   │   ├── state.py          # AgentState TypedDict
│   │   └── utils.py          # JSON parsing + PHI scrubbing
│   ├── retrieval/
│   │   ├── hybrid.py         # BM25 + Pinecone + RRF fusion
│   │   ├── cache.py          # Redis semantic cache
│   │   └── fda_live.py       # Live OpenFDA + PubMed fetch
│   ├── ingestion/
│   │   ├── ingest.py         # Ingestion pipeline
│   │   └── sources/          # FDA, guidelines, payer policies
│   ├── api/
│   │   ├── main.py           # FastAPI app + CORS
│   │   └── routes/
│   │       ├── appeals.py    # SSE streaming endpoint
│   │       ├── cases.py      # Case history CRUD
│   │       └── health.py     # Health check + stats
│   └── config.py             # Pydantic settings
├── frontend/
│   └── src/
│       ├── components/appeal/
│       │   ├── AgentTrace.jsx      # Real-time pipeline progress
│       │   ├── AppealLetter.jsx    # Letter editor + PDF export
│       │   ├── EvidencePanel.jsx   # Two-column evidence display
│       │   ├── EscalationCard.jsx  # Physician re-draft flow
│       │   └── AdminErrorCard.jsx  # ICD-10 correction flow
│       ├── pages/
│       │   ├── AppealPage.jsx      # Main appeal interface
│       │   ├── CasesPage.jsx       # Case history + drawer
│       │   └── AnalyticsPage.jsx   # Outcome analytics
│       ├── store/appealStore.js    # Zustand global state
│       ├── hooks/
│       │   ├── useAppealStream.js  # SSE event handler
│       │   └── usePageRefresh.js   # Auto-refresh on navigation
│       └── lib/
│           ├── api.js              # API base URL config
│           └── generatePDF.js      # jsPDF letter export
├── docker-compose.yml
├── render.yaml
└── README.md
```

---

## 💡 Key Technical Decisions

**Why LangGraph over a simple chain?**
The appeal workflow has conditional branching — admin error detection short-circuits the pipeline, low confidence triggers escalation instead of drafting, quality failures loop back to redraft. LangGraph's conditional edges make these transitions explicit, debuggable, and easy to extend.

**Why hybrid search?**
BM25 catches exact drug names and policy codes (sparse signal). Vector search catches semantic similarity for clinical concepts. RRF fusion combines both without manual weight tuning. Neither alone is sufficient for medical retrieval where exact terminology matters.

**Why confidence threshold at 0.72?**
Below 0.72, the agent lacks sufficient evidence to make a defensible clinical argument. Generating a weak letter is worse than escalating — it wastes physician review time and signals poor judgment to the insurer's medical director. The threshold was calibrated across 10+ denial scenarios.

**Why live OpenFDA fallback?**
Pre-indexing every FDA-approved drug is impractical and stale. The fallback fetches any label on demand and auto-ingests it into Pinecone. First query for a drug: ~2s live fetch. All subsequent queries: <0.5s from index. The knowledge base grows with usage.

**Why quality checker loops back?**
LLMs hallucinate citations and invent FDA section numbers. The quality checker runs a second LLM pass over the drafted letter, cross-referencing every claim against retrieved chunks. Letters scoring below 0.70 are automatically re-drafted (max 2 loops to prevent infinite cycles).

---

## 🔒 HIPAA Compliance Note

This system implements HIPAA Safe Harbor de-identification. Patient names, dates of birth, Social Security numbers, phone numbers, email addresses, and street addresses are automatically stripped before any text is sent to external AI services. Claim IDs and member IDs are preserved as they are required for appeal processing.

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

Built with ❤️ using LangGraph · FastAPI · React · Pinecone · Voyage AI · Google Gemini

**[🚀 Try the Live Demo](https://pa-evidence-assistant.vercel.app)**

</div>
