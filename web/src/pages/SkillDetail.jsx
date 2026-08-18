import { Link, useParams } from 'react-router-dom'
import { useApi, money, num } from '../lib/api.js'
import { Loading, Problem, Bar } from '../components/UI.jsx'
import { Ranked } from '../components/Charts.jsx'

export default function SkillDetail() {
  const { skill } = useParams()
  const { data, error, loading } = useApi(`/skills/${encodeURIComponent(skill)}`, [skill])

  if (loading) return <Loading what={`Loading ${skill}`} />
  if (error) return <Problem message={error} />
  if (!data || data.error) return <Problem message="No skill by that name" />

  return (
    <>
      <p className="muted"><Link to="/skills">Skills</Link></p>
      <h1>{data.name}</h1>
      {data.description && <p className="lede">{data.description}</p>}

      {data.learnNext.length > 0 && (
        <section className="section">
          <h2>Learn these next</h2>
          <p className="muted">Asked for alongside {data.name} but do a different job, so
            each one adds something you do not already have.</p>
          <div className="card">
            {data.learnNext.map((s) => (
              <div className="rowline" key={s.name}>
                <span className="nm"><Link to={`/skills/${encodeURIComponent(s.name)}`}>{s.name}</Link></span>
                <Bar pct={s.strength * 110} />
                <span className="v">{s.strength.toFixed(2)}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {data.alternatives.length > 0 && (
        <section className="section">
          <h2>You probably only need one of these</h2>
          <p className="muted">These do the same job as {data.name}. Knowing both adds
            little, so spend the time elsewhere.</p>
          <div className="chiprow">
            {data.alternatives.map((s) => (
              <Link className="chip covered" key={s.name} to={`/skills/${encodeURIComponent(s.name)}`}>
                {s.name}
              </Link>
            ))}
          </div>
        </section>
      )}

      {data.pay.length > 0 && (
        <section className="section">
          <div className="chartbox">
            <h3>What jobs asking for {data.name} pay</h3>
            <p className="muted">Median salary, one figure per employer.</p>
            <Ranked data={data.pay.map((p) => ({ name: p.category, value: p.pay }))}
              fmt={(v) => `$${Math.round(v / 1000)}k`} />
          </div>
        </section>
      )}

      {data.demand.length > 0 && (
        <section className="section">
          <div className="chartbox">
            <h3>Who is asking for it</h3>
            <p className="muted">Share of jobs in each category that want {data.name}.</p>
            <Ranked data={data.demand.map((d) => ({ name: d.category, value: Math.round(d.share) }))}
              unit="%" />
          </div>
        </section>
      )}
    </>
  )
}
