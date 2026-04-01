import { useAppealStore } from '../../store/appealStore'
import styles from './EvidencePanel.module.css'

const BADGE_STYLES = {
  CMS:      { bg: '#eff6ff', color: '#1d4ed8' },
  FDA:      { bg: '#fffbeb', color: '#b45309' },
  ACR:      { bg: '#f0fdf4', color: '#15803d' },
  AHA:      { bg: '#fef2f2', color: '#dc2626' },
  ADA:      { bg: '#ede9fe', color: '#5b21b6' },
  ASCO:     { bg: '#fce7f3', color: '#9d174d' },
  AAN:      { bg: '#e0f2fe', color: '#0c4a6e' },
  USPSTF:   { bg: '#f0fdfa', color: '#0f766e' },
  GUIDELINES:{ bg: '#f3f4f6', color: '#6b7280' },
  PAYER:    { bg: '#f8fafc', color: '#475569' },
}

function getBadgeStyle(source) {
  const key = (source || '').toUpperCase().split(' ')[0]
  return BADGE_STYLES[key] || BADGE_STYLES.GUIDELINES
}

function EvidenceCard({ item }) {
  const score = Math.round((item.relevance_score || 0) * 100)
  const badge = getBadgeStyle(item.source)

  return (
    <div className={`${styles.card} ${item.contradicts_denial ? styles.contradicts : ''}`}>
      <div className={styles.cardTop}>
        <span
          className={styles.badge}
          style={{ background: badge.bg, color: badge.color }}
        >
          {(item.source || 'SRC').toUpperCase()}
        </span>
        <span className={styles.score}>{score}%</span>
        {item.live_fetch && (
          <span style={{
            fontSize: '0.65rem',
            color: 'var(--info, #0c4a6e)',
            background: 'var(--info-bg, #e0f2fe)',
            padding: '1px 6px',
            borderRadius: '4px',
            marginLeft: '4px',
          }}>
            live
          </span>
        )}
        {item.contradicts_denial && (
          <span className={styles.contradictsPill}>Contradicts denial</span>
        )}
      </div>
      <div className={styles.cardTitle}>{item.title || 'Untitled'}</div>
      <p className={styles.cardExcerpt}>
        {(item.text || '').slice(0, 180)}{(item.text || '').length > 180 ? '…' : ''}
      </p>
    </div>
  )
}

export default function EvidencePanel() {
  const {
    nodeTrace, evidenceItems, policyChunks, denialInfo,
    payerFound,
  } = useAppealStore()

  // Show as soon as evidence_retriever completes — don't wait for done
  const evidenceDone = nodeTrace.some(
    n => n.node === 'evidence_retriever' && n.status === 'done'
  )
  const policyDone = nodeTrace.some(
    n => n.node === 'policy_retriever' && n.status === 'done'
  )

  if (!evidenceDone && !policyDone) return null

  const hasPolicyChunks = (policyChunks || []).length > 0

  // Left: payer policy chunks
  // Right: clinical items where contradicts_denial = true
  const rawItems = [
    ...(policyChunks || []).map(c => ({ ...c, contradicts_denial: false, source: 'PAYER' })),
    ...(evidenceItems || []),
  ]

  // Deduplicate by title+source to prevent same chunk appearing multiple times
  const seen = new Set()
  const allItems = rawItems.filter(item => {
    const key = `${item.source}:${item.title}`.toLowerCase()
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })

  // Left column: only PAYER-sourced items
  // Right column: clinical items that contradict the denial
  const payerItems = allItems.filter(i => (i.source || '').toUpperCase() === 'PAYER')
  const guidelineItems = allItems.filter(i => i.contradicts_denial && (i.source || '').toUpperCase() !== 'PAYER')

  // Show amber warning when payer policy not found
  const showPolicyWarning = policyDone && !hasPolicyChunks && !payerFound

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h2 className={styles.title}>Evidence Retrieved</h2>
        <span className={styles.meta}>
          {guidelineItems.length} item{guidelineItems.length !== 1 ? 's' : ''} contradict denial
        </span>
      </div>

      {showPolicyWarning && (
        <div style={{
          background: '#fffbeb',
          border: '1px solid #fcd34d',
          borderRadius: '8px',
          padding: '10px 14px',
          marginBottom: '12px',
          fontSize: '0.78rem',
          color: '#92400e',
          lineHeight: 1.5,
          margin: '12px 16px 0',
        }}>
          <strong>{denialInfo?.payer || 'Payer'}</strong> policy not found in our database.
          {' '}Letter drafted using general biologic coverage criteria.
          {' '}Verify against the actual policy before submitting.
        </div>
      )}

      <div className={styles.columns}>
        {/* Left — Payer policy */}
        <div className={styles.column}>
          <div className={styles.colHeader}>Payer policy says</div>
          <div className={styles.cards}>
            {showPolicyWarning ? (
              <div className={styles.empty}>
                No matching payer policy found
              </div>
            ) : payerItems.length === 0 ? (
              <div className={styles.empty}>
                {policyDone ? 'No policy sections found' : 'Retrieving…'}
              </div>
            ) : (
              payerItems.map((item, i) => (
                <EvidenceCard key={i} item={item} />
              ))
            )}
          </div>
        </div>

        {/* Right — Clinical guidelines */}
        <div className={styles.column}>
          <div className={styles.colHeader}>Guidelines say</div>
          <div className={styles.cards}>
            {guidelineItems.length === 0 ? (
              <div className={styles.empty}>
                {evidenceDone ? 'No contradicting guidelines found' : 'Searching…'}
              </div>
            ) : (
              guidelineItems.map((item, i) => (
                <EvidenceCard key={i} item={item} />
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
