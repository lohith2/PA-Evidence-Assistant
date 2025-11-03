# Prior Authorization Appeal Agent

A production-grade Agentic RAG system that automates medical prior authorization appeal letters in ~30 seconds.

## Architecture

**7-node LangGraph pipeline:**

```
denial_reader → policy_retriever → evidence_retriever →
contradiction_finder → [appeal_drafter | escalation_node] → quality_checker
```

| Node | Model | Role |
|------|-------|------|
| denial_reader | Haiku | Extract structured info from denial letter |
| policy_retriever | — | Hybrid BM25+semantic search for payer policy |
| evidence_retriever | Haiku | 3 parallel queries: guidelines, FDA, necessity |
| contradiction_finder | Sonnet | Synthesize contradictions, score confidence |
| appeal_drafter | Sonnet | Draft cited appeal letter |
| escalation_node | Haiku | Generate specific gap list when evidence insufficient |
| quality_checker | Haiku | Review letter, loop back if quality < 0.70 |

## Quick Start

```bash
# 1. Configure API keys
cp .env.example .env
# Fill in: ANTHROPIC_API_KEY, PINECONE_API_KEY, VOYAGE_API_KEY

# 2. Start all services
docker compose up --build

# 3. Ingest data (fetches CMS, FDA, PubMed, USPSTF, payer policies → Pinecone)
docker compose exec backend python scripts/download_data.py --all
# Target: >1000 vectors in Pinecone

# 4. Verify
docker compose exec backend python -c "
from pinecone import Pinecone
from config import settings
pc = Pinecone(api_key=settings.pinecone_api_key)
stats = pc.Index(settings.pinecone_index).describe_index_stats()
print(f'Vectors: {stats[\"total_vector_count\"]}')
"

# 5. Open
open http://localhost:3000

# 6. Test
curl -X POST http://localhost:8000/appeals/ \
  -H "Content-Type: application/json" \
  -d '{"denial_text": "BlueCross denying Humira under policy 4.2.1b. Insufficient DMARD failure documentation. Claim BCB-2024-PA-10392.", "user_id": "test"}'

# 7. Run tests
docker compose exec backend pytest tests/ -v
```

## API

| Method | Path | Description |
|--------|------|-------------|
| POST | /appeals/stream | SSE streaming — 7 node events |
| POST | /appeals/ | Sync version for testing |
| GET | /cases/ | List appeal cases |
| GET | /cases/{session_id} | Full case detail |
| POST | /eval/run | LLM-as-judge scoring |
| GET | /stats | Aggregate analytics |
| GET | /health | Liveness |

## Key Design Decisions

**Why BM25 for policy retrieval:** Policy codes like "4.2.1b" are opaque alphanumeric strings. Semantic embeddings treat them as near-meaningless tokens. BM25 exact match ensures the right policy section is always found.

**Why `contradicts_denial` per-chunk:** A session may retrieve 7 chunks where 3 support and 4 contradict the denial. Aggregating to a session-level boolean loses the granularity needed for targeted appeal arguments.

**Why quality_checker loops:** Real appeal letters get physician review before submission. The quality checker simulates that review automatically, with a max of 2 loops to prevent infinite revision.

**Why escalation produces a gap list:** "Needs physician review" is not actionable. "Provide documentation of DMARD trials with dates, duration, and discontinuation reason" is.

**Why confidence uses 3 weighted factors:** Retrieval score conflates relevance with authority. A highly relevant blog post should score lower than a moderately relevant FDA label. Diversity prevents one strong source from inflating the score.
