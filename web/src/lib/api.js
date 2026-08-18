// One place that knows how to reach the backend.
// Every page uses useApi, so loading and error states look the same everywhere
// and a failed fetch never renders as an empty page pretending to be a result.
import { useEffect, useState } from 'react'

export async function get(path) {
  const res = await fetch(`/api${path}`)
  if (!res.ok) throw new Error(`The server returned ${res.status}`)
  return res.json()
}

export function useApi(path, deps = []) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let live = true
    setLoading(true)
    setError(null)
    get(path)
      .then((d) => live && setData(d))
      .catch((e) => live && setError(e.message))
      .finally(() => live && setLoading(false))
    return () => { live = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  return { data, error, loading }
}

export const money = (v) =>
  v == null ? null : `$${Math.round(Number(v)).toLocaleString()}`
export const num = (v) => (v == null ? '0' : Number(v).toLocaleString())
