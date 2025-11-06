import { useAppealStore } from '../../store/appealStore'
import styles from './AgentTrace.module.css'

function NodeRow({ node, label, status, data }) {
  const isRunning = status === 'running'
  const isDone = status === 'done'

  function renderMeta() {
    if (!data) return null
    const parts = []
    if (data.drug) parts.push(`Drug: ${data.drug}`)
    if (data.payer) parts.push(`Payer: ${data.payer}`)
    if (data.policy_code) parts.push(`Policy: ${data.policy_code}`)
    if (data.chunks_found != null) parts.push(`${data.chunks_found} policy sections retrieved`)
    if (data.evidence_label != null) parts.push(data.evidence_label)
    else if (data.evidence_found != null) parts.push(`${data.evidence_found} evidence items retrieved`)
    if (data.confidence != null) parts.push(`Confidence: ${data.confidence}%`)
    if (data.viable != null) parts.push(data.viable ? 'viable' : 'escalating')
    if (data.letter_length != null) parts.push(`${data.letter_length} words drafted`)
    if (data.quality_score != null) parts.push(`Quality: ${data.quality_score}%`)
    if (data.issues != null && data.issues > 0) parts.push(`${data.issues} issues found`)
    return parts.join(' · ')
  }

  return (
    <div className={`${styles.row} ${styles[status]}`}>
      <div className={styles.dot}>
        {isDone && <span className={styles.dotDone}>●</span>}
        {isRunning && <span className={styles.dotRunning}>◉</span>}
        {status === 'pending' && <span className={styles.dotPending}>○</span>}
      </div>
      <div className={styles.content}>
        <div className={styles.nodeName}>
          {label}
          {isRunning && <span className={styles.pulsingLabel}> · Running...</span>}
        </div>
        {isDone && data && (
          <div className={styles.meta}>{renderMeta()}</div>
        )}
      </div>
      <div className={styles.status}>
        {isDone && <span className={styles.checkmark}>✓</span>}
        {isRunning && <span className={styles.loader} />}
        {status === 'pending' && <span className={styles.dash}>—</span>}
      </div>
    </div>
  )
}

export default function AgentTrace() {
  const { nodeTrace, status, skipAdminCheck } = useAppealStore()

  if (status === 'idle') return null

  const visibleTrace = skipAdminCheck
    ? nodeTrace.filter(n => n.node !== 'admin_error_checker')
    : nodeTrace

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <span className={styles.headerTitle}>Agent Pipeline</span>
        {status === 'done' && <span className={styles.badge}>Complete</span>}
        {status === 'escalated' && <span className={`${styles.badge} ${styles.badgeWarn}`}>Escalated</span>}
        {status === 'running' && <span className={`${styles.badge} ${styles.badgeRunning}`}>Running</span>}
      </div>
      <div className={styles.rows}>
        {visibleTrace.map(n => (
          <NodeRow key={n.node} {...n} />
        ))}
      </div>
    </div>
  )
}
