import React from 'react'
import { BrowserRouter, Link, NavLink, Route, Routes } from 'react-router-dom'
import Dashboard from './pages/Dashboard.jsx'
import { EntityForm, EntityList } from './pages/EntityList.jsx'
import { entities } from './entities.js'

export default function App() {
  return <BrowserRouter><div className="app-shell"><header className="site-header"><div className="header-inner"><Link className="brand" to="/"><span className="brand-mark">◈</span> stillwater<span className="brand-dot">.</span></Link><nav aria-label="Main navigation"><NavLink to="/" end>Overview</NavLink>{Object.entries(entities).map(([key, config]) => <span key={key} className="nav-group"><NavLink to={`/${key}`}>{config.label}</NavLink>{!config.readOnlyCreate && <Link className="nav-new" to={`/${key}/new`} title={`New ${config.singular}`}>+</Link>}</span>)}</nav></div></header>
    <Routes><Route path="/" element={<Dashboard />}/>{Object.keys(entities).map(key => <React.Fragment key={key}><Route path={`/${key}`} element={<EntityList entity={key}/>}/>{!entities[key].readOnlyCreate && <Route path={`/${key}/new`} element={<EntityForm entity={key}/>}/>}<Route path={`/${key}/:id/edit`} element={<EntityForm entity={key}/>}/></React.Fragment>)}<Route path="*" element={<main className="container"><h1>Page not found</h1><Link to="/">Back to overview</Link></main>}/></Routes>
    <footer className="site-footer">A calmer way to see what’s next · Stillwater</footer></div></BrowserRouter>
}
