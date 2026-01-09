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
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={stats.appeals_by_payer} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <XAxis dataKey="payer" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="count" fill="#0d9488" radius={[4,4,0,0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Bar: Appeals by drug */}
        <div className={styles.chartCard}>
          <h3 className={styles.chartTitle}>Top Denied Drugs</h3>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart
              data={stats.appeals_by_drug.slice(0, 5)}
              layout="vertical"
              margin={{ top: 0, right: 20, left: 40, bottom: 0 }}
            >
              <XAxis type="number" tick={{ fontSize: 11 }} />
              <YAxis 
                type="category" 
                dataKey="drug_or_procedure" 
                tick={{ fontSize: 11 }} 
                width={140}
                tickFormatter={(val) => val && val.length > 22 ? val.substring(0, 22) + '...' : val}
              />
              <Tooltip />
              <Bar dataKey="count" fill="#2563eb" radius={[0,4,4,0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Line: Approval rate trend */}
        <div className={styles.chartCard}>
          <h3 className={styles.chartTitle}>Approval Rate Over Time</h3>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={stats.approval_trend} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
              <XAxis dataKey="week" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="appeals" stroke="#6b7280" strokeWidth={2} dot={false} name="Appeals" />
              <Line type="monotone" dataKey="approved" stroke="#059669" strokeWidth={2} dot={false} name="Approved" />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Pie: escalated vs auto-drafted */}
        <div className={styles.chartCard}>
          <h3 className={styles.chartTitle}>Auto-drafted vs Escalated</h3>
          <ResponsiveContainer width="100%" height={280}>
            <PieChart>
              <Pie
                data={pieData}
                cx="50%"
                cy="45%"
                innerRadius={55}
                outerRadius={80}
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
              <Legend verticalAlign="bottom" height={36} iconType="circle" wrapperStyle={{ fontSize: '12px' }} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}
