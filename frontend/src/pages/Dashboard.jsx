import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'

const colors = ['#14b8a6', '#6366f1', '#f59e0b', '#f43f5e', '#10b981', '#ec4899']

function CategoryPie({ title, items, currency }) {
  const total = items.reduce((sum, item) => sum + item.amount, 0)
  let offset = 0
  const segments = items.map((item, index) => {
    const start = offset
    offset += item.amount / total * 100
    return `${colors[index % colors.length]} ${start}% ${offset}%`
  })
  return <div className="pie-panel"><h4>{title}</h4>{total ? <>
    <div className="pie-chart" role="img" aria-label={`${title}: ${items.map(item => `${item.name} ${item.amount.toFixed(2)} ${currency}`).join(', ')}`} style={{ background: `conic-gradient(${segments.join(', ')})` }} />
    <ul className="pie-legend">{items.map((item, index) => <li key={item.name}><span className="pie-swatch" style={{ background: colors[index % colors.length] }} />{item.name}<strong>{item.amount.toFixed(2)} {currency}</strong></li>)}</ul>
  </> : <p className="muted">No {title.toLowerCase()} this month.</p>}</div>
}

function CashflowTable({ title, months }) {
  return <div className="card table-scroll"><h4>{title}</h4><table><thead><tr><th>Month</th><th>Income</th><th>Spending</th><th>Monthly total</th><th>General total · end balance</th></tr></thead><tbody>{months.map(row => {
    const monthly = row.income - row.spending
    return <tr key={row.month}><td>{row.month}</td><td>{row.income.toFixed(2)}</td><td>{row.spending.toFixed(2)}</td><td className={monthly >= 0 ? 'balance-positive' : 'balance-negative'}>{monthly.toFixed(2)}</td><td className={row.endBalance >= 0 ? 'balance-positive' : 'balance-negative'}><strong>{row.endBalance.toFixed(2)}</strong></td></tr>
  })}</tbody></table></div>
}

export default function Dashboard() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [view, setView] = useState('total')
  const [selectedAccounts, setSelectedAccounts] = useState({})
  const [overages, setOverages] = useState(null)
  const [overageError, setOverageError] = useState('')
  useEffect(() => {
    api('/dashboard/').then(setData).catch(e => setError(e.message))
    api('/overview/overages/').then(setOverages).catch(e => setOverageError(e.message))
  }, [])
  return <main className="container">
    <div className="page-heading"><div><p className="eyebrow">OVERVIEW</p><h2>Your spending outlook</h2></div></div>
    {error && <p className="error" role="alert">{error}</p>}
    {!data && !error && <p>Loading dashboard…</p>}
    {data && Object.keys(data.currencies).length === 0 && <div className="card empty">No accounts yet. <Link to="/account/new">Add an account →</Link></div>}
    {data && Object.entries(data.currencies).map(([currency, summary]) => <section key={currency} className="dashboard-section"><h3>{currency} · next {summary.months.length} months</h3>
      <div className="metric-grid">{[
        ['This month income', summary.months[0].income],
        ['This month expenses', summary.months[0].spending],
        ['This month total', summary.months[0].income - summary.months[0].spending],
        ['Average monthly income', summary.months.reduce((sum, row) => sum + row.income, 0) / summary.months.length],
        ['Average monthly expenses', summary.averageMonthlySpending],
        ['Average monthly total', summary.months.reduce((sum, row) => sum + row.income - row.spending, 0) / summary.months.length]
      ].map(([label, amount], index) => <div key={label} className={`card metric${index === 2 || index === 5 ? ' accent' : ''}`}><span>{label}</span><strong>{amount.toFixed(2)}</strong><small>{currency}</small></div>)}</div>
      <div className="card"><h3>Categories · this month</h3><div className="pie-grid"><CategoryPie title="Income" items={summary.categories.income} currency={currency}/><CategoryPie title="Expenses" items={summary.categories.expense} currency={currency}/></div></div>
      <label className="field dashboard-selector"><span>Show cashflow table</span><select value={view} onChange={event => setView(event.target.value)}><option value="account">Individual accounts</option><option value="group">Groups</option><option value="total">Total</option></select></label>
      {view === 'total' ? <CashflowTable title={`All accounts · ${currency}`} months={summary.months}/> : view === 'account' ? <><label className="field dashboard-selector">Individual account <select value={selectedAccounts[currency] ?? summary.accounts[0]?.id ?? ''} onChange={event => setSelectedAccounts(current => ({ ...current, [currency]: Number(event.target.value) }))}>{summary.accounts.map(account => <option key={account.id} value={account.id}>{account.name}</option>)}</select></label>{summary.accounts.filter(account => account.id === (selectedAccounts[currency] ?? summary.accounts[0]?.id)).map(account => <CashflowTable key={account.id} title={account.name} months={account.months}/>)}</> : summary.groups.length ? summary.groups.map(group => <CashflowTable key={group.id} title={group.name} months={group.months}/>) : <div className="card empty">No groups in {currency} yet. <Link to="/accountgroup/new">Create a group →</Link></div>}
    </section>)}
    <section className="card"><h3>Expenses above the stipulated monthly value</h3><p className="muted">Recorded expenses exceeding their average plus deviation.</p>
      {overageError && <p className="error" role="alert">{overageError}</p>}
      {!overages && !overageError && <p>Loading expense overages…</p>}
      {overages && (overages.length ? <div className="table-scroll"><table><thead><tr><th>Date</th><th>Expense</th><th>Account</th><th>Actual</th><th>Average + deviation</th></tr></thead><tbody>{overages.map(row => <tr key={`${row.id}-${row.date}`}><td>{row.date}</td><td><Link to={`/expense/${row.id}/edit`}>{row.description}</Link></td><td>#{row.account_id}</td><td className="balance-negative">{row.amount.toFixed(2)}</td><td>{row.expectedValue.toFixed(2)} + {row.allowedDeviation.toFixed(2)} = {row.limit.toFixed(2)}</td></tr>)}</tbody></table></div> : <p className="muted">No recorded expenses above their stipulated value.</p>)}
    </section>
    <p className="muted footnote">Projections use your opening balances and scheduled entries. Add accounts to a group to choose a consolidated cashflow view.</p>
  </main>
}
