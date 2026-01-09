import { useState, useEffect } from 'react'
import { generateAppealPDF } from '../../lib/generatePDF'
import API_URL from '../../lib/api.js'
import styles from './CaseDetailDrawer.module.css'

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

export default function CaseDetailDrawer({ caseData, onClose, onStatusChange }) {
  const [details, setDetails] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    fetch(`${API_URL}/cases/` + caseData.session_id)
      .then(r => r.json())
      .then(d => {
        setDetails(d)
        setLoading(false)
      })
      .catch(e => {
        console.error(e)
        setLoading(false)
      })
  }, [caseData.session_id])

  const copyLetter = () => {
    if (details?.appeal_letter) {
      navigator.clipboard.writeText(details.appeal_letter)
    }
  }

  const downloadPdf = () => {
    if (!details?.appeal_letter) return
    generateAppealPDF({
      appealLetter: details.appeal_letter,
      citations: details.citations || [],
      claimId: details.claim_id,
      drug: details.drug_or_procedure,
      payer: details.payer,
      confidenceScore: details.confidence_score,
      sessionId: details.session_id,
    })
  }

  const dateStr = caseData.created_at
    ? new Date(caseData.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
    : '—'

  // Extract unique sources
  const sourceKeys = new Set()
  if (details?.evidence_items) {
    details.evidence_items.forEach(ev => {
      sourceKeys.add((ev.source || 'SRC').toUpperCase())
    })
  }
  // add PAYER if policy_code was found maybe? Or we just rely on evidence items
  const uniqueSources = Array.from(sourceKeys)

  return (
    <div className={styles.drawerOverlay}>
      <div className={styles.backdrop} onClick={onClose} />
      <div className={styles.drawer}>
        {/* Header */}
        <div className={styles.header}>
          <div className={styles.headerLeft}>
            <h2 className={styles.drugName}>{caseData.drug_or_procedure || 'Unknown'}</h2>
            <p className={styles.payerName}>{caseData.payer || 'Unknown Payer'}</p>
          </div>
          <div className={styles.headerRight}>
            <span className={`${styles.badge} ${styles['badge_' + caseData.status] || styles.badge_draft}`}>
              {caseData.status || 'draft'}
            </span>
            <button className={styles.closeButton} onClick={onClose}>
              &times;
            </button>
          </div>
        </div>

        {/* Section 1: Case details */}
        <div className={styles.section}>
          <div className={styles.sectionLabel}>Case Details</div>
          <div className={styles.detailGrid}>
            <div className={styles.detailItem}>
              <span className={styles.detailKey}>Claim ID</span>
              <span className={`${styles.detailVal} ${styles.mono}`}>{caseData.session_id.split('-')[0]}</span>
            </div>
            <div className={styles.detailItem}>
              <span className={styles.detailKey}>Date Submitted</span>
              <span className={styles.detailVal}>{dateStr}</span>
            </div>
            <div className={styles.detailItem}>
              <span className={styles.detailKey}>Confidence Score</span>
              <span className={styles.detailVal}>
                {caseData.confidence_score != null ? `${caseData.confidence_score}%` : '—'}
              </span>
            </div>
            <div className={styles.detailItem}>
              <span className={styles.detailKey}>Quality Score</span>
              <span className={styles.detailVal}>
                {caseData.quality_score != null ? `${caseData.quality_score}%` : '—'}
              </span>
            </div>
            <div className={styles.detailItem}>
              <span className={styles.detailKey}>Escalated</span>
              <span className={styles.detailVal}>{caseData.escalated ? 'Yes' : 'No'}</span>
            </div>
          </div>
        </div>

        {/* Section 2: Appeal letter */}
        <div className={styles.section}>
          <div className={styles.sectionLabel}>Letter of Medical Necessity</div>
          {loading ? (
            <div style={{ padding: 20, color: 'var(--text-muted)' }}>Loading...</div>
          ) : details?.appeal_letter ? (
            <div className={styles.letterBox}>{details.appeal_letter}</div>
          ) : (
            <div style={{ padding: 20, color: 'var(--text-muted)' }}>No appeal letter generated.</div>
          )}
        </div>

        {/* Section 3: Evidence sources */}
        {uniqueSources.length > 0 && (
          <div className={styles.section}>
            <div className={styles.sectionLabel}>Sources cited</div>
            <div className={styles.sourcesRow}>
              {uniqueSources.map(src => {
                const style = getBadgeStyle(src)
                return (
                  <span
                    key={src}
                    className={styles.sourceBadge}
                    style={{ background: style.bg, color: style.color }}
                  >
                    {src}
                  </span>
                )
              })}
            </div>
          </div>
        )}

        {/* Section 4: Actions */}
        <div className={styles.actions}>
          <button className={styles.btn} onClick={copyLetter}>Copy letter</button>
          <button className={styles.btn} onClick={downloadPdf}>Download PDF</button>
          {caseData.status === 'submitted' && (
            <>
              <button 
                className={`${styles.btn} ${styles.btnApprove}`}
                onClick={() => onStatusChange(caseData.session_id, 'approved')}
              >
                Mark approved
              </button>
              <button 
                className={`${styles.btn} ${styles.btnDeny}`}
                onClick={() => onStatusChange(caseData.session_id, 'denied')}
              >
                Mark denied
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
