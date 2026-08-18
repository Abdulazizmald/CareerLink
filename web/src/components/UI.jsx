import { Link } from 'react-router-dom'

// Loading, empty and error are components rather than inline JSX so every page
// fails the same way. An empty result explains what to change; it never renders
// as a blank area that looks like a result of zero.
export const Loading = ({ what = 'Loading' }) => (
  <div className="loading">{what}…</div>
)

export const Problem = ({ message }) => (
  <div className="error">
    <b>Something went wrong.</b> {message}. Refresh, or check the server is running.
  </div>
)

export const Empty = ({ title, hint }) => (
  <div className="empty">
    <b>{title}</b>
    {hint ? <><br />{hint}</> : null}
  </div>
)

// A value that was never stated is shown as an absence with its reason, not as a
// blank cell and never as a zero.
export const Absent = ({ reason = 'not stated' }) => (
  <span className="absent">— {reason}</span>
)

// The signature. A skill always carries what to do about it.
export const Skill = ({ name, state = 'plain', value }) => (
  <Link className={`chip ${state}`} to={`/skills/${encodeURIComponent(name)}`}>
    {name}{value != null ? <b>{value}</b> : null}
  </Link>
)

export const Bar = ({ pct }) => (
  <span className="bar"><i style={{ width: `${Math.max(2, Math.min(100, pct))}%` }} /></span>
)

export const Stat = ({ label, value, note }) => (
  <div className="stat">
    <dt>{label}</dt>
    <dd>{value}</dd>
    {note ? <small>{note}</small> : null}
  </div>
)

// -------------------------------------------------------------- learn cards
// A video/book actually shown, not a search link handed to another site.

const videoId = (url) => {
  try { return new URL(url).searchParams.get('v') } catch { return null }
}

export const VideoCard = ({ video, error }) => {
  if (error) return <Problem message={error} />
  if (!video) return <Empty title="No video found for this." />
  const id = videoId(video.url)
  return (
    <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
      {id && (
        <div style={{ position: 'relative', paddingTop: '56.25%', background: '#000' }}>
          <iframe title={video.title} src={`https://www.youtube.com/embed/${id}`}
            style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', border: 0 }}
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen />
        </div>
      )}
      <div style={{ padding: '.8rem 1rem' }}>
        <b>{video.title}</b>
        <p className="muted" style={{ margin: '.2rem 0 0' }}>{video.channel}</p>
      </div>
    </div>
  )
}

export const BookCard = ({ book, error }) => {
  if (error) return <Problem message={error} />
  if (!book) return <Empty title="No book found for this." />
  return (
    <div className="card book-card">
      {book.thumbnail && <img src={book.thumbnail} alt="" width={64} height={96} />}
      <div>
        <b>{book.title}</b>
        <p className="muted" style={{ margin: '.2rem 0' }}>
          {book.authors}{book.year ? ` · ${book.year}` : ''}</p>
        {book.blurb && (
          <p className="muted" style={{ fontSize: '.85rem' }}>
            {book.blurb.length > 220 ? book.blurb.slice(0, 220) + '…' : book.blurb}</p>
        )}
      </div>
    </div>
  )
}
