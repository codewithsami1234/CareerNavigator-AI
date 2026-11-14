import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"
import { groupSkills } from "../evidence"
import type { DetectedSkill } from "../types"
import { Card } from "./ui"

export function SkillCategoryChart({ skills }: { skills: DetectedSkill[] }) {
  const groups = groupSkills(skills)
  if (groups.length === 0) return null
  const rows = groups.map(([name, items]) => ({ name, count: items.length }))
  return (
    <Card>
      <h2 className="font-semibold">Skills by category</h2>
      <p className="mt-1 text-sm text-slate-500">Counts of taxonomy skills extracted from the latest resume. This is not a proficiency chart.</p>
      <ul className="sr-only">
        {rows.map((row) => <li key={row.name}>{row.name}: {row.count}</li>)}
      </ul>
      <div className="mt-4 h-72 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} layout="vertical" margin={{ top: 8, right: 16, left: 8, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" horizontal={false} />
            <XAxis type="number" allowDecimals={false} tick={{ fontSize: 12 }} />
            <YAxis type="category" dataKey="name" width={148} tick={{ fontSize: 11 }} />
            <Tooltip />
            <Bar dataKey="count" fill="#B88746" radius={[0, 6, 6, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  )
}
