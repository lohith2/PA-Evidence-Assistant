import { useEffect, useState, useCallback } from 'react'
import { usePageRefresh } from '../hooks/usePageRefresh'
import API_URL from '../lib/api.js'
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import styles from './AnalyticsPage.module.css'

const COLORS = ['#0d9488', '#2563eb', '#d97706', '#dc2626', '#7c3aed', '#059669']

function StatCard({ label, value, sub }) {
  return (
    <div className={styles.statCard}>
      <div className={styles.statValue}>{value}</div>
      <div className={styles.statLabel}>{label}</div>
      {sub && <div className={styles.statSub}>{sub}</div>}
    </div>
  )
}

export default function AnalyticsPage() {
  const [stats, setStats] = useState(null)
  const [isMobile, setIsMobile] = useState(() => window.innerWidth < 768)

  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth < 768)
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  const fetchStats = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/stats`)
      const data = await res.json()
      setStats(data)
    } catch {}
  }, [])

  usePageRefresh(fetchStats)

  if (!stats) {
    return (
      <div className={styles.page}>
        <h1 className={styles.title}>Appeal Outcomes</h1>
        <div className={styles.loading}>Loading analytics…</div>
      </div>
    )
  }

  const pieData = [
    { name: 'Auto-drafted', value: stats.total_appeals - stats.escalated_count },
    { name: 'Escalated', value: stats.escalated_count },
  ]

  return (
    <div className={styles.page}>
      <h1 className={styles.title}>Appeal Outcomes</h1>
      <p className={styles.subtitle}>Appeal outcomes and agent performance</p>

      <div className={styles.statGrid}>
        <StatCard
          label="Total Appeals Generated"
          value={stats.total_appeals.toLocaleString()}
        />
        <StatCard
          label="Avg Confidence Score"
          value={`${stats.avg_confidence}%`}
          sub="Evidence strength"
        />
        <StatCard
          label="Approval Rate"
          value={`${stats.approval_rate}%`}
          sub={`${stats.approved_count} of ${stats.submitted_count} submitted`}
        />
        <StatCard
          label="Physician Hours Saved"
          value={`${stats.time_saved_hours.toLocaleString()}h`}
          sub="At 2.5h per appeal"
        />
      </div>

      <div className={styles.charts}>
        {/* Bar: Appeals by payer */}
        <div className={styles.chartCard}>
          <h3 className={styles.chartTitle}>Appeals by Payer</h3>
          <ResponsiveContainer width="100%" height={isMobile ? 200 : 220}>
            <BarChart data={stats.appeals_by_payer} margin={{ top: 0, right: 0, left: isMobile ? -30 : -20, bottom: 0 }}>
              <XAxis
                dataKey="payer"
                tick={{ fontSize: 11 }}
                interval={0}
                tickFormatter={(val) => {
                  if (!val) return ''
                  return isMobile && val.length > 8 ? `${val.slice(0, 8)}...` : val
                }}
              />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="count" fill="#0d9488" radius={[4,4,0,0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Bar: Appeals by drug */}
        <div className={styles.chartCard}>
          <h3 className={styles.chartTitle}>Top Denied Drugs</h3>
          <ResponsiveContainer width="100%" height={isMobile ? 220 : 280}>
            <BarChart
              data={stats.appeals_by_drug.slice(0, 5)}
              layout="vertical"
              margin={{ top: 0, right: isMobile ? 8 : 20, left: isMobile ? 8 : 40, bottom: 0 }}
            >
              <XAxis type="number" tick={{ fontSize: 11 }} />
              <YAxis 
                type="category" 
                dataKey="drug_or_procedure" 
                tick={{ fontSize: 11 }} 
                width={isMobile ? 84 : 140}
                tickFormatter={(val) => {
                  const max = isMobile ? 10 : 22
                  return val && val.length > max ? val.substring(0, max) + '...' : val
                }}
              />
              <Tooltip />
              <Bar dataKey="count" fill="#2563eb" radius={[0,4,4,0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Line: Approval rate trend */}
        <div className={styles.chartCard}>
          <h3 className={styles.chartTitle}>Approval Rate Over Time</h3>
          <ResponsiveContainer width="100%" height={isMobile ? 220 : 220}>
            <LineChart data={stats.approval_trend} margin={{ top: 5, right: 10, left: isMobile ? -28 : -20, bottom: 0 }}>
              <XAxis dataKey="week" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Legend wrapperStyle={{ fontSize: '12px' }} />
              <Line type="monotone" dataKey="appeals" stroke="#6b7280" strokeWidth={2} dot={false} name="Appeals" />
              <Line type="monotone" dataKey="approved" stroke="#059669" strokeWidth={2} dot={false} name="Approved" />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Pie: escalated vs auto-drafted */}
        <div className={styles.chartCard}>
          <h3 className={styles.chartTitle}>Auto-drafted vs Escalated</h3>
          <ResponsiveContainer width="100%" height={isMobile ? 240 : 280}>
            <PieChart>
              <Pie
                data={pieData}
                cx="50%"
                cy={isMobile ? '42%' : '45%'}
                innerRadius={isMobile ? 42 : 55}
                outerRadius={isMobile ? 62 : 80}
                paddingAngle={3}
                dataKey="value"
                label={({ percent }) => `${Math.round(percent * 100)}%`}
                labelLine={false}
              >
                {pieData.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
              <Legend verticalAlign="bottom" height={isMobile ? 52 : 36} iconType="circle" wrapperStyle={{ fontSize: '12px' }} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}
