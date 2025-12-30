import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'

export function usePageRefresh(fetchFn) {
  const location = useLocation()

  // Refetch when route changes back to this page
  useEffect(() => {
    fetchFn()
  }, [location.pathname, fetchFn])

  // Refetch when tab becomes visible again
  useEffect(() => {
    const handleVisibility = () => {
      if (document.visibilityState === 'visible') {
        fetchFn()
      }
    }
    document.addEventListener('visibilitychange', handleVisibility)
    return () => document.removeEventListener(
      'visibilitychange', handleVisibility
    )
  }, [fetchFn])

  // Refetch when window regains focus
  useEffect(() => {
    const handleFocus = () => fetchFn()
    window.addEventListener('focus', handleFocus)
    return () => window.removeEventListener('focus', handleFocus)
  }, [fetchFn])
}
