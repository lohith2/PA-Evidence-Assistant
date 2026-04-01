import { create } from 'zustand'

const NODE_ORDER = [
  'denial_reader',
  'admin_error_checker',
  'policy_retriever',
  'evidence_retriever',
  'contradiction_finder',
  'appeal_drafter',
  'escalation_node',
  'quality_checker',
]

const NODE_LABELS = {
  denial_reader: 'Reading denial letter',
  admin_error_checker: 'Checking for administrative errors',
  policy_retriever: 'Retrieving payer policy',
  evidence_retriever: 'Searching clinical guidelines',
  contradiction_finder: 'Analyzing evidence vs policy',
  appeal_drafter: 'Drafting appeal letter',
  escalation_node: 'Generating escalation notice',
  quality_checker: 'Checking letter quality',
}

function makeInitialTrace() {
  return NODE_ORDER.map(node => ({
    node,
    label: NODE_LABELS[node],
    status: 'pending',
    data: null,
  }))
}

export const useAppealStore = create((set) => ({
  // Session
  denialText: '',
  patientContext: '',
  sessionId: null,
  status: 'idle',       // idle | running | done | error
  nodeTrace: makeInitialTrace(),

  // Results
  appealLetter: '',
  citations: [],
  evidenceItems: [],
  policyChunks: [],
  payerFound: true,
  payerNotFoundMessage: '',
  confidenceScore: null,
  qualityScore: null,
  qualityIssues: [],
  escalated: false,
  escalationReason: '',
  missingEvidence: [],
  denialInfo: null,
  contradictions: [],
  activeEvidenceSource: null,

  // Submit workflow
  isSubmitted: false,
  isSubmitting: false,

  // Admin error
  adminError: false,
  adminErrorType: '',
  adminExplanation: '',
  adminSuggestion: '',
  adminCorrectCode: '',

  // Correction flow (not cleared on reset — must survive pipeline restart)
  correctionApplied: false,
  correctionNote: '',
  skipAdminCheck: false,

  // History view
  loadedFromHistory: false,

  // Error
  errorMessage: '',

  setDenialText: (text) => set({ denialText: text }),
  setPatientContext: (text) => set({ patientContext: text }),

  reset: () => set({
    sessionId: null,
    status: 'idle',
    nodeTrace: makeInitialTrace(),
    appealLetter: '',
    citations: [],
    evidenceItems: [],
    policyChunks: [],
    payerFound: true,
    payerNotFoundMessage: '',
    confidenceScore: null,
    qualityScore: null,
    qualityIssues: [],
    escalated: false,
    escalationReason: '',
    missingEvidence: [],
    denialInfo: null,
    contradictions: [],
    errorMessage: '',
    activeEvidenceSource: null,
    isSubmitted: false,
    isSubmitting: false,
    adminError: false,
    adminErrorType: '',
    adminExplanation: '',
    adminSuggestion: '',
    adminCorrectCode: '',
    loadedFromHistory: false,
  }),

  startNode: (node) => set(state => ({
    status: 'running',
    nodeTrace: state.nodeTrace.map(n =>
      n.node === node ? { ...n, status: 'running' } : n
    ),
  })),

  // Extract intermediate evidence data from specific nodes as they complete
  completeNode: (node, data) => set(state => {
    const patch = {
      nodeTrace: state.nodeTrace.map(n =>
        n.node === node ? { ...n, status: 'done', data } : n
      ),
    }
    // Surface evidence as soon as retrieval nodes complete
    if (node === 'policy_retriever') {
      const hasPolicyChunks = Array.isArray(data?.policy_chunks) && data.policy_chunks.length > 0
      if (hasPolicyChunks) {
        patch.policyChunks = data.policy_chunks
        patch.payerFound = true
        patch.payerNotFoundMessage = ''
      } else if (data?.payer_found !== undefined) {
        patch.payerFound = data.payer_found
        patch.payerNotFoundMessage = data.payer_not_found_message || ''
      } else if (Array.isArray(data?.policy_chunks)) {
        patch.policyChunks = []
      }
    }
    if (node === 'evidence_retriever' && data?.items?.length) {
      patch.evidenceItems = data.items
    }
    return patch
  }),

  setDone: (payload) => {
    set(() => {
      const hasPolicyChunks = Array.isArray(payload.policy_chunks) && payload.policy_chunks.length > 0

      return {
        status: 'done',
        sessionId: payload.session_id,
        appealLetter: payload.appeal_letter || '',
        citations: payload.citations || [],
        // Always overwrite evidenceItems from done payload — it reflects the final
        // state after contradiction_finder has written contradicts_denial=True back
        // to items.
        ...(payload.evidence_items?.length
          ? { evidenceItems: payload.evidence_items }
          : {}),
        ...(Array.isArray(payload.policy_chunks)
          ? { policyChunks: payload.policy_chunks }
          : {}),
        ...(hasPolicyChunks
          ? { payerFound: true, payerNotFoundMessage: '' }
          : payload.payer_found !== undefined
            ? { payerFound: payload.payer_found, payerNotFoundMessage: payload.payer_not_found_message || '' }
            : {}),
        confidenceScore: payload.confidence_score,
        qualityScore: payload.quality_score,
        qualityIssues: payload.quality_issues || [],
        escalated: payload.escalated || false,
        escalationReason: payload.escalation_reason || '',
        missingEvidence: payload.missing_evidence || [],
        denialInfo: payload.denial_info,
        contradictions: payload.contradictions || [],
        adminError: payload.admin_error || false,
        adminErrorType: payload.admin_error_type || '',
        adminExplanation: payload.admin_explanation || '',
        adminSuggestion: payload.admin_suggestion || '',
        adminCorrectCode: payload.admin_correct_code || '',
      }
    })
  },

  setError: (msg) => set({ status: 'error', errorMessage: msg }),

  setSubmitting: () => set({ isSubmitting: true }),
  setSubmitted: () => set({ isSubmitting: false, isSubmitted: true }),
  setSubmitError: () => set({ isSubmitting: false }),

  setActiveEvidenceSource: (source) => set({ activeEvidenceSource: source }),

  setCorrectionApplied: (note) => set({ correctionApplied: true, correctionNote: note }),
  clearCorrection: () => set({ correctionApplied: false, correctionNote: '', skipAdminCheck: false }),
  setSkipAdminCheck: (val) => set({ skipAdminCheck: val }),

  // Hydrate store from a saved case (history view)
  setLoaded: (c) => {
    const rawItems = c.evidence_items || []
    const policyChunks = rawItems.filter(i => (i.source || '').toUpperCase() === 'PAYER')
    const evidenceItems = rawItems.filter(i => (i.source || '').toUpperCase() !== 'PAYER')

    return set({
      status: 'done',
      sessionId: c.session_id,
      denialText: c.raw_denial_text || '',
      appealLetter: c.appeal_letter || '',
      citations: c.citations || [],
      evidenceItems,
      policyChunks,
      payerFound: policyChunks.length > 0,
      confidenceScore: c.confidence_score ?? null,
      qualityScore: c.quality_score ?? null,
      qualityIssues: [],
      escalated: c.escalated || false,
      escalationReason: c.escalation_reason || '',
      denialInfo: {
        drug_or_procedure: c.drug_or_procedure,
        payer: c.payer,
        denial_reason: c.denial_reason,
        policy_code: c.policy_code,
        patient_id: null,
        claim_id: null,
      },
      isSubmitted: ['submitted', 'approved', 'denied'].includes(c.status),
      loadedFromHistory: true,
      nodeTrace: NODE_ORDER.map(node => ({
        node,
        label: NODE_LABELS[node],
        status: 'done',
        data: null,
      })),
    })
  },
}))
