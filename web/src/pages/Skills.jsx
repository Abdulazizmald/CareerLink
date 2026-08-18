import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useApi, num } from '../lib/api.js'
import { Loading, Problem, Empty } from '../components/UI.jsx'

export default function Skills() {
  const [params, setParams] = useSearchParams()
  const q = params.get('q') || ''
  const group = params.get('group') || ''
  const picked = params.get('skill') || ''
  const [draft, setDraft] = useState(q)

  const meta = useApi('/meta', [])
  const list = useApi(`/skills?q=${encodeURIComponent(q)}&group=${group}`, [q, group])
  const detail = useApi(picked ? `/skills/${encodeURIComponent(picked)}` : '/skills?limit=1', [picked])

  const set = (patch) => {
    const next = { q, group, skill: picked, ...patch }
    setParams(Object.fromEntries(Object.entries(next).filter(([, v]) => v)))
  }
  const names = list.data?.rows.map((r) => r.name) || []

  return (
    <>
      <h1>Skills</h1>
      <p className="lede">Look up any tool to see who hires for it, what it pays, and
        which skills are worth learning next to it.</p>

      <form className="filters" onSubmit={(e) => { e.preventDefault(); set({ q: draft }) }}>
        <label className="field">Area
          <select value={group} onChange={(e) => set({ group: e.target.value, skill: '' })}>
            <option value="">All areas</option>
            {meta.data?.skillGroups.map((g) => <option key={g} value={g}>{g}</option>)}
          </select>
        </label>
        <label className="field">Skill
          <select value={picked} onChange={(e) => set({ skill: e.target.value })}>
            <option value="">Pick one to see its closest matches</option>
            {names.map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </label>
        <label className="field grow">Or search
          <input value={draft} onChange={(e) => setDraft(e.target.value)}
            placeholder="kubernetes, excel, react" />
        </label>
        <button className="btn" type="submit">Search</button>
      </form>

      {picked && detail.data && !detail.data.error && (
        <section className="section">
          <h2>Closest to {picked}</h2>
          <p className="muted">Skills that show up in the same job adverts unusually
            often. Blue means it adds something new. Amber means it does the same job,
            so learning both adds little.</p>
          <div className="card">
            {[...(detail.data.learnNext || []), ...(detail.data.alternatives || [])]
              .sort((a, b) => b.strength - a.strength).slice(0, 5).map((s) => (
                <div className="rowline" key={s.name}>
                  <span className="nm">
                    <Link to={`/skills/${encodeURIComponent(s.name)}`}>{s.name}</Link>
                  </span>
                  <span className="bar"><i style={{ width: `${Math.min(100, s.strength * 110)}%` }} /></span>
                  <span className="v">{s.strength.toFixed(2)}</span>
                  <span className={`chip ${s.relation === 'next' ? 'next' : 'covered'}`}>
                    {s.relation === 'next' ? 'learn next' : 'already covered'}
                  </span>
                </div>
              ))}
          </div>
          <p style={{ marginTop: '.9rem' }}>
            <Link className="btn quiet" to={`/skills/${encodeURIComponent(picked)}`}>
              Open the full page for {picked}</Link>
          </p>
        </section>
      )}

      {list.loading && <Loading what="Loading skills" />}
      {list.error && <Problem message={list.error} />}
      {list.data && list.data.rows.length === 0 && (
        <Empty title={`No skill matches "${q}".`} hint="Try a shorter word." />
      )}

      {list.data && list.data.rows.length > 0 && (
        <section className="section">
          <h2>All skills</h2>
          <p className="muted">{list.data.total} skills{group ? ` in ${group}` : ''},
            ranked by how many job adverts ask for them.</p>
          <div className="grid g2" style={{ marginTop: '.9rem' }}>
            {list.data.rows.slice(0, 24).map((s) => (
              <Link className="card" key={s.name} to={`/skills/${encodeURIComponent(s.name)}`}>
                <h3>{s.name}</h3>
                <p className="muted" style={{ marginBottom: '.6rem' }}>
                  {s.description || 'Asked for across the job market.'}</p>
                <span className="tag">{num(s.postings)} jobs ask for it</span>
              </Link>
            ))}
          </div>
        </section>
      )}
    </>
  )
}
