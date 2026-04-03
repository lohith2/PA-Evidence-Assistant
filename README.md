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

**[🚀 Live Demo](https://pa-evidence-assistant.vercel.app)** 

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

| Layer | Technology | Purpose |
|---|---|---|
| **API** | FastAPI + Python 3.12 | REST API with SSE streaming |
| **Pipeline** | LangGraph 0.2 | Agentic graph with conditional routing |
| **LLM** | Google Gemini 2.5 Flash/Pro | All agent nodes |
| **Embeddings** | Voyage AI voyage-3 | Pinecone vector search |
| **Vector DB** | Pinecone | FDA labels, guidelines, payer policies |
| **Cache** | Redis (Upstash) | Semantic query caching |
| **Database** | Supabase (PostgreSQL) | Case persistence and analytics |
| **Live Data** | OpenFDA + PubMed APIs | On-demand drug labels and abstracts |
| **Frontend** | React 18 + Vite + Zustand | UI with real-time SSE streaming |
| **PDF** | jsPDF | Client-side letter export |
| **Hosting** | Render + Vercel + Upstash | Backend, frontend, managed Redis |

---

## 💡 Key Technical Decisions

**Why LangGraph over a simple chain?**
The workflow has real conditional branching — admin errors short-circuit the pipeline, low confidence routes to escalation, quality failures loop back to redraft. LangGraph makes these transitions explicit and debuggable.

**Why hybrid search?**
BM25 catches exact drug names and policy codes; vector search catches semantic similarity for clinical concepts. RRF fusion combines both without manual weight tuning — neither alone is sufficient for medical retrieval.

**Why confidence threshold at 0.72?**
Below 0.72, the agent lacks sufficient evidence for a defensible clinical argument. A weak letter is worse than escalating — it wastes physician review time and signals poor judgment to the insurer's medical director.

**Why live OpenFDA fallback?**
Pre-indexing every FDA-approved drug is impractical and stale. The fallback fetches on demand and auto-ingests to Pinecone — first query takes ~2s, every subsequent query hits the index at <0.5s.

**Why quality checker loops back?**
LLMs hallucinate citations and invent FDA section numbers. A second LLM pass cross-references every claim against retrieved chunks, re-drafting automatically if quality < 0.70 (max 2 loops).

---

## 🚀 Quick Start

```bash
git clone https://github.com/lohith2/PA-Evidence-Assistant.git
cd PA-Evidence-Assistant
cp .env.example .env
docker compose up --build
```

**Required env vars:** `GEMINI_API_KEY` · `PINECONE_API_KEY` · `VOYAGE_API_KEY` · `DATABASE_URL` · `REDIS_URL`

---

<div align="center">

Built using LangGraph · FastAPI · React · Pinecone · Voyage AI · Google Gemini

*Portfolio project by [lohith2](https://github.com/lohith2) — demonstrating agentic RAG, hybrid retrieval, and production ML system design*

**[🚀 Try the Live Demo](https://pa-evidence-assistant.vercel.app)**
## License

MIT © 2026 Lohith Reddy Kondreddy

</div>

