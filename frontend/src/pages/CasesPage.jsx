import { useState, useEffect, useCallback } from 'react'
import { usePageRefresh } from '../hooks/usePageRefresh'
import CaseDetailDrawer from '../components/appeal/CaseDetailDrawer'
import API_URL from '../lib/api.js'
import styles from './CasesPage.module.css'

const STATUS_TABS = ['all', 'draft', 'submitted', 'approved', 'denied']

export default function CasesPage() {
  const [cases, setCases] = useState([])
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState('all')
  const [search, setSearch] = useState('')
  const [pendingOutcome, setPendingOutcome] = useState({}) // {sessionId: 'approved'|'denied'}
  const [selectedCase, setSelectedCase] = useState(null)

  const fetchCases = useCallback(async () => {
    setLoading(true)
    const params = new URLSearchParams()
    if (tab !== 'all') params.set('status', tab)
    if (search) params.set('search', search)
    try {
      const resp = await fetch(`${API_URL}/cases/?${params}`)
      if (resp.ok) {
        const data = await resp.json()
        setCases(data.cases || [])
      }
    } catch {
      setCases([])
    } finally {
      setLoading(false)
    }
  }, [tab, search])

  usePageRefresh(fetchCases)

  useEffect(() => {
    fetchCases()
  }, [fetchCases])

  async function markOutcome(sessionId, outcome) {
    setPendingOutcome(p => ({ ...p, [sessionId]: outcome }))
    await fetch(`${API_URL}/cases/${sessionId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ outcome, status: outcome }),
    })
    setPendingOutcome(p => { const n = { ...p }; delete n[sessionId]; return n })
    fetchCases()
  }

  const handleStatusChange = (id, newStatus) => {
    markOutcome(id, newStatus)
    setSelectedCase(prev => ({...prev, status: newStatus, outcome: newStatus}))
  }

  // Compute approval rate from current case list
  const allForStats = cases
  const submitted = allForStats.filter(c => ['submitted','approved','denied'].includes(c.status))
  const approved  = allForStats.filter(c => c.outcome === 'approved')
  const approvalRate = submitted.length > 0
    ? Math.round((approved.length / submitted.length) * 100)
    : null

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <h1 className={styles.title}>Appeal Cases</h1>
          {approvalRate !== null && (
            <p className={styles.subtitle}>
              {approved.length} of {submitted.length} submitted appeals overturned ({approvalRate}%)
            </p>
          )}
        </div>
      </div>

      <div className={styles.controls}>
        <div className={styles.tabs}>
          {STATUS_TABS.map(t => (
            <button
              key={t}
              className={`${styles.tab} ${tab === t ? styles.tabActive : ''}`}
              onClick={() => setTab(t)}
            >
              {t.charAt(0).toUpperCase() + t.slice(1)}
            </button>
          ))}
        </div>
        <input
          className={styles.search}
          placeholder="Search by drug or payer…"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
      </div>

      {cases.length === 0 && !loading ? (
        <div className={styles.empty}>
          <div className={styles.emptyIcon}>◎</div>
          <p className={styles.emptyTitle}>No appeals yet</p>
          <p className={styles.emptySubtitle}>Paste a denial letter to get started.</p>
        </div>
      ) : (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Date</th>
                <th>Drug / Procedure</th>
                <th>Payer</th>
                <th>Confidence</th>
                <th>Status</th>
                <th>Outcome</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {loading
                ? Array.from({ length: 5 }).map((_, i) => (
                    <tr key={i} className={styles.skeletonRow}>
                      {Array.from({ length: 7 }).map((_, j) => (
                        <td key={j}><div className={`skeleton ${styles.skeletonCell}`} /></td>
                      ))}
                    </tr>
                  ))
                : cases.map(c => (
                  <tr key={c.session_id} className={styles.row}>
                    <td className={styles.mono}>
                      {c.created_at
                        ? new Date(c.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
                        : '—'}
                    </td>
                    <td className={styles.drug}>{c.drug_or_procedure || '—'}</td>
                    <td>{c.payer || '—'}</td>
                    <td>
                      {c.confidence_score != null ? (
                        <span className={`${styles.confidence} ${
                          c.confidence_score >= 75 ? styles.confHigh
                          : c.confidence_score >= 50 ? styles.confMed
                          : styles.confLow
                        }`}>
                          {c.confidence_score}%
                        </span>
                      ) : '—'}
                    </td>
                    <td>
                      <span className={`${styles.badge} ${styles['badge_' + c.status] || styles.badge_draft}`}>
                        {c.status || 'draft'}
                      </span>
                    </td>
                    <td>
                      {c.outcome ? (
                        <span className={`${styles.badge} ${styles['badge_' + c.outcome] || ''}`}>
                          {c.outcome}
                        </span>
                      ) : c.status === 'submitted' ? (
                        <div className={styles.outcomeButtons}>
                          <button
                            className={styles.approveBtn}
                            onClick={() => markOutcome(c.session_id, 'approved')}
                            disabled={!!pendingOutcome[c.session_id]}
                          >
                            {pendingOutcome[c.session_id] === 'approved' ? '…' : 'Mark approved'}
                          </button>
                          <button
                            className={styles.denyBtn}
                            onClick={() => markOutcome(c.session_id, 'denied')}
                            disabled={!!pendingOutcome[c.session_id]}
                          >
                            {pendingOutcome[c.session_id] === 'denied' ? '…' : 'Mark denied'}
                          </button>
                        </div>
                      ) : '—'}
                    </td>
                    <td>
                      <button 
                        className={styles.viewLink} 
                        style={{ border: 'none', background: 'transparent', cursor: 'pointer', padding: 0 }}
                        onClick={() => setSelectedCase(c)}
                      >
                        View →
                      </button>
                    </td>
                  </tr>
                ))
              }
            </tbody>
          </table>
        </div>
      )}

      {selectedCase && (
        <CaseDetailDrawer
          caseData={selectedCase}
          onClose={() => setSelectedCase(null)}
          onStatusChange={handleStatusChange}
        />
      )}
    </div>
  )
}
