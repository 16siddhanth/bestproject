"use client"

import { useState } from "react"
import { Power, Loader2, Vibrate, Cog, Scale, Camera, CircleDot } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"

interface HwStatus {
  belt: string
  vibration: string
  servo: string
  scales: string
  camera: string
}

interface SystemControlProps {
  status: string
  running: boolean
  vibrationActive: boolean
  connected: boolean
  hwStatus?: HwStatus
  onStart: () => void
  onStop: () => void
}

const STATUS_LABELS: Record<string, { text: string; color: string }> = {
  idle: { text: "Idle", color: "bg-zinc-700 text-zinc-300" },
  running: { text: "Running", color: "bg-emerald-900/80 text-emerald-300" },
  detecting: { text: "Object Detected", color: "bg-amber-900/80 text-amber-300" },
  classifying: { text: "Classifying…", color: "bg-blue-900/80 text-blue-300" },
  sorting: { text: "Sorting", color: "bg-purple-900/80 text-purple-300" },
  stopping: { text: "Stopping…", color: "bg-red-900/80 text-red-300" },
}

const HW_ICONS: Record<string, React.ReactNode> = {
  belt: <Cog className="h-3 w-3" />,
  vibration: <Vibrate className="h-3 w-3" />,
  servo: <CircleDot className="h-3 w-3" />,
  scales: <Scale className="h-3 w-3" />,
  camera: <Camera className="h-3 w-3" />,
}

const HW_LABELS: Record<string, string> = {
  belt: "Belt",
  vibration: "Vibrator",
  servo: "Servo",
  scales: "Scales",
  camera: "Camera",
}

export default function SystemControl({
  status,
  running,
  vibrationActive,
  connected,
  hwStatus,
  onStart,
  onStop,
}: SystemControlProps) {
  const [loading, setLoading] = useState(false)

  const handleToggle = async () => {
    setLoading(true)
    try {
      if (running) {
        onStop()
      } else {
        onStart()
      }
    } finally {
      setTimeout(() => setLoading(false), 1500)
    }
  }

  const statusInfo = STATUS_LABELS[status] || STATUS_LABELS.idle

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-4 flex-wrap">
        {/* Start / Stop Button */}
        <Button
          onClick={handleToggle}
          disabled={loading}
          size="lg"
          className={`
            relative h-14 px-8 rounded-2xl text-base font-semibold tracking-wide
            transition-all duration-300 shadow-lg
            ${running
              ? "bg-red-600 hover:bg-red-700 text-white shadow-red-900/40"
              : "bg-emerald-600 hover:bg-emerald-700 text-white shadow-emerald-900/40"
            }
            ${running && !loading ? "animate-pulse-subtle" : ""}
            disabled:opacity-50
          `}
        >
          {loading ? (
            <Loader2 className="h-5 w-5 animate-spin mr-2" />
          ) : (
            <Power className="h-5 w-5 mr-2" />
          )}
          {loading ? (running ? "Stopping…" : "Starting…") : running ? "Stop System" : "Start System"}
        </Button>

        {/* Status Badge */}
        <Badge className={`${statusInfo.color} text-sm px-3 py-1.5 border-0`}>
          {statusInfo.text}
        </Badge>

        {/* Vibration Motor Active Indicator */}
        {running && vibrationActive && (
          <Badge
            className="text-sm px-3 py-1.5 border-0 bg-orange-900/80 text-orange-300 animate-pulse"
          >
            <Vibrate className="h-3.5 w-3.5 mr-1.5 animate-bounce" />
            Vibrating
          </Badge>
        )}

        {/* Backend Unreachable */}
        {!connected && (
          <Badge className="bg-red-900/60 text-red-300 text-sm px-3 py-1.5 border-0">
            Backend Unreachable
          </Badge>
        )}
      </div>

      {/* Per-component hardware status chips */}
      {running && hwStatus && (
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-[11px] text-white/40 mr-1">Hardware:</span>
          {Object.entries(hwStatus).map(([key, val]) => {
            const isActive = val === "active"
            return (
              <Badge
                key={key}
                className={`text-[10px] px-2 py-0.5 border-0 flex items-center gap-1
                  ${isActive
                    ? "bg-emerald-900/50 text-emerald-400"
                    : "bg-zinc-800/80 text-zinc-500"
                  }`}
              >
                {HW_ICONS[key]}
                {HW_LABELS[key] || key}
                <span className={`ml-0.5 inline-block h-1.5 w-1.5 rounded-full ${isActive ? "bg-emerald-400" : "bg-zinc-600"}`} />
              </Badge>
            )
          })}
        </div>
      )}
    </div>
  )
}
