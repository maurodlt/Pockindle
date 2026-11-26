import React, { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, get, list, remove, save } from '../api.js'
import { entities, initialValues, payload } from '../entities.js'

export function Projection({ entity, id }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    setData(null); setError('')
    api(`/${entity}/${id}/cashflow/`).then(setData).catch(e => setError(e.message))
  }, [entity, id])
  if (error) return <p className="error" role="alert">{error}</p>
  if (!data) return <p>Loading projection…</p>
  return <section className="card"><h2>Monthly cashflow · {data.currency}</h2><p className="muted">Projected end-of-month balances, based on your opening balances and scheduled entries.</p>
    <div className="table-scroll"><table><thead><tr><th>Month</th><th>Income</th><th>Spending</th><th>End balance</th></tr></thead><tbody>
      {data.months.map(row => <tr key={row.month}><td>{row.month}</td><td>{row.revenue.toFixed(2)}</td><td>{row.spending.toFixed(2)}</td><td><strong>{row.endBalance.toFixed(2)}</strong></td></tr>)}
    </tbody></table></div></section>
}

export function EntityList({ entity }) {
  const config = entities[entity]
  const [rows, setRows] = useState(null)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState(null)
  function refresh() { setRows(null); setError(''); list(entity).then(setRows).catch(e => setError(e.message)) }
  useEffect(refresh, [entity])
  async function erase(row) {
    if (!window.confirm(`Delete ${row.name || row.description || config.singular}?`)) return
    try { await remove(entity, row.id); if (selected === row.id) setSelected(null); refresh() } catch (e) { setError(e.message) }
  }
  function display(field, row) {
    const value = row[field.name === 'account' || field.name === 'category' ? `${field.name}_id` : field.name]
    return Array.isArray(value) ? value.join(', ') : value == null ? '—' : String(value)
  }
  return <main className="container"><div className="page-heading"><div><p className="eyebrow">YOUR FINANCES</p><h1>{config.label}</h1><p className="muted">Keep your financial picture up to date.</p></div>
    {!config.readOnlyCreate && <Link className="button" to={`/${entity}/new`}>+ New {config.singular.toLowerCase()}</Link>}
  </div>
  {error && <p className="error" role="alert">{error}</p>}
  {rows === null ? <p>Loading {config.label.toLowerCase()}…</p> : rows.length === 0 ? <div className="card empty">No {config.label.toLowerCase()} yet. {!config.readOnlyCreate && <Link to={`/${entity}/new`}>Add your first one →</Link>}</div> :
    <div className="card table-scroll"><table><thead><tr><th>#</th>{config.fields.filter(f => f.type !== 'multi').map(f => <th key={f.name}>{f.label}</th>)}<th>Actions</th></tr></thead><tbody>{rows.map(row => <tr key={row.id}>
      <td>{row.id}</td>{config.fields.filter(f => f.type !== 'multi').map(f => <td key={f.name}>{display(f, row)}</td>)}
      <td className="actions">{(entity === 'account' || entity === 'accountgroup') && <button className="text-button" onClick={() => setSelected(selected === row.id ? null : row.id)}>Cashflow</button>}
        <Link to={`/${entity}/${row.id}/edit`}>Edit</Link><button className="text-button danger" onClick={() => erase(row)}>Delete</button></td>
    </tr>)}</tbody></table></div>}
  {selected && <Projection entity={entity} id={selected} />}
  {entity === 'entry' && <p className="muted">New entries are added as revenues or expenses. Edit or delete them here, too.</p>}
  </main>
}

export function EntityForm({ entity }) {
  const { id } = useParams()
  const navigate = useNavigate()
  const config = entities[entity]
  const [values, setValues] = useState(() => initialValues(entity))
  const [options, setOptions] = useState({})
  const [loading, setLoading] = useState(Boolean(id))
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    setValues(initialValues(entity)); setError(''); setLoading(Boolean(id))
    if (id) get(entity, id).then(result => {
      const record = result[entity] || result
      const linked = entity === 'accountgroup' ? { accounts: result.account_ids } : entity === 'account' ? { groups: result.accountgroup_ids } : {}
      setValues({ ...initialValues(entity), ...record, ...linked, account: record.account_id, category: record.category_id }); setLoading(false)
    }).catch(e => { setError(e.message); setLoading(false) })
    const sources = [...new Set(config.fields.filter(f => f.source).map(f => f.source))]
    Promise.all(sources.map(source => list(source).then(items => [source, items]))).then(pairs => setOptions(Object.fromEntries(pairs))).catch(e => setError(e.message))
  }, [entity, id])
  async function submit(event) {
    event.preventDefault(); setBusy(true); setError('')
    try { await save(entity, payload(entity, values), id); navigate(`/${entity}`) }
    catch (e) { setError(e.message) } finally { setBusy(false) }
  }
  return <main className="container narrow"><Link className="back" to={`/${entity}`}>← {config.label}</Link><div className="page-heading"><div><p className="eyebrow">{id ? 'UPDATE' : 'CREATE'}</p><h1>{id ? `Edit ${config.singular.toLowerCase()}` : `New ${config.singular.toLowerCase()}`}</h1></div></div>
    {error && <p className="error" role="alert">{error}</p>}
    {loading ? <p>Loading {config.singular.toLowerCase()}…</p> : <form className="card form" onSubmit={submit}>{config.fields.map(field => <label key={field.name} className="field"><span>{field.label}{field.required && ' *'}</span>
      {field.type === 'multi' ? <div className="checks">{(options[field.source] || []).length === 0 ? <span className="muted">Create an {field.source === 'account' ? 'account' : 'account group'} first.</span> : options[field.source].map(option => <label key={option.id}><input type="checkbox" checked={(values[field.name] || []).includes(option.id)} onChange={event => setValues(current => ({ ...current, [field.name]: event.target.checked ? [...(current[field.name] || []), option.id] : current[field.name].filter(value => value !== option.id) }))}/>{option.name}</label>)}</div>
      : field.type === 'reference' || field.type === 'enum' ? <select value={values[field.name] ?? ''} required={field.required} onChange={event => setValues({ ...values, [field.name]: event.target.value })}>
        {field.type === 'reference' ? <><option value="">Choose {field.label.toLowerCase()}</option>{(options[field.source] || []).map(option => <option key={option.id} value={option.id}>{option.name}</option>)}</> : field.options.map(option => <option key={option} value={option}>{option === 'FIX' ? 'Fixed' : option === 'VARIABLE' ? 'Variable' : option === 'EXTRAORDINARY' ? 'Extraordinary' : option}</option>)}</select>
      : <input type={field.type} value={values[field.name] ?? ''} required={field.required} min={field.min} step={field.type === 'number' ? field.step || 'any' : undefined} onChange={event => setValues({ ...values, [field.name]: event.target.value })}/>}</label>)}
      <div className="form-actions"><button className="button" disabled={busy || (entity === 'accountgroup' && !(values.accounts || []).length)}>{busy ? 'Saving…' : id ? 'Save changes' : `Create ${config.singular.toLowerCase()}`}</button><Link to={`/${entity}`}>Cancel</Link></div>
    </form>}
  </main>
}
