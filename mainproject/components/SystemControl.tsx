"use client"

import { useState } from "react"
import { Power, Loader2, Vibrate } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"

interface SystemControlProps {
  status: string
  running: boolean
  vibrationActive: boolean
  connected: boolean
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

export default function SystemControl({
  status,
  running,
  vibrationActive,
  connected,
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
    <div className="flex items-center gap-4 flex-wrap">
      {/* Start / Stop Button */}
      <Button
        onClick={handleToggle}
        disabled={loading || !connected}
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

      {/* Vibration Motor Indicator */}
      {running && (
        <Badge
          className={`text-sm px-3 py-1.5 border-0 transition-all duration-300 ${
            vibrationActive
              ? "bg-orange-900/80 text-orange-300 animate-pulse"
              : "bg-zinc-800 text-zinc-500"
          }`}
        >
          <Vibrate className={`h-3.5 w-3.5 mr-1.5 ${vibrationActive ? "animate-bounce" : ""}`} />
          {vibrationActive ? "Vibrating" : "Vibrator Idle"}
        </Badge>
      )}

      {/* Connection Warning */}
      {!connected && (
        <Badge className="bg-red-900/60 text-red-300 text-sm px-3 py-1.5 border-0">
          System Offline
        </Badge>
      )}
    </div>
  )
}
