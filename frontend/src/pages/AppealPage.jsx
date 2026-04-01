import { useEffect, useState } from 'react'
import API_URL from '../lib/api.js'
import DenialInput from '../components/appeal/DenialInput'
import AgentTrace from '../components/appeal/AgentTrace'
import EvidencePanel from '../components/appeal/EvidencePanel'
import AppealLetter from '../components/appeal/AppealLetter'
import EscalationCard from '../components/appeal/EscalationCard'
import AdminErrorCard from '../components/appeal/AdminErrorCard'
import { useAppealStore } from '../store/appealStore'
import styles from './AppealPage.module.css'

export default function AppealPage() {
  const {
    status, nodeTrace, escalated, appealLetter, errorMessage,
    loadedFromHistory, evidenceItems, adminError, sessionId,
    correctionApplied, correctionNote, clearCorrection,
    setLoaded, reset,
  } = useAppealStore()
  const [showBanner, setShowBanner] = useState(false)
  const [loadError, setLoadError] = useState('')

  // Preserve the current in-progress/generated appeal when navigating away and back.
  // Only reset when explicitly opening a saved history case, or when leaving history
  // mode and returning to a fresh /appeal route.
  useEffect(() => {
    const historySessionId = new URLSearchParams(window.location.search).get('session')
    setLoadError('')

    if (!historySessionId) {
      if (loadedFromHistory) reset()
      return
    }

    if (loadedFromHistory && sessionId === historySessionId) return

    reset()
    fetch(`${API_URL}/cases/${historySessionId}`)
      .then(r => {
        if (!r.ok) throw new Error('Case not found')
        return r.json()
      })
      .then(data => setLoaded(data))
      .catch(err => setLoadError(err.message))
  }, [loadedFromHistory, reset, sessionId, setLoaded]) // eslint-disable-line react-hooks/exhaustive-deps

  function handleExportSuccess() {
    setShowBanner(true)
    setTimeout(() => setShowBanner(false), 5000)
  }

  // Auto-dismiss correction banner when pipeline completes
  useEffect(() => {
    if (status === 'done' && correctionApplied) {
      const t = setTimeout(() => clearCorrection(), 3000)
      return () => clearTimeout(t)
    }
  }, [status, correctionApplied]) // eslint-disable-line react-hooks/exhaustive-deps

  const evidenceRetrieved = loadedFromHistory
    ? evidenceItems.length > 0
    : nodeTrace.some(n => n.node === 'evidence_retriever' && n.status === 'done')

  const showLetter = status === 'done' && !escalated && !!appealLetter
  const showEscalation = status === 'done' && escalated

  return (
    <div className={styles.page}>
      {showBanner && (
        <div className={styles.successBanner}>
          <span className={styles.bannerIcon}>✓</span>
          PDF ready. Submit by fax or through your payer's provider portal. Track outcome in Appeal Cases.
          <button className={styles.bannerClose} onClick={() => setShowBanner(false)}>✕</button>
        </div>
      )}

      <div className={styles.content}>
        {loadError && (
          <div className={styles.error}><strong>Error:</strong> {loadError}</div>
        )}

        {!loadedFromHistory && <DenialInput />}

        {status !== 'idle' && (
          <>
            {correctionApplied && (
              <div className={styles.correctionBanner}>
                Correction applied: {correctionNote}
              </div>
            )}

            {!loadedFromHistory && <AgentTrace />}

            {evidenceRetrieved && <EvidencePanel />}

            {status === 'done' && adminError && <AdminErrorCard />}

            {showLetter && <AppealLetter onExportSuccess={handleExportSuccess} />}

            {showEscalation && <EscalationCard />}

            {status === 'error' && (
              <div className={styles.error}>
                <strong>Error:</strong> {errorMessage}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
