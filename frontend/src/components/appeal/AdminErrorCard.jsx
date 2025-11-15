import { useAppealStore } from '../../store/appealStore'
import { useAppealStream } from '../../hooks/useAppealStream'
import styles from './AdminErrorCard.module.css'

const ERROR_TYPE_LABELS = {
  icd10_mismatch: 'ICD-10 code mismatch',
  out_of_network: 'Out-of-network provider',
  duplicate: 'Duplicate submission',
  expired_pa: 'Expired or incorrect PA reference',
  missing_modifier: 'Missing billing modifier',
  plan_mismatch: 'Plan coverage mismatch',
}

function buildCorrectedDenial(original, errorType, correctCode, fix) {
  if (errorType === 'icd10_mismatch' && correctCode) {
    // Extract the first code from correctCode (may be "M05.xx or M06.xx")
    const firstCode = correctCode.split(/\s|,|or/)[0].trim()
    // Match ICD-10 pattern: letter + 2 digits + optional decimal + digits
    const icd10Pattern = /[A-Z]\d{2}\.?\d*/g
    const wrongCodes = original.match(icd10Pattern) || []

    let corrected = original
    for (const wrongCode of wrongCodes) {
      if (wrongCode !== firstCode) {
        corrected = corrected.replace(new RegExp(wrongCode, 'g'), firstCode)
        break // only replace the first mismatched code
      }
    }
    return corrected + `\n\n[Correction applied: ${fix}]`
  }
  return original + `\n\n[Correction applied: ${fix}]`
}

export default function AdminErrorCard() {
  const {
    adminErrorType, adminExplanation, adminSuggestion, adminCorrectCode,
    denialText, setDenialText, setCorrectionApplied,
  } = useAppealStore()
  const { submit } = useAppealStream()

  async function handleResubmit() {
    const correctedDenial = buildCorrectedDenial(
      denialText, adminErrorType, adminCorrectCode, adminSuggestion
    )
    setDenialText(correctedDenial)
    setCorrectionApplied(adminSuggestion || 'Correction applied')
    await submit(correctedDenial, { skipAdminCheck: true })
  }

  function handleForceAppeal() {
    submit(denialText, { skipAdminCheck: true })
  }

  const errorLabel = ERROR_TYPE_LABELS[adminErrorType] || adminErrorType || 'Administrative error'

  return (
    <div className={styles.card}>
      <div className={styles.header}>
        <span className={styles.icon}>⚠</span>
        <span className={styles.title}>Coding error detected — no clinical appeal needed</span>
      </div>

      <div className={styles.section}>
        <p className={styles.sectionLabel}>What we found</p>
        <p className={styles.sectionText}>
          <strong>{errorLabel}.</strong>{' '}
          {adminExplanation}
        </p>
      </div>

      {adminSuggestion && (
        <div className={styles.fixBox}>
          <p className={styles.fixLabel}>Suggested fix</p>
          <p className={styles.fixText}>{adminSuggestion}</p>
          {adminCorrectCode && (
            <p className={styles.correctCode}>
              Correct code: <code className={styles.code}>{adminCorrectCode}</code>
            </p>
          )}
        </div>
      )}

      <p className={styles.advice}>
        Resubmit the corrected claim before filing a clinical appeal — this is faster and more likely to succeed.
      </p>

      <div className={styles.actions}>
        <button className={styles.copyBtn} onClick={handleResubmit}>
          Resubmit with correction
        </button>
        <button className={styles.forceBtn} onClick={handleForceAppeal}>
          Build clinical appeal anyway
        </button>
      </div>
    </div>
  )
}
