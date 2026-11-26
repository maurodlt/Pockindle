import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, list } from '../api.js'
import { today } from '../entities.js'

export default function Transfers() {
  const [accounts, setAccounts] = useState(null)
  const [transfers, setTransfers] = useState(null)
  const [values, setValues] = useState({ fromAccount: '', toAccount: '', amount: '', date: today(), description: '', recurrenceIntervalMonths: '', endDate: '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  async function refresh() {
    try {
      const [items, records] = await Promise.all([list('account'), api('/transfer/')])
      setAccounts(items); setTransfers(records)
    } catch (e) { setError(e.message) }
  }
  useEffect(() => { refresh() }, [])
  async function submit(event) {
    event.preventDefault(); setBusy(true); setError('')
    try {
      await api('/transfer/', { method: 'POST', body: JSON.stringify({ ...values, fromAccount: Number(values.fromAccount), toAccount: Number(values.toAccount), amount: Number(values.amount), recurrenceIntervalMonths: values.recurrenceIntervalMonths ? Number(values.recurrenceIntervalMonths) : null, endDate: values.recurrenceIntervalMonths && values.endDate ? values.endDate : null }) })
      setValues(current => ({ ...current, amount: '', description: '', recurrenceIntervalMonths: '', endDate: '' }))
      await refresh()
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }
  async function erase(id) {
    if (!window.confirm('Delete this transfer?')) return
    try { setError(''); await api(`/transfer/${id}/`, { method: 'DELETE' }); await refresh() }
    catch (e) { setError(e.message) }
  }
  const source = accounts?.find(a => a.id === Number(values.fromAccount))
  return <main className="container"><div className="page-heading"><div><p className="eyebrow">MOVE MONEY</p><h1>Transfers</h1><p className="muted">Move money between accounts in the same currency. Consolidated balances stay unchanged.</p></div></div>
    {error && <p className="error" role="alert">{error}</p>}
    {!accounts || !transfers ? <p>Loading transfers…</p> : <>
      {accounts.length < 2 ? <div className="card empty">Add at least two accounts to make a transfer. <Link to="/account/new">Add an account →</Link></div> :
        <form className="card form" onSubmit={submit}>
          <label className="field"><span>From account *</span><select required value={values.fromAccount} onChange={e => setValues({ ...values, fromAccount: e.target.value, toAccount: '' })}><option value="">Choose an account</option>{accounts.map(a => <option key={a.id} value={a.id}>{a.name} · {a.currency}</option>)}</select></label>
          <label className="field"><span>To account *</span><select required value={values.toAccount} onChange={e => setValues({ ...values, toAccount: e.target.value })}><option value="">Choose an account</option>{accounts.filter(a => a.id !== Number(values.fromAccount) && (!source || a.currency === source.currency)).map(a => <option key={a.id} value={a.id}>{a.name} · {a.currency}</option>)}</select></label>
          <label className="field"><span>Amount *</span><input type="number" required min="0.01" step="0.01" value={values.amount} onChange={e => setValues({ ...values, amount: e.target.value })}/></label>
          <label className="field"><span>Date *</span><input type="date" required value={values.date} onChange={e => setValues({ ...values, date: e.target.value })}/></label>
          <label className="field"><span>Description</span><input type="text" maxLength="100" value={values.description} onChange={e => setValues({ ...values, description: e.target.value })}/></label>
          <label className="field"><span>Repeat transfer</span><select value={values.recurrenceIntervalMonths ? 'repeat' : 'once'} onChange={e => setValues({ ...values, recurrenceIntervalMonths: e.target.value === 'repeat' ? '1' : '', endDate: '' })}><option value="once">One time</option><option value="repeat">Repeat monthly</option></select></label>
          {values.recurrenceIntervalMonths && <><label className="field"><span>Repeat every (months) *</span><input type="number" required min="1" step="1" value={values.recurrenceIntervalMonths} onChange={e => setValues({ ...values, recurrenceIntervalMonths: e.target.value })}/></label><label className="field"><span>Repeat until (optional)</span><input type="date" min={values.date} value={values.endDate} onChange={e => setValues({ ...values, endDate: e.target.value })}/></label></>}
          <div className="form-actions"><button className="button" disabled={busy}>{busy ? 'Transferring…' : 'Transfer money'}</button></div>
        </form>}
      <section className="card table-scroll"><h2>Transfer history</h2>{transfers.length === 0 ? <p className="muted">No transfers yet.</p> : <table><thead><tr><th>Date</th><th>From</th><th>To</th><th>Amount</th><th>Description</th><th>Repeats</th><th>Actions</th></tr></thead><tbody>{transfers.map(t => <tr key={t.id}><td>{t.date}</td><td>{accounts.find(a => a.id === t.fromAccount_id)?.name || t.fromAccount_id}</td><td>{accounts.find(a => a.id === t.toAccount_id)?.name || t.toAccount_id}</td><td>{t.amount.toFixed(2)}</td><td>{t.description || '—'}</td><td>{t.recurrenceIntervalMonths ? `Every ${t.recurrenceIntervalMonths} month${t.recurrenceIntervalMonths === 1 ? '' : 's'}${t.endDate ? ` until ${t.endDate}` : ''}` : 'No'}</td><td><button className="text-button danger" onClick={() => erase(t.id)}>Delete</button></td></tr>)}</tbody></table>}</section>
    </>}
  </main>
}
