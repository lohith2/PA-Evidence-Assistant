import { useState, useRef } from 'react'
import { useAppealStore } from '../../store/appealStore'
import { useAppealStream } from '../../hooks/useAppealStream'
import styles from './DenialInput.module.css'

const EXAMPLES = [
  {
    label: 'Biologic for RA',
    text: `BlueCross BlueShield is denying prior authorization for adalimumab (Humira) 40mg biweekly for patient ID 4821-B under Medical Policy 4.2.1b — Biologic DMARD Agents. Denial reason: Medical records do not document adequate trial and failure of two conventional DMARDs (methotrexate and at least one additional agent) for a minimum of 3 months each. Claim ID: BCB-2024-PA-10392.`,
  },
  {
    label: 'GLP-1 for diabetes',
    text: `Aetna has denied prior authorization for semaglutide (Ozempic) 1mg weekly injection under pharmacy benefit policy RX-DM-2024-07. Denial reason: Patient's current HbA1c of 7.8% does not meet the threshold of >8.0% required for approval of GLP-1 receptor agonists under the diabetes management step therapy protocol. Patient must first demonstrate inadequate glycemic control on maximum tolerated dose of metformin plus a sulfonylurea. Claim ID: AET-2024-88821.`,
  },
  {
    label: 'MS medication',
    text: `UnitedHealthcare is denying coverage for ocrelizumab (Ocrevus) 600mg IV infusion under policy MS-BIO-2024. Denial reason: Medical records indicate diagnosis of relapsing-remitting MS (RRMS) with 1 relapse in the past 24 months. Policy requires documentation of 2 or more relapses in the preceding 12 months OR failure of at least one first-line disease modifying therapy (interferon beta or glatiramer acetate) for minimum 6 months. Claim ID: UHC-2024-MS-44721.`,
  },
]

export default function DenialInput() {
  const { denialText, setDenialText, patientContext, setPatientContext, status } = useAppealStore()
  const { submit } = useAppealStream()
  const [dragging, setDragging] = useState(false)
  const fileRef = useRef()
  const running = status === 'running'

  async function handleSubmit(e) {
    e.preventDefault()
    if (!denialText.trim() || running) return
    await submit(denialText.trim())
  }

  async function handleFile(file) {
    if (!file) return
    const form = new FormData()
    form.append('file', file)
    const resp = await fetch('/appeals/pdf/upload-pdf', { method: 'POST', body: form })
    if (resp.ok) {
      const { extracted_text } = await resp.json()
      setDenialText(extracted_text)
    }
  }

  function onDrop(e) {
    e.preventDefault()
    setDragging(false)
    handleFile(e.dataTransfer.files[0])
  }

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h1 className={styles.title}>Build Appeal Evidence Package</h1>
        <p className={styles.subtitle}>Paste the denial letter and patient context. The agent searches clinical guidelines, FDA labels, and peer-reviewed literature to build your evidence package and draft a Letter of Medical Necessity.</p>
      </div>

      <div className={styles.examples}>
        {EXAMPLES.map(ex => (
          <button
            key={ex.label}
            className={styles.exampleChip}
            onClick={() => setDenialText(ex.text)}
          >
            {ex.label}
          </button>
        ))}
      </div>

      <form onSubmit={handleSubmit}>
        <div
          className={`${styles.dropZone} ${dragging ? styles.dragging : ''}`}
          onDragOver={e => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
        >
          <textarea
            className={styles.textarea}
            value={denialText}
            onChange={e => setDenialText(e.target.value)}
            placeholder={`Paste the denial letter here, or describe the denial:\n\nExample: 'BlueCross denied Humira for our patient with severe rheumatoid arthritis under policy 4.2.1b, citing insufficient DMARD failure documentation.'`}
            rows={8}
            disabled={running}
          />
        </div>

        <div className={styles.contextSection}>
          <label className={styles.contextLabel}>Patient clinical context</label>
          <p className={styles.contextSub}>What the MA team brings from the chart</p>
          <textarea
            className={styles.contextTextarea}
            value={patientContext}
            onChange={e => setPatientContext(e.target.value)}
            placeholder={`Prior treatments tried (drug, dose, dates, reason stopped)\nRelevant lab values (A1c, DAS28, eGFR, LDL, etc.)\nDisease severity and duration\nSpecialist recommendations or consult notes\n\nLeave blank if unknown — the agent will flag what's missing.`}
            rows={5}
            disabled={running}
          />
        </div>

        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
          padding: '10px 14px', marginBottom: 16,
          background: 'rgba(16, 185, 129, 0.08)',
          border: '1px solid rgba(16, 185, 129, 0.2)',
          borderRadius: 8, fontSize: 13, color: 'var(--text-muted)',
        }}>
          <span style={{ fontSize: 16 }}>🔒</span>
          <span>
            <strong style={{ color: 'var(--text-primary)' }}>HIPAA Safe Harbor:</strong>{' '}
            Patient names, SSNs, DOBs, addresses, and other PHI are automatically
            de-identified before processing. No identifiable patient data is stored
            or sent to external services.
          </span>
        </div>

        <div className={styles.actions}>
          <button
            type="button"
            className={styles.uploadBtn}
            onClick={() => fileRef.current?.click()}
            disabled={running}
          >
            ↑ Upload PDF
          </button>
          <input
            ref={fileRef}
            type="file"
            accept=".pdf"
            style={{ display: 'none' }}
            onChange={e => handleFile(e.target.files[0])}
          />
          <div className={styles.submitWrap}>
            <button
              type="submit"
              className={styles.submitBtn}
              disabled={!denialText.trim() || running}
            >
              {running ? (
                <span className={styles.spinner} />
              ) : (
                'Find supporting evidence →'
              )}
            </button>
            {!running && (
              <p className={styles.hint}>Agent searches PubMed, FDA, CMS guidelines, and payer policies — typically 20–40 seconds</p>
            )}
          </div>
        </div>
      </form>
    </div>
  )
}
