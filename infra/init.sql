CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS appeal_cases (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      TEXT NOT NULL UNIQUE,
    user_id         TEXT NOT NULL,
    raw_denial_text TEXT NOT NULL,
    drug_or_procedure TEXT,
    payer           TEXT,
    denial_reason   TEXT,
    policy_code     TEXT,
    appeal_letter   TEXT,
    confidence_score FLOAT,
    quality_score   FLOAT,
    escalated       BOOLEAN DEFAULT FALSE,
    escalation_reason TEXT,
    citations       JSONB DEFAULT '[]',
    node_trace      JSONB DEFAULT '[]',
    status          TEXT DEFAULT 'draft',
    outcome         TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS evidence_items (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      TEXT REFERENCES appeal_cases(session_id),
    source          TEXT,
    title           TEXT,
    text            TEXT,
    relevance_score FLOAT,
    contradicts_denial BOOLEAN,
    url             TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS eval_results (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          TEXT REFERENCES appeal_cases(session_id),
    citation_accuracy   FLOAT,
    policy_compliance   FLOAT,
    clinical_accuracy   FLOAT,
    letter_quality      FLOAT,
    overall             FLOAT,
    reasoning           TEXT,
    evaluated_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cases_created ON appeal_cases(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cases_payer ON appeal_cases(payer);
CREATE INDEX IF NOT EXISTS idx_cases_outcome ON appeal_cases(outcome) WHERE outcome IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_evidence_session ON evidence_items(session_id);
