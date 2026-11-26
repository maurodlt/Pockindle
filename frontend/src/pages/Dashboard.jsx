import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'

export default function Dashboard() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api('/dashboard/').then(setData).catch(e => setError(e.message)) }, [])
  return <main className="container"><section className="hero"><p className="eyebrow">A CLEARER PICTURE</p><h1>Feel at home with your money.</h1><p>See what you’ve spent, what’s coming, and where you’ll stand at the end of each month.</p><div className="hero-actions"><Link className="button" to="/expense/new">+ Add expense</Link><Link className="button secondary" to="/revenue/new">+ Add revenue</Link></div></section>
    <div className="page-heading"><div><p className="eyebrow">OVERVIEW</p><h2>Your spending outlook</h2></div></div>
    {error && <p className="error" role="alert">{error}</p>}
    {!data && !error && <p>Loading dashboard…</p>}
    {data && Object.keys(data.currencies).length === 0 && <div className="card empty">No accounts yet. <Link to="/account/new">Add an account →</Link></div>}
    {data && Object.entries(data.currencies).map(([currency, summary]) => <section key={currency} className="dashboard-section"><h3>{currency} · next {summary.months.length} months</h3>
      <div className="metric-grid"><div className="card metric"><span>This month’s spending</span><strong>{summary.currentMonthSpending.toFixed(2)}</strong><small>{currency}</small></div><div className="card metric"><span>Following months’ spending</span><strong>{summary.futureMonthSpending.toFixed(2)}</strong><small>{currency} · combined</small></div><div className="card metric accent"><span>Average monthly spending</span><strong>{summary.averageMonthlySpending.toFixed(2)}</strong><small>{currency} · projected period</small></div></div>
      <div className="card table-scroll"><table><thead><tr><th>Month</th><th>Revenue</th><th>Spending</th><th>End balance</th></tr></thead><tbody>{summary.months.map(row => <tr key={row.month}><td>{row.month}</td><td>{row.revenue.toFixed(2)}</td><td>{row.spending.toFixed(2)}</td><td><strong>{row.endBalance.toFixed(2)}</strong></td></tr>)}</tbody></table></div>
    </section>)}
    <p className="muted footnote">Projections use your opening balances and scheduled entries. Add accounts to a group to choose a consolidated cashflow view.</p>
  </main>
}
