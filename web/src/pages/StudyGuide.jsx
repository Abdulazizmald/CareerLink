import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useApi, num } from '../lib/api.js'
import { Loading, Problem, Empty } from '../components/UI.jsx'

export default function StudyGuide() {
  const [params, setParams] = useSearchParams()
  const q = params.get('q') || ''
  const category = params.get('category') || ''
  const [draft, setDraft] = useState(q)

  const meta = useApi('/meta', [])
  const { data, error, loading } = useApi(
    `/roles?q=${encodeURIComponent(q)}&category=${category}&limit=20`, [q, category])

  const apply = (e) => {
    e.preventDefault()
    setParams(draft ? { q: draft, category } : category ? { category } : {})
  }

  return (
    <>
      <h1>Study guide</h1>
      <p className="lede">Tell us what you can already do. We will find the jobs that
        want it, and build you a plan for the rest.</p>

      <form className="filters" onSubmit={apply}>
        <label className="field grow">What do you already know?
          <input value={draft} onChange={(e) => setDraft(e.target.value)}
            placeholder="python and sql, i build dashboards" />
        </label>
        <label className="field">Category
          <select value={category}
            onChange={(e) => setParams(q ? { q, category: e.target.value } : { category: e.target.value })}>
            <option value="">All categories</option>
            {meta.data?.categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </label>
        <button className="btn" type="submit">Find jobs for me</button>
      </form>
      <p className="muted" style={{ marginTop: '.7rem' }}>
        Name the tools you can use rather than describing the work. "kubernetes terraform"
        finds more than "i look after servers".</p>

      {loading && <Loading what="Matching jobs" />}
      {error && <Problem message={error} />}
      {data && data.rows.length === 0 && (
        <Empty title={`Nothing matched "${q}".`}
          hint="Try naming a tool, or clear the box to browse the biggest jobs instead." />
      )}

      {data && data.rows.length > 0 && (
        <>
          <p className="muted" style={{ marginTop: '1.4rem' }}>
            {data.scored ? `Closest ${data.rows.length} of ${num(data.total)} jobs`
              : `${data.rows.length} biggest jobs. Type above to match them to you.`}
          </p>
          <div className="grid g2">
            {data.rows.map((r) => (
              <Link className="card" key={r.role} to={`/study/${encodeURIComponent(r.role)}`}>
                <h3>{r.role_label}</h3>
                <p className="muted">{r.category} · {num(r.postings)} openings ·{' '}
                  {num(r.companies)} employers</p>
                <div className="chiprow">
                  {r.skills.slice(0, 5).map((s) => <span className="chip next" key={s}>{s}</span>)}
                </div>
                <p className="more" style={{ marginTop: '.9rem', marginBottom: 0 }}>
                  See the plan →</p>
              </Link>
            ))}
          </div>
        </>
      )}
    </>
  )
}
