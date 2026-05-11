"use client"

import { useState, useEffect, useRef, useCallback } from "react"
import { Video, VideoOff, Wifi, WifiOff, Activity } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"

interface Detection {
  label: string
  confidence: number
  bin_id: number
  box: [number, number, number, number] // x, y, w, h
}

interface InferenceStatus {
  connected: boolean
  inference?: {
    results: Array<{ label: string; confidence: number; bin_id: number }>
    detections: Detection[]
    fps: number
    is_running: boolean
    has_frame: boolean
  }
  hardware?: {
    conveyor_state: string
    bin_counts: Record<string, number>
  } | null
}

interface LiveFeedProps {
  /** Called whenever new classification results arrive */
  onClassification?: (results: Array<{ label: string; confidence: number; color: string }>) => void
  /** Polling interval in ms (default: 1000) */
  pollInterval?: number
  /** Show hardware status overlay */
  showHardwareStatus?: boolean
}

function pickColor(label: string): string {
  const l = label.toLowerCase()
  if (l.includes("carrot")) return "#f97316"

  if (l.includes("tomato") || l.includes("pepper")) return "#ef4444"
  if (l.includes("onion")) return "#a3a3a3"
  if (l.includes("cucumber") || l.includes("broccoli") || l.includes("cabbage") || l.includes("cauliflower")) return "#16a34a"
  if (l.includes("potato")) return "#d4a574"

  return "#f59e0b"
}

export default function LiveFeed({
  onClassification,
  pollInterval = 1000,
  showHardwareStatus = true,
}: LiveFeedProps) {
  const [status, setStatus] = useState<InferenceStatus | null>(null)
  const [streamError, setStreamError] = useState(false)
  const [streamLoaded, setStreamLoaded] = useState(false)
  const imgRef = useRef<HTMLImageElement>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Poll Pi status for classification results and detection metadata
  const pollStatus = useCallback(async () => {
    try {
      const res = await fetch("/api/pi-status", { cache: "no-store" })
      const data: InferenceStatus = await res.json()
      setStatus(data)

      // Forward classification results to parent
      if (data.connected && data.inference?.results?.length && onClassification) {
        const top3 = data.inference.results.slice(0, 3).map((r) => ({
          label: r.label,
          confidence: r.confidence,
          color: pickColor(r.label),
        }))
        onClassification(top3)
      }
    } catch {
      setStatus({ connected: false })
    }
  }, [onClassification])

  useEffect(() => {
    pollStatus()
    pollRef.current = setInterval(pollStatus, pollInterval)
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [pollStatus, pollInterval])

  const isConnected = status?.connected === true
  const isRunning = status?.inference?.is_running === true
  const fps = status?.inference?.fps ?? 0
  const results = status?.inference?.results ?? []

  return (
    <Card className="card-veggie overflow-hidden">
      <CardContent className="p-0 relative">
        {/* MJPEG Stream — the Pi already draws bounding boxes on the frames */}
        <div className="relative aspect-video bg-black rounded-lg overflow-hidden">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            ref={imgRef}
            src={isConnected && isRunning ? "/api/stream" : undefined}
            alt="Live YOLO11n inference feed"
            className={`w-full h-full object-contain ${streamLoaded ? "" : "hidden"}`}
            onLoad={() => {
              setStreamLoaded(true)
              setStreamError(false)
            }}
            onError={() => {
              setStreamError(true)
              setStreamLoaded(false)
            }}
          />

          {/* Fallback when stream is not available */}
          {(!streamLoaded || streamError || !isRunning) && (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center p-4">
                {!isConnected ? (
                  <>
                    <WifiOff className="h-10 w-10 text-red-400 mx-auto mb-3" />
                    <p className="text-red-400 text-sm font-medium">Pi Server Offline</p>
                    <p className="text-muted-foreground text-xs mt-1">
                      Start the YOLO11n server: <code className="bg-white/10 px-1.5 py-0.5 rounded text-xs">python main.py</code>
                    </p>
                  </>
                ) : !isRunning ? (
                  <>
                    <VideoOff className="h-10 w-10 text-yellow-400 mx-auto mb-3" />
                    <p className="text-yellow-400 text-sm font-medium">Inference Not Running</p>
                    <p className="text-muted-foreground text-xs mt-1">Camera connected but inference engine is stopped</p>
                  </>
                ) : (
                  <>
                    <Video className="h-10 w-10 text-muted-foreground mx-auto mb-3 animate-pulse" />
                    <p className="text-muted-foreground text-sm">Connecting to stream...</p>
                  </>
                )}
              </div>
            </div>
          )}

          {/* Top-left: Connection + FPS badge */}
          <div className="absolute top-2 left-2 flex gap-2">
            <Badge
              variant="secondary"
              className={`text-xs ${isConnected ? "bg-green-900/80 text-green-300" : "bg-red-900/80 text-red-300"}`}
            >
              {isConnected ? <Wifi className="h-3 w-3 mr-1" /> : <WifiOff className="h-3 w-3 mr-1" />}
              {isConnected ? "Connected" : "Offline"}
            </Badge>
            {isRunning && (
              <Badge variant="secondary" className="text-xs bg-black/60 text-white">
                <Activity className="h-3 w-3 mr-1" />
                {fps.toFixed(1)} FPS
              </Badge>
            )}
          </div>

          {/* Top-right: Live classification results */}
          {isRunning && results.length > 0 && (
            <div className="absolute top-2 right-2 flex flex-col gap-1">
              {results.slice(0, 3).map((r, i) => (
                <Badge
                  key={i}
                  className="text-xs font-mono"
                  style={{
                    backgroundColor: `${pickColor(r.label)}CC`,
                    color: "white",
                    border: `1px solid ${pickColor(r.label)}`,
                  }}
                >
                  {r.label}: {r.confidence.toFixed(1)}%
                </Badge>
              ))}
            </div>
          )}

          {/* Bottom: Hardware status bar */}
          {showHardwareStatus && isConnected && status?.hardware && (
            <div className="absolute bottom-0 left-0 right-0 bg-black/70 px-3 py-1.5 flex items-center justify-between">
              <span className="text-xs text-white/80">
                Conveyor: <span className="font-medium text-white">{status.hardware.conveyor_state}</span>
              </span>
              {status.hardware.bin_counts && (
                <div className="flex gap-2">
                  {Object.entries(status.hardware.bin_counts).map(([bin, count]) => (
                    <span key={bin} className="text-xs text-white/80">
                      Bin {bin}: <span className="font-medium text-white">{count}</span>
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
