import React from 'react'
import { BrowserRouter, Link, NavLink, Route, Routes } from 'react-router-dom'
import Dashboard from './pages/Dashboard.jsx'
import Transfers from './pages/Transfers.jsx'
import { EntityForm, EntityList } from './pages/EntityList.jsx'
import { entities } from './entities.js'

export default function App() {
  return <BrowserRouter><div className="app-shell"><header className="site-header"><div className="header-inner"><Link className="brand" to="/"><span className="brand-mark">◈</span> Pockindle<span className="brand-dot">.</span></Link><nav aria-label="Main navigation"><NavLink to="/" end>Overview</NavLink><details className="nav-menu"><summary>Accounts ▾</summary><div className="nav-dropdown"><NavLink to="/account">Individual Accounts</NavLink><NavLink to="/accountgroup">Groups</NavLink></div></details><details className="nav-menu"><summary>Entries ▾</summary><div className="nav-dropdown"><NavLink to="/entry">All entries</NavLink><NavLink to="/revenue">Revenue</NavLink><NavLink to="/expense">Expenses</NavLink><NavLink to="/transfer">Transfers</NavLink><NavLink to="/category">Categories</NavLink></div></details></nav></div></header>
    <Routes><Route path="/" element={<Dashboard />}/><Route path="/transfer" element={<Transfers />}/>{Object.keys(entities).map(key => <React.Fragment key={key}><Route path={`/${key}`} element={<EntityList entity={key}/>}/>{!entities[key].readOnlyCreate && <Route path={`/${key}/new`} element={<EntityForm entity={key}/>}/>}<Route path={`/${key}/:id/edit`} element={<EntityForm entity={key}/>}/></React.Fragment>)}<Route path="*" element={<main className="container"><h1>Page not found</h1><Link to="/">Back to overview</Link></main>}/></Routes>
    <footer className="site-footer">A calmer way to see what’s next · Pockindle</footer></div></BrowserRouter>
}
