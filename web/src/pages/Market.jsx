import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useApi, money, num } from '../lib/api.js'
import { Loading, Problem, Empty, Absent } from '../components/UI.jsx'
import { Ranked } from '../components/Charts.jsx'

export default function Market() {
  const [params, setParams] = useSearchParams()
  const q = params.get('q') || ''
  const category = params.get('category') || ''
  const sort = params.get('sort') || 'postings'
  const [draft, setDraft] = useState(q)

  const meta = useApi('/meta', [])
  const { data, error, loading } = useApi(
    `/roles?q=${encodeURIComponent(q)}&category=${category}&sort=${sort}&limit=25`,
    [q, category, sort])

  const set = (patch) => {
    const next = { q, category, sort, ...patch }
    setParams(Object.fromEntries(Object.entries(next).filter(([, v]) => v)))
  }

  return (
    <>
      <h1>The market</h1>
      <p className="lede">See what other companies ask for and pay for the same job.
        Titles are grouped, so one job appears once no matter how it was advertised.</p>

      <form className="filters" onSubmit={(e) => { e.preventDefault(); set({ q: draft }) }}>
        <label className="field grow">Describe the role
          <input value={draft} onChange={(e) => setDraft(e.target.value)}
            placeholder="someone to run our kubernetes platform" />
        </label>
        <label className="field">Category
          <select value={category} onChange={(e) => set({ category: e.target.value })}>
            <option value="">All</option>
            {meta.data?.categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </label>
        <label className="field">Order by
          <select value={sort} onChange={(e) => set({ sort: e.target.value })}>
            <option value="postings">Most openings</option>
            <option value="employers">Most employers</option>
            <option value="pay">Highest pay</option>
          </select>
        </label>
        <button className="btn" type="submit">Search</button>
      </form>

      {loading && <Loading what="Loading the market" />}
      {error && <Problem message={error} />}
      {data && data.rows.length === 0 && (
        <Empty title={`Nothing matched "${q}".`} hint="Try naming the tools the job needs." />
      )}

      {data && data.rows.length > 0 && (
        <>
          <section className="section">
            <div className="chartbox">
              <h3>Openings for these jobs</h3>
              <p className="muted">How much competition you face when hiring for each.</p>
              <Ranked
                data={data.rows.slice(0, 10).map((r) => ({ name: r.role_label, value: r.postings }))}
                height={340} />
            </div>
          </section>

          <p className="muted" style={{ marginTop: '1.4rem' }}>
            Showing {data.rows.length} of {num(data.total)}</p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Job</th><th>Category</th><th className="n">Openings</th>
                  <th className="n">Employers</th><th className="n">Median pay</th>
                  <th className="n">Experienced</th></tr>
              </thead>
              <tbody>
                {data.rows.map((r) => (
                  <tr key={r.role}>
                    <td><Link to={`/study/${encodeURIComponent(r.role)}`}>{r.role_label}</Link></td>
                    <td className="muted">{r.category}</td>
                    <td className="n">{num(r.postings)}</td>
                    <td className="n">{num(r.companies)}</td>
                    <td className="n">
                      {r.median_salary ? money(r.median_salary)
                        : <Absent reason={`only ${r.salary_companies} quoted pay`} />}
                    </td>
                    <td className="n">{Math.round(r.pct_senior_or_above)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  )
}
