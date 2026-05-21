"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"

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

const ANIMAL_CONFIG: Record<
  string,
  { emoji: string; accentHue: number; gradient: string; border: string; barTrack: string }
> = {
  Cattle: {
    emoji: "🐄",
    accentHue: 35,
    gradient: "from-amber-950/60 to-amber-900/20",
    border: "border-amber-700/30",
    barTrack: "bg-amber-950/40",
  },
  Goats: {
    emoji: "🐐",
    accentHue: 150,
    gradient: "from-emerald-950/60 to-emerald-900/20",
    border: "border-emerald-700/30",
    barTrack: "bg-emerald-950/40",
  },
  Poultry: {
    emoji: "🐔",
    accentHue: 200,
    gradient: "from-sky-950/60 to-sky-900/20",
    border: "border-sky-700/30",
    barTrack: "bg-sky-950/40",
  },
  Pigs: {
    emoji: "🐷",
    accentHue: 350,
    gradient: "from-rose-950/60 to-rose-900/20",
    border: "border-rose-700/30",
    barTrack: "bg-rose-950/40",
  },
}

const NUTRIENT_DISPLAY: {
  key: string
  label: string
  unit: string
  color: string
  glowColor: string
}[] = [
  { key: "protein_g",     label: "Protein",    unit: "%",          color: "bg-blue-500",   glowColor: "shadow-blue-500/30" },
  { key: "fiber_g",       label: "Fiber",      unit: "%",          color: "bg-green-500",  glowColor: "shadow-green-500/30" },
  { key: "fat_g",         label: "Fat",        unit: "%",          color: "bg-orange-400", glowColor: "shadow-orange-400/30" },
  { key: "calcium_mg",    label: "Calcium",    unit: "mg/100g",    color: "bg-purple-500", glowColor: "shadow-purple-500/30" },
  { key: "phosphorus_mg", label: "Phosphorus", unit: "mg/100g",    color: "bg-teal-400",   glowColor: "shadow-teal-400/30" },
  { key: "calories_kcal", label: "Energy",     unit: "kcal/100g",  color: "bg-amber-500",  glowColor: "shadow-amber-500/30" },
]

/**
 * Reference bin fill target in grams DM.
 * Bars reach their full profile-match display once the bin has
 * accumulated this much dry-matter weight.
 */
const BIN_TARGET_DM_G = 50

/** Minimum DM weight before showing status indicators and target zones. */
const MIN_WEIGHT_FOR_STATUS_G = 5

/**
 * Compute how far the current value is toward the target midpoint,
 * scaled by how full the bin is (weight / BIN_TARGET_DM_G).
 * Returns 0-100 for under-target, 100 for at-target, and >100 for over.
 * Clamped at 120 for display purposes.
 */
function getNutrientProgress(value: number, target: TargetRange | undefined, weight: number): number {
  if (!target || target.max <= 0) return 0
  const mid = (target.min + target.max) / 2
  if (mid <= 0) return 0
  // Scale by how full the bin is — bars gradually fill as peels accumulate
  const weightFactor = Math.min(weight / BIN_TARGET_DM_G, 1.0)
  return Math.min(120, (value / mid) * 100 * weightFactor)
}

/**
 * Returns a status label and color based on where value sits vs target range.
 * Status is suppressed when the bin has insufficient weight to be meaningful.
 */
function getNutrientStatus(
  value: number,
  target: TargetRange | undefined,
  weight: number
): { status: "empty" | "low" | "optimal" | "high"; statusColor: string } {
  if (!target) return { status: "empty", statusColor: "text-white/30" }
  if (value <= 0) return { status: "empty", statusColor: "text-white/30" }
  // Don't show composition-based status until bin has enough material
  if (weight < MIN_WEIGHT_FOR_STATUS_G) return { status: "empty", statusColor: "text-white/30" }
  if (value < target.min) return { status: "low", statusColor: "text-yellow-400" }
  if (value <= target.max) return { status: "optimal", statusColor: "text-emerald-400" }
  return { status: "high", statusColor: "text-red-400" }
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
            className={`bg-gradient-to-br ${config.gradient} border ${config.border} transition-all duration-300 hover:border-white/20`}
          >
            <CardHeader className="pb-2 pt-3 px-4">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-semibold flex items-center gap-2">
                  <span className="text-lg">{config.emoji}</span>
                  <span className="text-white/90">{bin.animal}</span>
                  <span className="text-[10px] text-white/30 font-normal">Bin {bin.bin_id}</span>
                </CardTitle>
                <div className="flex items-center gap-1.5">
                  <Badge variant="secondary" className="text-[10px] bg-black/30 text-white/70 border-0 px-1.5 py-0.5">
                    {bin.peel_count} peels
                  </Badge>
                  <Badge variant="secondary" className="text-[10px] bg-black/30 text-white/70 border-0 font-mono px-1.5 py-0.5">
                    {weight.toFixed(1)}g DM
                  </Badge>
                </div>
              </div>
            </CardHeader>
            <CardContent className="px-4 pb-3 pt-0">
              <div className="space-y-2">
                {NUTRIENT_DISPLAY.map((nutrient) => {
                  const value = bin.nutrients_per_100g?.[nutrient.key as keyof BinNutrients] ?? 0
                  const target = bin.target_ranges?.[nutrient.key]
                  const progress = getNutrientProgress(value, target, weight)
                  const { status, statusColor } = getNutrientStatus(value, target, weight)
                  const showZone = weight >= MIN_WEIGHT_FOR_STATUS_G

                  // Target zone markers (as % of bar width, where 100% = midpoint)
                  // Scaled by weight factor so the zone grows proportionally with bar fill
                  const mid = target ? (target.min + target.max) / 2 : 1
                  const weightFactor = Math.min(weight / BIN_TARGET_DM_G, 1.0)
                  const targetMinPct = target && mid > 0 ? Math.min(100, (target.min / mid) * 100) * weightFactor : 0
                  const targetMaxPct = target && mid > 0 ? Math.min(120, (target.max / mid) * 100) * weightFactor : 0
                  // Scale to bar's 120% max
                  const barScale = 100 / 120
                  const zoneLeft = targetMinPct * barScale
                  const zoneRight = targetMaxPct * barScale

                  return (
                    <div key={nutrient.key}>
                      {/* Label row */}
                      <div className="flex items-center justify-between mb-0.5">
                        <span className="text-[10px] text-white/50 font-medium tracking-wide">
                          {nutrient.label}
                        </span>
                        <div className="flex items-center gap-1.5">
                          {status !== "empty" && (
                            <span className={`text-[9px] font-semibold uppercase tracking-wider ${statusColor}`}>
                              {status === "optimal" ? "✓" : status === "low" ? "▼" : "▲"}
                            </span>
                          )}
                          <span className="text-[10px] text-white/50 font-mono tabular-nums w-20 text-right">
                            {value.toFixed(1)}{nutrient.unit}
                          </span>
                        </div>
                      </div>
                      {/* Bar */}
                      <div className={`relative h-2 ${config.barTrack} rounded-full overflow-hidden`}>
                        {/* Target zone indicator — only visible once bin has meaningful weight */}
                        {target && value > 0 && showZone && (
                          <div
                            className="absolute top-0 bottom-0 bg-white/[0.06] border-l border-r border-white/10 rounded-sm z-0"
                            style={{
                              left: `${zoneLeft}%`,
                              width: `${Math.max(zoneRight - zoneLeft, 0)}%`,
                            }}
                          />
                        )}
                        {/* Fill bar */}
                        <div
                          className={`absolute top-0 left-0 h-full rounded-full transition-all duration-700 ease-out ${nutrient.color} ${
                            status === "optimal" && showZone ? `shadow-sm ${nutrient.glowColor}` : ""
                          }`}
                          style={{
                            width: `${Math.min(progress * barScale, 100)}%`,
                            opacity: value > 0 ? 1 : 0,
                          }}
                        />
                      </div>
                      {/* Target range label (subtle) */}
                      {target && (
                        <div className="flex justify-between mt-0.5">
                          <span className="text-[8px] text-white/20 font-mono">
                            {target.min}{nutrient.unit}
                          </span>
                          <span className="text-[8px] text-white/20 font-mono">
                            {target.max}{nutrient.unit}
                          </span>
                        </div>
                      )}
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
