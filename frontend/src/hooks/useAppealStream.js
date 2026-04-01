import { useCallback } from 'react'
import { useAppealStore } from '../store/appealStore'
import API_URL from '../lib/api.js'

export function useAppealStream() {
  const submit = useCallback(async (denialText, { skipAdminCheck = false } = {}) => {
    // Always read fresh state to avoid stale closure
    useAppealStore.getState().reset()
    useAppealStore.getState().setDenialText(denialText)
    // Set after reset so it persists — AgentTrace reads this to filter admin_error_checker
    if (skipAdminCheck) useAppealStore.getState().setSkipAdminCheck(true)

    let response
    try {
      response = await fetch(`${API_URL}/appeals/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          denial_text: denialText,
          patient_context: useAppealStore.getState().patientContext,
          skip_admin_check: skipAdminCheck,
          user_id: 'web-user',
        }),
      })
    } catch (err) {
      useAppealStore.getState().setError(`Network error: ${err.message}`)
      return
    }

    if (!response.ok) {
      useAppealStore.getState().setError(`Server error: ${response.status}`)
      return
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })

      // SSE events are delimited by \n\n — split on that boundary
      // so event: and data: lines are always processed together
      const blocks = buffer.split('\n\n')
      buffer = blocks.pop() // keep trailing incomplete block

      for (const block of blocks) {
        if (!block.trim()) continue

        let eventType = ''
        let dataStr = ''

        for (const line of block.split('\n')) {
          if (line.startsWith('event: ')) {
            eventType = line.slice(7).trim()
          } else if (line.startsWith('data: ')) {
            dataStr = line.slice(6).trim()
          }
        }

        if (!eventType || !dataStr) continue

        try {
          const data = JSON.parse(dataStr)
          const s = useAppealStore.getState()

          if (eventType === 'stream_started') {
            // Immediately show the running state — don't wait for
            // the first Gemini API call (~2s) to complete
            s.startNode('denial_reader')
          } else if (eventType === 'node_start') {
            s.startNode(data.node)
          } else if (eventType === 'node_done') {
            s.completeNode(data.node, data.data)
          } else if (eventType === 'done') {
            console.log('=== DONE PAYLOAD FIELDS ===')
            console.log('policy_chunks:', data.policy_chunks)
            console.log('payer_found:', data.payer_found)
            console.log('payer_not_found_message:', data.payer_not_found_message)
            console.log('all keys:', Object.keys(data))
            if (data.session_id) {
              window.sessionStorage.setItem('activeAppealSessionId', data.session_id)
            }
            s.setDone(data)
          } else if (eventType === 'error') {
            s.setError(data.message || 'Unknown error')
          }
        } catch (e) {
          console.error('SSE parse error:', e, 'raw:', dataStr.slice(0, 200))
        }
      }
    }
  }, [])

  return { submit }
}
