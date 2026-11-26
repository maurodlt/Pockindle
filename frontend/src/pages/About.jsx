import React from 'react'
import { Link } from 'react-router-dom'

export default function About() {
  return <main className="container narrow about-page">
    <div className="page-heading"><div><p className="eyebrow">ABOUT THE APP</p><h1>About Pockindle</h1><p className="muted">Personal finances, today and in the months ahead.</p></div></div>
    <section className="card"><h2>What you can do</h2><p>Track income and fixed, variable, and extraordinary expenses across multiple accounts. See today's balance, upcoming bills, monthly cashflow and savings trends on the overview. Group accounts to view a consolidated forecast, organize entries by optional income or expense categories, and schedule one-time or repeating transfers between accounts.</p></section>
    <section className="card"><h2>Getting started</h2><ol><li><Link to="/account/new">Add an account</Link> with its opening balance, date and currency. Add more accounts if needed, then <Link to="/accountgroup/new">create a group</Link> to consolidate them.</li><li>Add <Link to="/income/new">income</Link> and <Link to="/expense/new">expenses</Link>. Choose the type first; set a repeat interval for recurring entries. Create categories directly from an entry form, or leave the category empty.</li><li>Use the month and year selectors on the <Link to="/income">income</Link> and <Link to="/expense">expenses</Link> pages to update monthly amounts. Variable entries highlighted in yellow need an actual amount.</li><li>Visit <Link to="/">Overview</Link> for balances, spending, alerts and projected cashflow. Use the cashflow table selector to compare accounts, groups and the total. <Link to="/transfer">Transfers</Link> move funds between accounts in the same currency and can repeat.</li></ol></section>
    <section className="card"><h2>Credits</h2><p>Developed by Mauro Dalle Lucca Tosi.</p><span className="besser-tag">Built with BESSER</span></section>
  </main>
}
