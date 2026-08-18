import { Link, useParams } from 'react-router-dom'
import { useApi } from '../lib/api.js'
import { Loading, Problem, Absent } from '../components/UI.jsx'

export default function CandidateDetail() {
  const { id } = useParams()
  const { data, error, loading } = useApi(`/candidates/${encodeURIComponent(id)}`, [id])

  if (loading) return <Loading what="Loading candidate" />
  if (error) return <Problem message={error} />
  if (!data || data.error) return <Problem message="No candidate by that reference number" />

  return (
    <>
      <p className="muted"><Link to="/candidates">Candidates</Link></p>
      <div style={{ display: 'flex', alignItems: 'center', gap: '.7rem', flexWrap: 'wrap' }}>
        <h1 style={{ margin: 0 }}>Candidate</h1>
        <span className="tag">{data.id}</span>
        {!data.real && <span className="tag warn">example profile</span>}
      </div>
      {data.bio && <p className="lede" style={{ marginTop: '.8rem' }}>{data.bio}</p>}

      <dl className="stats" style={{ margin: '1.4rem 0' }}>
        <div className="stat">
          <dt>Education</dt>
          <dd style={{ font: '500 1.1rem var(--body)' }}>
            {data.degree ? `${data.degree}${data.major ? ` in ${data.major}` : ''}` : <Absent />}</dd>
        </div>
        <div className="stat">
          <dt>Experience</dt>
          <dd style={{ font: '500 1.1rem var(--body)' }}>{data.years ? `${data.years} years` : <Absent />}</dd>
        </div>
        <div className="stat">
          <dt>GPA</dt>
          <dd style={{ font: '500 1.1rem var(--body)' }}>{data.gpa || <Absent />}</dd>
        </div>
      </dl>

      {data.skills.length > 0 && (
        <div className="chiprow" style={{ marginBottom: '1.4rem' }}>
          {data.skills.map((s) => (
            <Link className="chip plain" key={s} to={`/skills/${encodeURIComponent(s)}`}>{s}</Link>
          ))}
        </div>
      )}

      <section className="section">
        <h2>Full resume</h2>
        <p className="muted">Shown as submitted. Contact details were already
          removed at the source.</p>
        <div className="prose">{data.resume}</div>
      </section>
    </>
  )
}
