import { useEffect, useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import styles from './AppLayout.module.css'

const NAV = [
  { to: '/appeal', icon: '◎', label: 'New Appeal' },
  { to: '/cases', icon: '≡', label: 'Cases' },
  { to: '/analytics', icon: '◈', label: 'Analytics' },
]

export default function AppLayout({ children }) {
  const location = useLocation()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [isMobile, setIsMobile] = useState(() => window.innerWidth < 768)

  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth < 768)
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  useEffect(() => {
    setSidebarOpen(false)
  }, [location.pathname])

  useEffect(() => {
    if (!isMobile) setSidebarOpen(false)
  }, [isMobile])

  const currentNav = NAV.find(item => item.to === location.pathname) || NAV[0]

  function renderNavItems() {
    return NAV.map(({ to, icon, label }) => (
      <NavLink
        key={to}
        to={to}
        className={({ isActive }) =>
          `${styles.navItem} ${isActive ? styles.navItemActive : ''}`
        }
      >
        <span className={styles.navIcon}>{icon}</span>
        <span>{label}</span>
      </NavLink>
    ))
  }

  return (
    <div className={styles.shell}>
      {isMobile && (
        <header className={styles.mobileHeader}>
          <button
            type="button"
            className={styles.menuButton}
            onClick={() => setSidebarOpen(true)}
            aria-label="Open navigation menu"
          >
            ☰
          </button>
          <div className={styles.mobileBrand}>
            <span className={styles.mobileBrandName}>PA Evidence Assistant</span>
            <span className={styles.mobileBrandSub}>{currentNav.label}</span>
          </div>
        </header>
      )}

      {isMobile && sidebarOpen && (
        <button
          type="button"
          className={styles.backdrop}
          onClick={() => setSidebarOpen(false)}
          aria-label="Close navigation menu"
        />
      )}

      <aside className={`${styles.sidebar} ${sidebarOpen ? styles.sidebarOpen : ''}`}>
        <div className={styles.brand}>
          <span className={styles.brandName}>PA Evidence Assistant</span>
          <span className={styles.brandSub}>Clinical evidence for PA appeals</span>
        </div>
        <nav className={styles.nav}>{renderNavItems()}</nav>
        <div className={styles.sidebarFooter}>
          <span className={styles.footerText}>HIPAA-compliant • Audit logged</span>
        </div>
      </aside>
      <main className={styles.main}>{children}</main>
      {isMobile && (
        <nav className={styles.mobileTabBar}>
          {renderNavItems()}
        </nav>
      )}
    </div>
  )
}
