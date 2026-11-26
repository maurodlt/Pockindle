import React, { useEffect, useId, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'

const colors = ['#14b8a6', '#6366f1', '#f59e0b', '#f43f5e', '#10b981', '#ec4899']

function CategoryPie({ title, items, currency, month }) {
  const [active, setActive] = useState(null)
  const total = items.reduce((sum, item) => sum + item.amount, 0)
  let offset = 0
  const segments = items.map((item, index) => {
    const start = offset
    offset += item.amount / total * 100
    return { ...item, start, end: offset, color: colors[index % colors.length] }
  })
  const label = item => `${month} · ${item.name}: ${money(item.amount, currency)}`
  return <div className="pie-panel"><h4>{title}</h4>{total ? <>
    <div className="pie-interactive"><div className="pie-chart" role="img" tabIndex="0" aria-label={`${title} categories for ${month}: ${segments.map(label).join(', ')}`} style={{ background: `conic-gradient(${segments.map(item => `${item.color} ${item.start}% ${item.end}%`).join(', ')})` }} onMouseMove={event => { const bounds = event.currentTarget.getBoundingClientRect(); const x = event.clientX - bounds.left - bounds.width / 2; const y = event.clientY - bounds.top - bounds.height / 2; const angle = (Math.atan2(x, -y) * 180 / Math.PI + 360) % 360 / 3.6; setActive(segments.findIndex(item => angle >= item.start && angle < item.end)) }} onMouseLeave={() => setActive(null)} onBlur={() => setActive(null)} />{active !== null && active >= 0 && <span className="pie-tooltip" role="status">{label(segments[active])}</span>}</div>
    <ul className="pie-legend">{segments.map((item, index) => <li key={`${item.name}-${index}`} tabIndex="0" onMouseEnter={() => setActive(index)} onMouseLeave={() => setActive(null)} onFocus={() => setActive(index)} onBlur={() => setActive(null)} title={label(item)}><span className="pie-swatch" style={{ background: item.color }} />{item.name}<strong>{item.amount.toFixed(2)} {currency}</strong></li>)}</ul>
  </> : <p className="muted">No {title.toLowerCase()} this month.</p>}</div>
}

const money = (value, currency) => `${Number(value || 0).toFixed(2)} ${currency}`

function Trend({ values, dates, label, low = false, unit = '' }) {
  const [active, setActive] = useState(null)
  const tooltipId = useId()
  if (!values?.length) return null
  const minimum = Math.min(...values), span = Math.max(...values) - minimum || 1
  const coordinates = values.map((value, index) => ({
    x: 12 + index * 276 / Math.max(1, values.length - 1),
    y: 75 - (value - minimum) / span * 62
  }))
  const lowest = values.indexOf(minimum)
  const pointLabel = index => `${dates[index]}: ${Number(values[index]).toFixed(2)}${unit}`
  return <div className="trend-wrap" onMouseLeave={() => setActive(null)}>
    <svg className="trend" viewBox="0 0 300 90" role="img" aria-label={`${label}: ${values.map((_, index) => pointLabel(index)).join(', ')}`} aria-describedby={active === null ? undefined : tooltipId}>
      <polyline points={coordinates.map(point => `${point.x},${point.y}`).join(' ')} fill="none" stroke="#0d9b87" strokeWidth="3" strokeLinejoin="round" />
      {coordinates.map((point, index) => <circle key={`${dates[index]}-${index}`} className="trend-point" cx={point.x} cy={point.y} r="10" fill="transparent" stroke="transparent" tabIndex="0" aria-label={pointLabel(index)} onMouseEnter={() => setActive(index)} onFocus={() => setActive(index)} onBlur={() => setActive(null)}><title>{pointLabel(index)}</title></circle>)}
      {low && <circle cx={coordinates[lowest].x} cy={coordinates[lowest].y} r="5" fill="#f43f5e" pointerEvents="none" />}
    </svg>
    {active !== null && <span id={tooltipId} className="trend-tooltip" role="status" style={{ left: `${coordinates[active].x / 300 * 100}%` }}>{pointLabel(active)}</span>}
  </div>
}

function Progress({ label, value, total, currency }) {
  const overPlan = label === 'Expenses so far vs planned' && value > total
  return <div className={`progress-row${overPlan ? ' progress-over' : ''}`}><div><strong>{label}</strong><span>{money(value, currency)} / {money(total, currency)}</span></div><progress value={Math.min(Math.max(value, 0), Math.max(total, 1))} max={Math.max(total, 1)} /><small>{total ? (value / total * 100).toFixed(0) : '0'}% of plan</small></div>
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
    {data && Object.entries(data.currencies).map(([currency, summary]) => <section key={currency} className="dashboard-section">
      <h3>Where am I now · {currency}</h3>
      <div className="dashboard-grid"><div className="card"><h4>Current balance · net worth</h4><strong className="big-number">{money(summary.todayBalance, currency)}</strong><p className={summary.changeSinceLastMonth >= 0 ? 'balance-positive' : 'balance-negative'}>Since last month: {summary.changeSinceLastMonth >= 0 ? '+' : ''}{money(summary.changeSinceLastMonth, currency)}</p><Trend values={summary.balanceTrend} dates={summary.balanceTrendDates} unit={` ${currency}`} label="Balance over six months" /></div>
        <div className="card"><h4>Account balances today</h4>{summary.accounts.map(account => <div className="account-trend" key={account.id}><Link to={`/account/${account.id}/edit`}>{account.name}</Link><strong className={account.todayBalance < 0 ? 'status-red' : undefined}>{money(account.todayBalance, currency)}</strong><Trend values={account.balanceTrend} dates={summary.balanceTrendDates} unit={` ${currency}`} label={`${account.name} six-month balance trend`} /></div>)}</div></div>
      <div className="card"><h4>This month so far</h4><div className="dashboard-grid"><Progress label="Income received vs expected" value={summary.monthToDate.incomeReceived} total={summary.monthToDate.incomeExpected} currency={currency}/><Progress label="Expenses so far vs planned" value={summary.monthToDate.expensesSpent} total={summary.monthToDate.expensesPlanned} currency={currency}/></div><p className={`key-figure${summary.monthToDate.leftToSpend < 0 ? ' status-red' : summary.monthToDate.leftToSpend < summary.monthToDate.monthlyIncome * 0.1 ? ' status-yellow' : ''}`}>Left to spend this month: <strong>{money(summary.monthToDate.leftToSpend, currency)}</strong></p></div>
      <div className="card"><h3>Categories · this month</h3><div className="pie-grid"><CategoryPie title="Income" items={summary.categories.income} currency={currency} month={data.asOf.slice(0, 7)}/><CategoryPie title="Expenses" items={summary.categories.expense} currency={currency} month={data.asOf.slice(0, 7)}/></div></div>
      <h3>What needs attention</h3>
      <div className="dashboard-grid"><div className="card"><h4>Missing monthly amounts</h4><strong className={`big-number ${summary.missingAmounts.length > 0 ? 'status-yellow' : 'status-green'}`}>{summary.missingAmounts.length}</strong><p>Variable entries need this month’s amount.</p>{['income', 'expense'].map(kind => { const count = summary.missingAmounts.filter(row => row.kind === kind).length; return count ? <p key={kind}><Link to={`/${kind}`}>{count} {kind} {count === 1 ? 'entry' : 'entries'} need an amount →</Link></p> : null })}{!summary.missingAmounts.length && <p className="muted">All amounts are up to date.</p>}</div>
        <div className="card"><h4>First low-balance warning</h4>{summary.lowBalance ? <><p className="status-red"><strong>{summary.lowBalance.name}</strong> reaches {money(summary.lowBalance.balance, currency)} in {summary.lowBalance.month}.</p>{summary.lowBalance.transferFrom && <p>Consider a transfer from {summary.lowBalance.transferFrom}. <Link to="/transfer">View transfers →</Link></p>}</> : <p className="muted">No account or group projected below zero.</p>}</div></div>
      <div className="dashboard-grid"><div className="card"><h4>Coming up in the next 14 days</h4>{summary.timeline.length ? <ul className="dashboard-list">{summary.timeline.map((item, index) => <li key={`${item.date}-${item.account_id}-${index}`}><span>{item.date} · {item.description} ({item.account})</span><strong>{item.kind === 'expense' ? '−' : '+'}{money(item.amount, currency)}</strong>{item.kind === 'expense' && <small className={item.canCover ? 'balance-positive' : 'balance-negative'}>{item.canCover ? 'Covered' : 'Account may not cover this bill'}</small>}</li>)}</ul> : <p className="muted">No bills or income due in the next 14 days.</p>}</div>
        <div className="card"><h4>Off-plan entries this month</h4><strong className={`big-number ${summary.offPlan.count > 0 ? 'status-red' : 'status-green'}`}>{summary.offPlan.count}</strong>{summary.offPlan.worst ? <p>Worst: {summary.offPlan.worst.description} ({summary.offPlan.worst.kind}), {money(summary.offPlan.worst.difference, currency)} {summary.offPlan.worst.kind === 'income' ? 'below minimum' : 'above limit'}.</p> : <p className="muted">Nothing recorded outside its expected range.</p>}</div></div>
      <h3>Where the money goes</h3>
      <div className="dashboard-grid"><div className="card"><h4>Fixed vs variable vs extraordinary</h4><div className="stacked-bar" role="img" aria-label="Spending by type">{Object.entries(summary.spendingTypes).map(([kind, amount]) => <span key={kind} className={`stack-${kind}`} tabIndex="0" role="img" aria-label={`${data.asOf.slice(0, 7)} · ${kind}: ${money(amount, currency)}`} style={{ width: `${summary.monthToDate.expensesPlanned ? amount / summary.monthToDate.expensesPlanned * 100 : 0}%` }} title={`${data.asOf.slice(0, 7)} · ${kind}: ${money(amount, currency)}`} />)}</div><p>{Object.entries(summary.spendingTypes).map(([kind, amount]) => `${kind}: ${money(amount, currency)}`).join(' · ')}</p><strong>{summary.monthToDate.monthlyIncomeExpected ? (summary.monthToDate.fixedCosts / summary.monthToDate.monthlyIncomeExpected * 100).toFixed(0) : '—'}% of expected income committed to fixed costs</strong></div>
        <div className="card"><h4>Category vs usual · previous six months</h4>{summary.categoryComparison.length ? <ul className="dashboard-list">{summary.categoryComparison.map(item => <li key={item.name}><span>{item.name}</span><strong>{money(item.current, currency)}</strong><small>Usual {money(item.average, currency)} · {item.average ? `${item.current >= item.average ? '+' : ''}${((item.current - item.average) / item.average * 100).toFixed(0)}%` : 'No prior spending'}</small></li>)}</ul> : <p className="muted">No category spending this month.</p>}</div></div>
      <div className="dashboard-grid"><div className="card"><h4>Recurring costs per year</h4>{summary.recurringCosts.length ? <ul className="dashboard-list">{summary.recurringCosts.map((item, index) => <li key={index}><span>{item.description}</span><strong>{money(item.yearly, currency)}/year</strong><small>{money(item.monthly, currency)}/month</small></li>)}</ul> : <p className="muted">No recurring expenses.</p>}</div><div className="card"><h4>Ending soon · next three months</h4>{summary.endingSoon.length ? <ul className="dashboard-list">{summary.endingSoon.map((item, index) => <li key={index}><span>{item.description} · {item.endDate}</span><strong>{item.monthlyChange >= 0 ? '+' : ''}{money(item.monthlyChange, currency)}/month</strong></li>)}</ul> : <p className="muted">No entries ending soon.</p>}</div></div>
      <h3>The future</h3>
      <div className="card"><h4>Projected end balance</h4><Trend values={summary.months.map(row => row.endBalance)} dates={summary.months.map(row => row.month)} unit={` ${currency}`} label="Projected monthly end balances" low/><p>Lowest: {money(Math.min(...summary.months.map(row => row.endBalance)), currency)} in {summary.months.reduce((lowest, row) => row.endBalance < lowest.endBalance ? row : lowest).month}</p></div>
      <div className="dashboard-grid"><div className="card"><h4>Monthly savings rate</h4><Trend values={summary.savingsRates.map(row => row.rate ?? 0)} dates={summary.savingsRates.map(row => row.month)} unit="%" label="Monthly savings rate percentage"/><ul className="dashboard-list">{summary.savingsRates.map(row => <li key={row.month}><span>{row.month}</span><strong>{row.rate === null ? '— (no income)' : `${row.rate.toFixed(1)}%`}</strong></li>)}</ul></div><div className="card"><h4>Emergency cover</h4><strong className={`big-number ${Number(summary.emergencyCover) < 3 ? 'status-red' : Number(summary.emergencyCover) < 6 ? 'status-yellow' : 'status-green'}`}>{`${Number(summary.emergencyCover ?? 0).toFixed(1)} months`}</strong><p className="muted">Today’s balance divided by average monthly fixed and variable expenses (using upcoming months when there is no history).</p></div></div>
      <div className="card"><h4>Big upcoming one-off or yearly expenses · next 12 months</h4>{summary.bigUpcoming.length ? <ul className="dashboard-list">{summary.bigUpcoming.map((item, index) => <li key={index}><span>{item.description} · {item.date}</span><strong>{money(item.amount, currency)}</strong><small>Set aside {money(item.monthlySetAside, currency)}/month</small></li>)}</ul> : <p className="muted">No upcoming one-off or yearly expenses.</p>}</div>
      <label className="field dashboard-selector"><span>Show cashflow table</span><select value={view} onChange={event => setView(event.target.value)}><option value="account">Individual accounts</option><option value="group">Groups</option><option value="total">Total</option></select></label>
      {view === 'total' ? <CashflowTable title={`All accounts · ${currency}`} months={summary.months}/> : view === 'account' ? summary.accounts.map(account => <CashflowTable key={account.id} title={account.name} months={account.months}/>) : summary.groups.length ? summary.groups.map(group => <CashflowTable key={group.id} title={group.name} months={group.months}/>) : <div className="card empty">No groups in {currency} yet. <Link to="/accountgroup/new">Create a group →</Link></div>}
    </section>)}
    <section className="card table-scroll"><h3>Historical off-plan entries</h3><p className="muted">Recorded expense amounts above their expected maximum and income amounts below their expected minimum, by occurrence. <Link to="/expense">Update monthly amounts →</Link></p>
      {overageError && <p className="error" role="alert">{overageError}</p>}
      {!overages && !overageError && <p>Loading off-plan entries…</p>}
      {overages && (overages.length ? <table><thead><tr><th>Date</th><th>Entry</th><th>Type</th><th>Amount</th><th>Limit</th></tr></thead><tbody>{overages.map(row => <tr key={`${row.kind}-${row.id}-${row.date}`}><td>{row.date}</td><td>{row.description}</td><td>{row.kind === 'expense' ? 'Expense above maximum' : 'Income below minimum'}</td><td className="balance-negative">{Number(row.amount).toFixed(2)}</td><td>{Number(row.limit).toFixed(2)}</td></tr>)}</tbody></table> : <p className="muted">No recorded amounts outside their expected range.</p>)}
    </section>
    <p className="muted footnote">Projections use your opening balances and scheduled entries. Add accounts to a group to choose a consolidated cashflow view.</p>
  </main>
}
