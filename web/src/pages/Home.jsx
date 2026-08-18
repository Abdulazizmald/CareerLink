import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useApi, money, num } from '../lib/api.js'
import { Loading, Problem, Stat, Skill } from '../components/UI.jsx'
import { Ranked, Levels, PayVsOpenings } from '../components/Charts.jsx'

export default function Home() {
  const { data, error, loading } = useApi('/home')
  const [known, setKnown] = useState('')
  const go = useNavigate()

  const submit = (e) => {
    e.preventDefault()
    go(`/study?q=${encodeURIComponent(known)}`)
  }

  return (
    <>
      {/* The hero is the product: finishing the sentence runs the search. */}
      <section className="opener">
        <form onSubmit={submit}>
          <h1 className="sentence">
            I already know{' '}
            <input value={known} onChange={(e) => setKnown(e.target.value)}
              placeholder="python, sql" aria-label="Skills you already have" />
          </h1>
          <p className="hint">Tell us the tools you can already use. We will show you
            the jobs they lead to, what those jobs pay, and exactly what to learn next.</p>
          <button className="btn lg" type="submit">Show me what to learn</button>
        </form>
      </section>

      <div className="grid g3" style={{ marginTop: '2rem' }}>
        <Link className="card" to="/jobs">
          <h3>Find a job</h3>
          <p className="muted">Search openings by field, level and whether you can work
            from home, then apply on LinkedIn.</p>
          <span className="more">Browse jobs →</span>
        </Link>
        <Link className="card" to="/skills">
          <h3>Look up a skill</h3>
          <p className="muted">See who hires for it, what it pays, and which skills go
            with it rather than repeat it.</p>
          <span className="more">Explore skills →</span>
        </Link>
        <Link className="card" to="/candidates">
          <h3>Hiring someone?</h3>
          <p className="muted">See what other companies ask for and pay for the same
            role, then search the candidate pool.</p>
          <span className="more">Open the recruiter view →</span>
        </Link>
      </div>

      {loading && <div className="section"><Loading what="Loading the market" /></div>}
      {error && <div className="section"><Problem message={error} /></div>}

      {data && (
        <>
          <section className="section">
            <dl className="stats">
              <Stat label="Open jobs" value={num(data.stats.postings)} note="advertised in one month" />
              <Stat label="Employers" value={num(data.stats.employers)} note="hiring across all fields" />
              <Stat label="Distinct jobs" value={num(data.stats.roles)} note="job titles grouped together" />
              <Stat label="Skills tracked" value={num(data.stats.skills)} note="tools and technologies" />
            </dl>
          </section>

          <section className="section">
            <div className="section-head">
              <h2>Where the jobs are</h2>
              <Link className="muted" to="/market">See every job →</Link>
            </div>
            <div className="chartbox">
              <h3>Openings by category</h3>
              <p className="muted">Which parts of the market are hiring the most.</p>
              <Ranked data={data.byCategory.map((c) => ({ name: c.category, value: c.postings }))} />
            </div>
          </section>

          <div className="grid g2 section">
            <div className="chartbox">
              <h3>What each category pays</h3>
              <p className="muted">Median salary, one figure per employer so a single
                large company cannot set the number.</p>
              <Ranked
                data={data.byCategory.filter((c) => c.pay).map((c) => ({ name: c.category, value: c.pay }))}
                fmt={(v) => `$${Math.round(v / 1000)}k`} />
            </div>
            <div className="chartbox">
              <h3>Where you can work from home</h3>
              <p className="muted">Share of adverts offering remote work, among those
                that said where you would be based.</p>
              <Ranked
                data={data.byCategory.filter((c) => c.remote != null)
                  .map((c) => ({ name: c.category, value: Math.round(c.remote) }))}
                unit="%" />
            </div>
          </div>

          <section className="section">
            <div className="chartbox">
              <h3>Pay against opportunity</h3>
              <p className="muted">Further right means more openings. Higher means better
                pay. Bigger circles mean more adverts actually stated a salary.</p>
              <PayVsOpenings data={data.byCategory} />
            </div>
          </section>

          <section className="section">
            <div className="chartbox">
              <h3>Experience wanted</h3>
              <p className="muted">Most adverts are written for experienced people. The
                pale band on the right is adverts that never said which level they wanted.</p>
              <Levels data={data.levels} />
            </div>
          </section>

          <div className="grid g2 section">
            <div>
              <h2>Best paid jobs</h2>
              <p className="muted">Highest median salary of any job with enough employers
                quoting a figure to be worth reporting.</p>
              <table style={{ marginTop: '.9rem' }}>
                <thead><tr><th>Job</th><th className="n">Median pay</th></tr></thead>
                <tbody>
                  {data.bestPaid.map((r) => (
                    <tr key={r.role}>
                      <td><Link to={`/study/${encodeURIComponent(r.role)}`}>{r.label}</Link>
                        <br /><span className="muted">{r.family}</span></td>
                      <td className="n">{money(r.pay)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div>
              <h2>Most wanted skills</h2>
              <p className="muted">Asked for across the most job adverts. A skill wanted in
                many categories travels further if you change direction later.</p>
              <div className="card" style={{ marginTop: '.9rem' }}>
                {data.topSkills.map((s) => {
                  const top = data.topSkills[0].postings
                  return (
                    <div className="rowline" key={s.skill}>
                      <span className="nm"><Link to={`/skills/${encodeURIComponent(s.skill)}`}>{s.skill}</Link></span>
                      <span className="bar"><i style={{ width: `${(100 * s.postings) / top}%` }} /></span>
                      <span className="v">{num(s.postings)}</span>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>

          <section className="section">
            <div className="section-head"><h2>Jobs with the most openings</h2></div>
            <div className="grid g2">
              {data.topRoles.slice(0, 6).map((r) => (
                <Link className="card" key={r.role} to={`/study/${encodeURIComponent(r.role)}`}>
                  <h3>{r.label}</h3>
                  <p className="muted">{r.family} · {num(r.postings)} openings ·{' '}
                    {num(r.companies)} employers{r.pay ? ` · ${money(r.pay)}` : ''}</p>
                  <div className="chiprow">
                    {r.skills.map((s) => <span className="chip next" key={s}>{s}</span>)}
                  </div>
                </Link>
              ))}
            </div>
          </section>
        </>
      )}
    </>
  )
}
