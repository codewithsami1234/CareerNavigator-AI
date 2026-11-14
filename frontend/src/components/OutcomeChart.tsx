import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"
import type { CareerReport } from "../types"
import { Card } from "./ui"

const CHART_COLORS = ["#668B70", "#D9A441", "#C96F68", "#746B5D"]

export function OutcomeChart({ career }: { career: CareerReport | null }) {
  const comparison = career?.comparison
  if (!comparison) return null
  const rows = [
    { name: "Matched", count: comparison.matched_count ?? 0 },
    { name: "Related", count: comparison.related_count ?? 0 },
    { name: "Missing", count: comparison.missing_count ?? 0 },
    { name: "Indeterminate", count: comparison.indeterminate_count ?? 0 },
  ]
  return (
    <Card>
      <h2 className="font-semibold">Requirement outcomes</h2>
      <p className="mt-1 text-sm text-slate-500">Counts from the comparison object. This chart is not a hiring rate.</p>
      <ul className="sr-only">
        {rows.map((row) => <li key={row.name}>{row.name}: {row.count}</li>)}
      </ul>
      <div className="mt-4 h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="name" tick={{ fontSize: 12 }} />
            <YAxis allowDecimals={false} width={32} tick={{ fontSize: 12 }} />
            <Tooltip />
            <Bar dataKey="count" radius={[6, 6, 0, 0]}>
              {rows.map((row, index) => <Cell key={row.name} fill={CHART_COLORS[index]} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  )
}
