import { useState, useEffect } from 'react'
import { useAppealStore } from '../../store/appealStore'
import { generateAppealPDF } from '../../lib/generatePDF'
import styles from './AppealLetter.module.css'

const SOURCE_CHIP_COLORS = {
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

function ConfidenceMeter({ score }) {
  const pct = Math.round((score || 0) * 100)
  let color = '#dc2626'
  let label = 'Low'
  if (pct >= 75) { color = '#059669'; label = 'Strong' }
  else if (pct >= 50) { color = '#d97706'; label = 'Moderate' }

  return (
    <div className={styles.meter}>
      <span className={styles.meterLabel}>Evidence confidence</span>
      <div className={styles.meterTrack}>
        <div
          className={styles.meterFill}
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
      <span className={styles.meterPct} style={{ color }}>{pct}%</span>
      <span className={styles.meterText} style={{ color }}>{label}</span>
    </div>
  )
}

export default function AppealLetter({ onExportSuccess }) {
  const {
    appealLetter, confidenceScore, qualityScore, qualityIssues, citations,
    sessionId, denialInfo, setSubmitting, setSubmitted, setSubmitError, isSubmitting, isSubmitted,
  } = useAppealStore()

  const [editedLetter, setEditedLetter] = useState('')

  // Populate textarea when letter arrives
  useEffect(() => {
    if (appealLetter) setEditedLetter(appealLetter)
  }, [appealLetter])

  function copyLetter() {
    navigator.clipboard.writeText(editedLetter)
  }

  function downloadPDF() {
    generateAppealPDF({
      appealLetter: editedLetter,
      citations,
      claimId: denialInfo?.claim_id,
      drug: denialInfo?.drug_or_procedure,
      payer: denialInfo?.payer,
      confidenceScore,
      sessionId,
    })
  }

  async function handleSubmit() {
    if (!sessionId || isSubmitting || isSubmitted) return
    setSubmitting()
    try {
      const res = await fetch(`/cases/${sessionId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: 'submitted', appeal_letter: editedLetter }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setSubmitted()
      generateAppealPDF({
        appealLetter: editedLetter,
        citations,
        claimId: denialInfo?.claim_id,
        drug: denialInfo?.drug_or_procedure,
        payer: denialInfo?.payer,
        confidenceScore,
        sessionId,
      })
      onExportSuccess?.()
    } catch (err) {
      console.error('Submit failed:', err)
      setSubmitError()
    }
  }

  // Deduplicate citations by source
  const uniqueCitations = []
  const seen = new Set()
  for (const c of (citations || [])) {
    const key = c.source || c
    if (!seen.has(key)) {
      seen.add(key)
      uniqueCitations.push(c)
    }
  }

  return (
    <div className={styles.card}>
      {/* Header */}
      <div className={styles.header}>
        <div>
          <span className={styles.headerLabel}>Letter of Medical Necessity (draft)</span>
          <p className={styles.headerDisclaimer}>Review and edit before submitting. Attach patient's clinical notes, labs, and specialist letters to complete the appeal package.</p>
        </div>
        <ConfidenceMeter score={confidenceScore} />
      </div>

      {qualityScore != null && qualityScore < 0.80 && qualityIssues?.length > 0 && (
        <div style={{
          borderLeft: '3px solid var(--warn, #d97706)',
          background: 'var(--warn-bg, #fffbeb)',
          padding: '12px 16px',
          borderRadius: '0 8px 8px 0',
          marginBottom: '16px',
        }}>
          <p style={{
            fontSize: '0.78rem',
            fontWeight: 600,
            color: 'var(--warn, #d97706)',
            marginBottom: '8px',
            marginTop: 0,
          }}>
            {qualityIssues.length} item{qualityIssues.length !== 1 ? 's' : ''} to review before submitting
          </p>
          {qualityIssues.map((issue, i) => (
            <div key={i} style={{
              display: 'flex',
              gap: '8px',
              alignItems: 'flex-start',
              marginBottom: '6px',
            }}>
              <input
                type="checkbox"
                style={{ marginTop: '2px', accentColor: 'var(--warn, #d97706)', flexShrink: 0 }}
              />
              <span style={{ fontSize: '0.78rem', color: 'var(--ink-secondary, #6b7280)' }}>
                {issue}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Editable letter body */}
      <div className={styles.body}>
        <textarea
          className={styles.textarea}
          value={editedLetter}
          onChange={e => setEditedLetter(e.target.value)}
          spellCheck={false}
          placeholder="Appeal letter will appear here…"
        />
      </div>

      {/* Citation chips */}
      {uniqueCitations.length > 0 && (
        <div className={styles.citations}>
          <span className={styles.citationsLabel}>Sources cited:</span>
          <div className={styles.chips}>
            {uniqueCitations.map((c, i) => {
              const src = (c.source || String(c)).toUpperCase().split(' ')[0]
              const style = SOURCE_CHIP_COLORS[src] || SOURCE_CHIP_COLORS.GUIDELINES
              return (
                <span
                  key={i}
                  className={styles.chip}
                  style={{ background: style.bg, color: style.color }}
                >
                  {src}
                  {c.text ? <span className={styles.chipTitle}> {c.text.slice(0, 30)}</span> : null}
                </span>
              )
            })}
          </div>
        </div>
      )}

      {/* Action bar */}
      <div className={styles.actions}>
        <div className={styles.actionsLeft}>
          <button className={styles.ghostBtn} onClick={copyLetter}>Copy</button>
          <button className={styles.ghostBtn} onClick={downloadPDF}>Download PDF</button>
        </div>
        <button
          className={`${styles.submitBtn} ${isSubmitted ? styles.submittedBtn : ''}`}
          onClick={handleSubmit}
          disabled={isSubmitting || isSubmitted}
        >
          {isSubmitting ? (
            <><span className={styles.spinner} /> Exporting…</>
          ) : isSubmitted ? (
            '✓ PDF exported'
          ) : (
            'Approve and export PDF →'
          )}
        </button>
      </div>
    </div>
  )
}
