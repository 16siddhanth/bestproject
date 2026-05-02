"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"

interface BinNutrients {
  calories_kcal: number
  protein_g: number
  fat_g: number
  fiber_g: number
  calcium_mg: number
  phosphorus_mg: number
}

interface TargetRange {
  min: number
  max: number
}

interface BinData {
  animal: string
  bin_id: number
  total_weight_g: number
  estimated_weight_g: number
  peel_count: number
  nutrients_per_100g: BinNutrients
  target_ranges: Record<string, TargetRange>
}

interface BinStatusPanelProps {
  bins: Record<string, BinData>
}

const ANIMAL_CONFIG: Record<string, { emoji: string; gradient: string; border: string }> = {
  Cattle: { emoji: "🐄", gradient: "from-amber-950/60 to-amber-900/30", border: "border-amber-800/40" },
  Goats: { emoji: "🐐", gradient: "from-emerald-950/60 to-emerald-900/30", border: "border-emerald-800/40" },
  Poultry: { emoji: "🐔", gradient: "from-sky-950/60 to-sky-900/30", border: "border-sky-800/40" },
  Pigs: { emoji: "🐷", gradient: "from-rose-950/60 to-rose-900/30", border: "border-rose-800/40" },
}

const NUTRIENT_DISPLAY: Record<string, { label: string; unit: string; color: string }> = {
  protein_g: { label: "Protein", unit: "g", color: "bg-blue-500" },
  fiber_g: { label: "Fiber", unit: "g", color: "bg-green-500" },
  calcium_mg: { label: "Calcium", unit: "mg", color: "bg-purple-500" },
  calories_kcal: { label: "Energy", unit: "kcal", color: "bg-amber-500" },
}

function getNutrientProgress(value: number, target: TargetRange | undefined): number {
  if (!target || target.max <= 0) return 0
  const mid = (target.min + target.max) / 2
  return Math.min(100, (value / mid) * 100)
}

export default function BinStatusPanel({ bins }: BinStatusPanelProps) {
  const binEntries = Object.values(bins).sort((a, b) => a.bin_id - b.bin_id)

  return (
    <div className="grid grid-cols-1 gap-3">
      {binEntries.map((bin) => {
        const config = ANIMAL_CONFIG[bin.animal] || ANIMAL_CONFIG.Cattle
        const weight = bin.total_weight_g > 0 ? bin.total_weight_g : bin.estimated_weight_g

        return (
          <Card
            key={bin.bin_id}
            className={`bg-gradient-to-br ${config.gradient} border ${config.border} transition-all duration-300`}
          >
            <CardHeader className="pb-2 pt-3 px-4">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-semibold flex items-center gap-2">
                  <span className="text-lg">{config.emoji}</span>
                  <span className="text-white/90">{bin.animal}</span>
                </CardTitle>
                <div className="flex items-center gap-2">
                  <Badge variant="secondary" className="text-xs bg-black/30 text-white/80 border-0">
                    {bin.peel_count} peels
                  </Badge>
                  <Badge variant="secondary" className="text-xs bg-black/30 text-white/80 border-0 font-mono">
                    {weight.toFixed(0)}g
                  </Badge>
                </div>
              </div>
            </CardHeader>
            <CardContent className="px-4 pb-3 pt-0">
              <div className="space-y-1.5">
                {Object.entries(NUTRIENT_DISPLAY).map(([key, display]) => {
                  const value = bin.nutrients_per_100g?.[key as keyof BinNutrients] ?? 0
                  const target = bin.target_ranges?.[key]
                  const progress = getNutrientProgress(value, target)

                  return (
                    <div key={key} className="flex items-center gap-2">
                      <span className="text-[10px] text-white/50 w-12 truncate">{display.label}</span>
                      <div className="flex-1 h-1.5 bg-white/10 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all duration-500 ${display.color}`}
                          style={{ width: `${Math.min(progress, 100)}%` }}
                        />
                      </div>
                      <span className="text-[10px] text-white/40 w-14 text-right font-mono">
                        {value.toFixed(1)}{display.unit}
                      </span>
                    </div>
                  )
                })}
              </div>
            </CardContent>
          </Card>
        )
      })}
    </div>
  )
}
