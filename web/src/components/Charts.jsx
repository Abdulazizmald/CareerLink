import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  ScatterChart, Scatter, ZAxis, RadialBarChart, RadialBar, LabelList,
} from 'recharts'

// Recharts defaults draw a grid, a legend, a border and an axis line. All of
// that is ink carrying no data, so it is switched off here rather than accepted.
// A legend also forces the eye between key and mark, so series are labelled
// directly instead.
const BLUE = '#1b4fd8'
const SOFT = '#a9c1f5'
const AMBER = '#e08a1e'
const INK2 = '#51607e'

const Tip = ({ active, payload, label, unit = '', fmt }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="tip">
      <b>{label ?? payload[0]?.payload?.name}</b>
      {payload.map((p) => (
        <span key={p.dataKey}>
          {p.name}: {fmt ? fmt(p.value) : p.value?.toLocaleString()}{unit}
        </span>
      ))}
    </div>
  )
}

export function Ranked({ data, xKey = 'value', yKey = 'name', unit = '', fmt, height }) {
  // Horizontal bars from a common zero, sorted. Sorting is not decoration: an
  // unordered bar chart makes the reader do the ranking.
  const rows = [...data].sort((a, b) => b[xKey] - a[xKey])
  return (
    <ResponsiveContainer width="100%" height={height ?? Math.max(180, rows.length * 34)}>
      <BarChart data={rows} layout="vertical" margin={{ left: 4, right: 46, top: 4, bottom: 4 }}>
        <XAxis type="number" hide />
        <YAxis type="category" dataKey={yKey} width={140} tickLine={false} axisLine={false} />
        <Tooltip cursor={{ fill: '#f2f6fd' }} content={<Tip unit={unit} fmt={fmt} />} />
        <Bar dataKey={xKey} radius={[0, 999, 999, 0]} fill={BLUE} maxBarSize={16}>
          <LabelList dataKey={xKey} position="right"
            formatter={(v) => (fmt ? fmt(v) : v.toLocaleString()) + unit}
            style={{ fill: INK2, fontSize: 12, fontFamily: 'DM Mono' }} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

export function Levels({ data }) {
  // Stacked, because these are parts of one whole and the whole is the point.
  // "Not stated" is its own muted band rather than being hidden, so nobody reads
  // the chart as if every advert declared a level.
  return (
    <ResponsiveContainer width="100%" height={Math.max(200, data.length * 34)}>
      <BarChart data={data} layout="vertical" margin={{ left: 4, right: 12, top: 4, bottom: 4 }}>
        <XAxis type="number" hide />
        <YAxis type="category" dataKey="category" width={140} tickLine={false} axisLine={false} />
        <Tooltip cursor={{ fill: '#f2f6fd' }} content={<Tip />} />
        <Bar dataKey="junior" stackId="a" name="Junior or mid" fill={SOFT} maxBarSize={18} />
        <Bar dataKey="senior" stackId="a" name="Senior" fill={BLUE} maxBarSize={18} />
        <Bar dataKey="lead" stackId="a" name="Lead or principal" fill="#0e1f3d" maxBarSize={18} />
        <Bar dataKey="unstated" stackId="a" name="Not stated" fill="#e2e8f4"
             radius={[0, 999, 999, 0]} maxBarSize={18} />
      </BarChart>
    </ResponsiveContainer>
  )
}

export function PayVsOpenings({ data }) {
  // Two measures at once: how many jobs there are, and what they pay. Position on
  // both axes, which is the perceptual task people read most accurately.
  return (
    <ResponsiveContainer width="100%" height={330}>
      <ScatterChart margin={{ left: 8, right: 24, top: 16, bottom: 28 }}>
        <XAxis type="number" dataKey="postings" name="Openings" tickLine={false}
               axisLine={{ stroke: '#dce3f0' }}
               label={{ value: 'Openings', position: 'insideBottom', offset: -16, fill: INK2, fontSize: 12 }} />
        <YAxis type="number" dataKey="pay" name="Median pay" tickLine={false}
               axisLine={{ stroke: '#dce3f0' }} tickFormatter={(v) => `$${v / 1000}k`} width={62} />
        <ZAxis type="number" dataKey="paidCount" range={[70, 520]} name="Adverts stating pay" />
        <Tooltip content={<Tip />} cursor={{ strokeDasharray: '3 3' }} />
        <Scatter data={data.filter((d) => d.pay != null)} fill={BLUE} fillOpacity={0.72}>
          {data.filter((d) => d.pay != null).map((d, i) => (
            <Cell key={i} fill={i === 0 ? AMBER : BLUE} />
          ))}
          <LabelList dataKey="category" position="top"
            style={{ fill: INK2, fontSize: 11, fontFamily: 'Public Sans' }} />
        </Scatter>
      </ScatterChart>
    </ResponsiveContainer>
  )
}

export function Dial({ value, label }) {
  return (
    <ResponsiveContainer width="100%" height={150}>
      <RadialBarChart innerRadius="66%" outerRadius="100%" startAngle={210} endAngle={-30}
        data={[{ name: label, value, fill: BLUE }]}>
        <RadialBar background={{ fill: '#e7ecf7' }} dataKey="value" cornerRadius={999} />
      </RadialBarChart>
    </ResponsiveContainer>
  )
}
