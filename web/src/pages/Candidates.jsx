import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useApi, num } from '../lib/api.js'
import { Loading, Problem, Empty, Absent } from '../components/UI.jsx'

export default function Candidates() {
  const [params, setParams] = useSearchParams()
  const q = params.get('q') || ''
  const role = params.get('role') || ''
  const limit = params.get('limit') || '10'
  const [draft, setDraft] = useState(q)

  const meta = useApi('/meta', [])
  const { data, error, loading } = useApi(
    `/candidates?q=${encodeURIComponent(q)}&role=${encodeURIComponent(role)}&limit=${limit}`,
    [q, role, limit])

  const set = (patch) => {
    const next = { q, role, limit, ...patch }
    setParams(Object.fromEntries(Object.entries(next).filter(([, v]) => v)))
  }

  return (
    <>
      <h1>Candidates</h1>
      <p className="lede">Pick the job you are hiring for, or describe what you need.
        Everyone here works in technology.</p>

      <form className="filters" onSubmit={(e) => { e.preventDefault(); set({ q: draft }) }}>
        <label className="field">Hiring for
          <select value={role} onChange={(e) => set({ role: e.target.value })}>
            <option value="">Any job</option>
            {meta.data?.roles.map((r) => <option key={r.role} value={r.role}>{r.label}</option>)}
          </select>
        </label>
        <label className="field grow">Or describe what you need
          <input value={draft} onChange={(e) => setDraft(e.target.value)}
            placeholder="aws and terraform, has run production systems" />
        </label>
        <label className="field">Show
          <select value={limit} onChange={(e) => set({ limit: e.target.value })}>
            <option value="5">Top 5</option>
            <option value="10">Top 10</option>
            <option value="25">Top 25</option>
          </select>
        </label>
        <button className="btn" type="submit">Find people</button>
      </form>

      {loading && <Loading what="Ranking candidates" />}
      {error && <Problem message={error} />}
      {data && data.rows.length === 0 && (
        <Empty title="Nobody matched."
          hint="Most people describe their work rather than listing tools, so try broader words." />
      )}

      {data && data.rows.length > 0 && (
        <>
          <p className="muted" style={{ marginTop: '1.4rem' }}>
            {data.scored ? `Best ${data.rows.length} of ${num(data.pool)} people`
              : `${data.rows.length} of ${num(data.pool)} people. Search above to rank them.`}
          </p>
          <div className="grid">
            {data.rows.map((c) => (
              <article className="card" key={c.id}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '.7rem', flexWrap: 'wrap' }}>
                  <h3 style={{ margin: 0 }}>Candidate</h3>
                  <span className="tag">{c.id}</span>
                  {!c.real && <span className="tag warn">example profile</span>}
                  {c.relevance != null && (
                    <span className="muted" style={{ marginLeft: 'auto', fontFamily: 'DM Mono' }}>
                      {c.relevance.toFixed(3)}
                    </span>
                  )}
                </div>
                <p className="muted" style={{ margin: '.6rem 0 .9rem' }}>{c.summary}</p>
                {c.bio && <p style={{ margin: '0 0 .9rem' }}>{c.bio}</p>}
                <div className="grid g3" style={{ gap: '.8rem', marginBottom: '.9rem' }}>
                  <div><div className="muted" style={{ fontSize: '.7rem', textTransform: 'uppercase', letterSpacing: '.09em' }}>Education</div>
                    <div>{c.degree ? `${c.degree}${c.major ? ` in ${c.major}` : ''}` : <Absent />}</div></div>
                  <div><div className="muted" style={{ fontSize: '.7rem', textTransform: 'uppercase', letterSpacing: '.09em' }}>Experience</div>
                    <div>{c.years ? `${c.years} years` : <Absent />}</div></div>
                  <div><div className="muted" style={{ fontSize: '.7rem', textTransform: 'uppercase', letterSpacing: '.09em' }}>GPA</div>
                    <div>{c.gpa || <Absent />}</div></div>
                </div>
                <div className="chiprow" style={{ marginBottom: '.9rem' }}>
                  {c.skills.slice(0, 12).map((s) => (
                    <Link className="chip plain" key={s} to={`/skills/${encodeURIComponent(s)}`}>{s}</Link>
                  ))}
                </div>
                <Link className="more" to={`/candidates/${encodeURIComponent(c.id)}`}>
                  See full resume →</Link>
              </article>
            ))}
          </div>
          <p className="muted" style={{ marginTop: '1.4rem' }}>
            Candidates are identified by reference number because the resume source
            removed names. A dash means the resume did not say, not that the person
            lacks it.</p>
        </>
      )}
    </>
  )
}
