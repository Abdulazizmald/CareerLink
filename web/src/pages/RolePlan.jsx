import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { get, useApi, money, num } from '../lib/api.js'
import { Loading, Problem, Absent, Stat, Bar, VideoCard, BookCard } from '../components/UI.jsx'

export default function RolePlan() {
  const { role } = useParams()
  const { data, error, loading } = useApi(`/roles/${encodeURIComponent(role)}`, [role])
  const learn = useApi(`/learn/role/${encodeURIComponent(role)}`, [role])

  const [openSkill, setOpenSkill] = useState(null)
  const [skillResources, setSkillResources] = useState({})

  const toggleSkill = (name) => {
    if (openSkill === name) { setOpenSkill(null); return }
    setOpenSkill(name)
    if (skillResources[name]) return
    setSkillResources((prev) => ({ ...prev, [name]: { loading: true } }))
    get(`/learn/skill/${encodeURIComponent(name)}`)
      .then((d) => setSkillResources((prev) => ({ ...prev, [name]: { data: d } })))
      .catch((e) => setSkillResources((prev) => ({ ...prev, [name]: { error: e.message } })))
  }

  if (loading) return <Loading what="Building your plan" />
  if (error) return <Problem message={error} />
  if (!data || data.error) return <Problem message="No job by that name" />

  return (
    <>
      <p className="muted"><Link to="/study">Study guide</Link> · {data.category}</p>
      <h1>{data.label}</h1>

      <dl className="stats" style={{ marginTop: '1.4rem' }}>
        <Stat label="Open jobs" value={num(data.postings)} note="advertised in one month" />
        <Stat label="Employers" value={num(data.companies)} note="hiring for this" />
        <Stat label="Median pay"
          value={data.pay ? money(data.pay) : '—'}
          note={data.pay ? `across ${data.payEmployers} employers`
            : 'too few employers quoted a figure'} />
        <Stat label="Experienced roles" value={`${Math.round(data.seniorPct)}%`}
          note="senior or above" />
      </dl>

      <section className="section">
        <h2>What the job is</h2>
        <p className="prose">{data.summary}</p>
      </section>

      <section className="section">
        <h2>Your plan</h2>
        <p className="muted">In order. Skills asked for by the most adverts come first,
          so you learn what gets you hired soonest.</p>
        {data.plan.map((step, i) => (
          <div className="step" key={step.title}>
            <h3><span className="n">{i + 1}</span>{step.title}</h3>
            <p className="muted">{step.why}</p>
            {step.skills.map((s) => (
              <div key={s.name}>
                <div className="rowline">
                  <span className="nm">
                    <Link to={`/skills/${encodeURIComponent(s.name)}`}>{s.name}</Link>
                  </span>
                  <Bar pct={s.share} />
                  <span className="v">{s.share}%</span>
                  <button type="button" className="btn quiet" style={{ padding: '.3rem .8rem' }}
                    onClick={() => toggleSkill(s.name)}>
                    {openSkill === s.name ? 'Hide ▴' : 'Learn ▾'}
                  </button>
                </div>
                {openSkill === s.name && (
                  <div className="grid g2" style={{ margin: '.6rem 0 1.2rem' }}>
                    {!skillResources[s.name] || skillResources[s.name].loading ? (
                      <Loading what={`Finding resources for ${s.name}`} />
                    ) : skillResources[s.name].error ? (
                      <Problem message={skillResources[s.name].error} />
                    ) : (
                      <>
                        <VideoCard video={skillResources[s.name].data.video}
                          error={skillResources[s.name].data.videoError} />
                        <BookCard book={skillResources[s.name].data.book}
                          error={skillResources[s.name].data.bookError} />
                      </>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        ))}
      </section>

      <section className="section">
        <h2>Learn the job itself</h2>
        <p className="muted">Found live rather than fixed in advance, so nothing here
          points at a video or book that was taken down.</p>
        {learn.loading && <Loading what="Finding videos and books" />}
        {learn.error && <Problem message={learn.error} />}
        {learn.data && (
          <>
            <div className="grid g3" style={{ marginBottom: '1rem' }}>
              {(learn.data.videos.length ? learn.data.videos : [null]).map((v, i) => (
                <VideoCard key={v?.url || i} video={v}
                  error={i === 0 ? learn.data.videosError : null} />
              ))}
            </div>
            <div className="grid g3">
              {(learn.data.books.length ? learn.data.books : [null]).map((b, i) => (
                <BookCard key={b?.url || i} book={b}
                  error={i === 0 ? learn.data.booksError : null} />
              ))}
            </div>
          </>
        )}
        <p style={{ marginTop: '1.2rem' }}>
          <Link className="btn quiet" to={`/jobs?q=${encodeURIComponent(data.label)}`}>See open jobs</Link>
        </p>
      </section>

      {data.certifications.length > 0 && (
        <section className="section">
          <h2>Certifications worth having</h2>
          <p className="muted">Easiest first. Each one is a real, current credential you
            can book today.</p>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Certification</th><th>From</th><th>Level</th><th>What it covers</th></tr></thead>
              <tbody>
                {data.certifications.map((c) => (
                  <tr key={c.name}>
                    <td>{c.url
                      ? <a href={c.url} target="_blank" rel="noopener noreferrer">{c.name}</a>
                      : c.name}</td>
                    <td className="muted">{c.provider}</td>
                    <td><span className="tag">{c.level}</span></td>
                    <td className="muted">{c.focus}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {data.related.length > 0 && (
        <section className="section">
          <h2>Similar jobs</h2>
          <div className="chiprow">
            {data.related.map((r) => (
              <Link className="chip plain" key={r.role} to={`/study/${encodeURIComponent(r.role)}`}>
                {r.role_label}<b>{num(r.postings)}</b>
              </Link>
            ))}
          </div>
        </section>
      )}
    </>
  )
}
