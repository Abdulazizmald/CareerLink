import { Fragment, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useApi, num } from '../lib/api.js'
import { Loading, Problem, Empty, Absent } from '../components/UI.jsx'

export default function Jobs() {
  const [params, setParams] = useSearchParams()
  const q = params.get('q') || ''
  const category = params.get('category') || ''
  const worksite = params.get('worksite') || ''
  const level = params.get('level') || ''
  const [draft, setDraft] = useState(q)
  const [openJob, setOpenJob] = useState(null)

  const meta = useApi('/meta', [])
  const set = (patch) => {
    const next = { q, category, worksite, level, ...patch }
    setParams(Object.fromEntries(Object.entries(next).filter(([, v]) => v)))
  }
  const { data, error, loading } = useApi(
    `/jobs?q=${encodeURIComponent(q)}&category=${category}&worksite=${worksite}&level=${level}`,
    [q, category, worksite, level])

  return (
    <>
      <h1>Jobs</h1>
      <p className="lede">Describe the work you want, narrow it down, then apply on
        LinkedIn. Each job appears once even when a company posted it many times.</p>

      <form className="filters" onSubmit={(e) => { e.preventDefault(); set({ q: draft }) }}>
        <label className="field grow">Describe the work
          <input value={draft} onChange={(e) => setDraft(e.target.value)}
            placeholder="remote platform work with kubernetes and python" />
        </label>
        <label className="field">Category
          <select value={category} onChange={(e) => set({ category: e.target.value })}>
            <option value="">All</option>
            {meta.data?.categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </label>
        <label className="field">Where
          <select value={worksite} onChange={(e) => set({ worksite: e.target.value })}>
            <option value="">Anywhere</option>
            <option value="remote">From home</option>
            <option value="hybrid">Some days in office</option>
            <option value="onsite">In the office</option>
          </select>
        </label>
        <label className="field">Experience
          <select value={level} onChange={(e) => set({ level: e.target.value })}>
            <option value="">Any</option>
            {meta.data?.levels.map((l) => <option key={l} value={l}>{l}</option>)}
          </select>
        </label>
        <button className="btn" type="submit">Search</button>
      </form>

      {loading && <Loading what="Finding jobs" />}
      {error && <Problem message={error} />}
      {data && data.rows.length === 0 && (
        <Empty title="No jobs matched."
          hint="Loosen one filter. Where you work is the strictest, because most adverts never say." />
      )}

      {data && data.rows.length > 0 && (
        <>
          <p className="muted" style={{ marginTop: '1.4rem' }}>
            Showing {data.rows.length} of {num(data.total)} matching jobs</p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Job</th><th>Company</th><th>Where</th>
                  <th className="n">Pay</th><th className="n">Experience</th><th></th></tr>
              </thead>
              <tbody>
                {data.rows.map((r) => (
                  <Fragment key={r.link}>
                    <tr>
                      <td><b>{r.title}</b><br /><span className="muted">{r.category}</span></td>
                      <td className="muted">{r.company}</td>
                      <td className="muted">{r.location}
                        {r.worksite ? <><br /><span className="tag">{r.worksite}</span></> : null}</td>
                      <td className="n">{r.pay || <Absent reason="not advertised" />}</td>
                      <td className="n">{r.level || <Absent reason="not stated" />}</td>
                      <td className="n" style={{ display: 'flex', gap: '.4rem', flexWrap: 'wrap' }}>
                        {r.description && (
                          <button type="button" className="btn quiet"
                            onClick={() => setOpenJob(openJob === r.link ? null : r.link)}>
                            {openJob === r.link ? 'Hide' : 'Description'}
                          </button>
                        )}
                        <a className="btn quiet" href={r.link} target="_blank" rel="noopener noreferrer">Apply</a>
                      </td>
                    </tr>
                    {openJob === r.link && r.description && (
                      <tr>
                        <td colSpan={6}>
                          <div className="prose" style={{ whiteSpace: 'pre-wrap' }}>{r.description}</div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  )
}
