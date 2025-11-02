import { NavLink } from 'react-router-dom'
import styles from './AppLayout.module.css'

const NAV = [
  { to: '/appeal', icon: '◎', label: 'New Appeal' },
  { to: '/cases', icon: '≡', label: 'Case History' },
  { to: '/analytics', icon: '◈', label: 'Analytics' },
]

export default function AppLayout({ children }) {
  return (
    <div className={styles.shell}>
      <aside className={styles.sidebar}>
        <div className={styles.brand}>
          <span className={styles.brandName}>PA Evidence Assistant</span>
          <span className={styles.brandSub}>Clinical evidence for PA appeals</span>
        </div>
        <nav className={styles.nav}>
          {NAV.map(({ to, icon, label }) => (
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
          ))}
        </nav>
        <div className={styles.sidebarFooter}>
          <span className={styles.footerText}>HIPAA-compliant • Audit logged</span>
        </div>
      </aside>
      <main className={styles.main}>{children}</main>
    </div>
  )
}
