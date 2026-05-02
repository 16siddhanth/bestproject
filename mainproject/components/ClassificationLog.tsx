"use client"

import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ClipboardList } from "lucide-react"

interface PeelEntry {
  label: string
  confidence: number
  count: number
}

interface ClassificationEventData {
  timestamp: number
  peels: PeelEntry[]
  estimated_weight_g: number
  assigned_bin: number
  assigned_animal: string
}

interface ClassificationLogProps {
  events: ClassificationEventData[]
}

const ANIMAL_COLORS: Record<string, string> = {
  Cattle: "bg-amber-900/60 text-amber-300",
  Goats: "bg-emerald-900/60 text-emerald-300",
  Poultry: "bg-sky-900/60 text-sky-300",
  Pigs: "bg-rose-900/60 text-rose-300",
}

function formatTime(ts: number): string {
  const d = new Date(ts * 1000)
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })
}

export default function ClassificationLog({ events }: ClassificationLogProps) {
  const reversed = [...events].reverse()

  return (
    <Card className="bg-card/50 border-border">
      <CardHeader className="pb-2 pt-3 px-4">
        <CardTitle className="text-sm font-medium flex items-center gap-2 text-white/80">
          <ClipboardList className="h-4 w-4" />
          Classification Log
          {events.length > 0 && (
            <Badge variant="secondary" className="text-[10px] bg-white/10 text-white/50 border-0 ml-auto">
              {events.length} events
            </Badge>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="px-4 pb-3 pt-0">
        {reversed.length === 0 ? (
          <div className="text-center py-6 text-white/30 text-xs">
            No classifications yet. Start the system to begin sorting.
          </div>
        ) : (
          <div className="max-h-[240px] overflow-y-auto space-y-1.5 pr-1 scrollbar-thin">
            {reversed.map((event, i) => {
              const peelSummary = event.peels
                .map((p) => `${p.label}${p.count > 1 ? ` ×${p.count}` : ""}`)
                .join(", ")
              const topConf = event.peels[0]?.confidence ?? 0
              const animalColor = ANIMAL_COLORS[event.assigned_animal] || ANIMAL_COLORS.Cattle

              return (
                <div
                  key={`${event.timestamp}-${i}`}
                  className="flex items-start gap-2 py-1.5 px-2 rounded-md bg-white/[0.03] hover:bg-white/[0.06] transition-colors"
                >
                  <span className="text-[10px] text-white/30 font-mono mt-0.5 w-16 flex-shrink-0">
                    {formatTime(event.timestamp)}
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="text-xs text-white/70 truncate">{peelSummary}</div>
                    <div className="flex items-center gap-1.5 mt-0.5">
                      <span className="text-[10px] text-white/40">
                        {topConf.toFixed(0)}% · {event.estimated_weight_g.toFixed(0)}g
                      </span>
                    </div>
                  </div>
                  <Badge className={`text-[10px] border-0 flex-shrink-0 ${animalColor}`}>
                    {event.assigned_animal}
                  </Badge>
                </div>
              )
            })}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
