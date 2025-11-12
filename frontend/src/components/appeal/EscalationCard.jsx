import { useState } from 'react'
import { useAppealStore } from '../../store/appealStore'
import { useAppealStream } from '../../hooks/useAppealStream'
import styles from './EscalationCard.module.css'

export default function EscalationCard() {
  const {
    escalated, escalationReason, missingEvidence,
    evidenceItems, confidenceScore, denialText,
  } = useAppealStore()

  const { submit } = useAppealStream()
  const [notes, setNotes] = useState('')
  const [reDrafting, setReDrafting] = useState(false)

  const pct = Math.round((confidenceScore || 0) * 100)

  const foundItems = (evidenceItems || []).filter(e => e.contradicts_denial)
  const notFoundItems = (evidenceItems || []).filter(e => !e.contradicts_denial)

  async function handleReDraft() {
    if (!notes.trim() || reDrafting) return
    setReDrafting(true)
    const augmented = `${denialText}\n\nPhysician notes: ${notes.trim()}`
    await submit(augmented)
    setReDrafting(false)
  }

  return (
    <div className={styles.card}>
      {/* Header */}
      <div className={styles.header}>
        <span className={styles.warningIcon}>⚠</span>
        <div>
          <h2 className={styles.title}>Physician Input Required</h2>
          <span className={styles.confidenceTag} style={{ color: '#dc2626' }}>
            Evidence confidence: {pct}%
          </span>
        </div>
      </div>

      {escalationReason && (
        <p className={styles.reason}>{escalationReason}</p>
      )}

      {/* Section A — What was found */}
      <div className={styles.section}>
        <div className={styles.sectionLabel}>Evidence found (partial):</div>
        <div className={styles.itemList}>
          {foundItems.length === 0 && notFoundItems.length === 0 && (
            <div className={styles.itemRow}>
              <span className={styles.iconX}>✗</span>
              <span className={styles.itemText}>No supporting evidence retrieved</span>
            </div>
          )}
          {foundItems.map((item, i) => (
            <div key={i} className={styles.itemRow}>
              <span className={styles.iconCheck}>✓</span>
              <span className={styles.itemText}>
                {item.title || item.source}
                {item.source && <span className={styles.srcTag}>[{item.source}]</span>}
              </span>
            </div>
          ))}
          {notFoundItems.slice(0, 3).map((item, i) => (
            <div key={i} className={styles.itemRow}>
              <span className={styles.iconX}>✗</span>
              <span className={styles.itemTextMuted}>{item.title || item.source}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Section B — What is missing */}
      {missingEvidence && missingEvidence.length > 0 && (
        <div className={styles.section}>
          <div className={styles.sectionLabel}>To complete this appeal, please provide:</div>
          <ol className={styles.gapList}>
            {missingEvidence.map((gap, i) => (
              <li key={i} className={styles.gapItem}>{gap}</li>
            ))}
          </ol>
        </div>
      )}

      {/* Clinical notes input */}
      <div className={styles.notesSection}>
        <label className={styles.notesLabel}>Add your clinical notes</label>
        <textarea
          className={styles.notesTextarea}
          value={notes}
          onChange={e => setNotes(e.target.value)}
          placeholder={
            'Example: Patient tried methotrexate 15mg weekly for 4 months ' +
            '(Jan–Apr 2024), discontinued due to hepatotoxicity. ' +
            'Then tried leflunomide 20mg daily for 3 months…'
          }
        />
        <button
          className={styles.reDraftBtn}
          onClick={handleReDraft}
          disabled={!notes.trim() || reDrafting}
        >
          {reDrafting ? (
            <><span className={styles.spinner} /> Running agent…</>
          ) : (
            'Re-draft with my notes →'
          )}
        </button>
      </div>
    </div>
  )
}
