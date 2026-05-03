"use client"

import { useState, useEffect, useCallback, useRef } from "react"
import { Leaf, Wifi, WifiOff, Gauge } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import SystemControl from "@/components/SystemControl"
import BinStatusPanel from "@/components/BinStatusPanel"
import ClassificationLog from "@/components/ClassificationLog"
import Link from "next/link"

const SYSTEM_API = process.env.NEXT_PUBLIC_SYSTEM_API || "http://localhost:5001"
const POLL_INTERVAL = 1200 // ms

interface HwStatus {
  conveyor: string
  vibration: string
  servo: string
  scales: string
  camera: string
}

interface SystemStatus {
  connected: boolean
  status: string
  running: boolean
  camera_connected: boolean
  fps: number
  vibration_active: boolean
  hw_status: HwStatus
  bins: Record<string, any>
  recent_events: any[]
}

const DEFAULT_BINS = {
  "0": {
    animal: "Cattle", bin_id: 0, total_weight_g: 0, estimated_weight_g: 0,
    peel_count: 0,
    nutrients_per_100g: { calories_kcal: 0, protein_g: 0, fat_g: 0, fiber_g: 0, calcium_mg: 0, phosphorus_mg: 0 },
    target_ranges: {
      calories_kcal: { min: 250, max: 300 }, protein_g: { min: 12, max: 16 },
      fat_g: { min: 3, max: 5 }, fiber_g: { min: 17, max: 25 },
      calcium_mg: { min: 400, max: 800 }, phosphorus_mg: { min: 200, max: 500 },
    },
  },
  "1": {
    animal: "Goats", bin_id: 1, total_weight_g: 0, estimated_weight_g: 0,
    peel_count: 0,
    nutrients_per_100g: { calories_kcal: 0, protein_g: 0, fat_g: 0, fiber_g: 0, calcium_mg: 0, phosphorus_mg: 0 },
    target_ranges: {
      calories_kcal: { min: 250, max: 280 }, protein_g: { min: 14, max: 18 },
      fat_g: { min: 3, max: 5 }, fiber_g: { min: 15, max: 22 },
      calcium_mg: { min: 400, max: 600 }, phosphorus_mg: { min: 200, max: 400 },
    },
  },
  "2": {
    animal: "Poultry", bin_id: 2, total_weight_g: 0, estimated_weight_g: 0,
    peel_count: 0,
    nutrients_per_100g: { calories_kcal: 0, protein_g: 0, fat_g: 0, fiber_g: 0, calcium_mg: 0, phosphorus_mg: 0 },
    target_ranges: {
      calories_kcal: { min: 280, max: 320 }, protein_g: { min: 16, max: 22 },
      fat_g: { min: 3, max: 8 }, fiber_g: { min: 3, max: 5 },
      calcium_mg: { min: 800, max: 1200 }, phosphorus_mg: { min: 400, max: 600 },
    },
  },
  "3": {
    animal: "Pigs", bin_id: 3, total_weight_g: 0, estimated_weight_g: 0,
    peel_count: 0,
    nutrients_per_100g: { calories_kcal: 0, protein_g: 0, fat_g: 0, fiber_g: 0, calcium_mg: 0, phosphorus_mg: 0 },
    target_ranges: {
      calories_kcal: { min: 320, max: 360 }, protein_g: { min: 13, max: 18 },
      fat_g: { min: 5, max: 10 }, fiber_g: { min: 5, max: 8 },
      calcium_mg: { min: 500, max: 900 }, phosphorus_mg: { min: 400, max: 700 },
    },
  },
}

export default function VeggieFeedApp() {
  const [systemStatus, setSystemStatus] = useState<SystemStatus>({
    connected: false,
    status: "idle",
    running: false,
    camera_connected: false,
    fps: 0,
    vibration_active: false,
    hw_status: { conveyor: "unknown", vibration: "unknown", servo: "unknown", scales: "unknown", camera: "unknown" },
    bins: DEFAULT_BINS,
    recent_events: [],
  })
  const intervalRef = useRef<NodeJS.Timeout | null>(null)

  const pollStatus = useCallback(async () => {
    try {
      const res = await fetch("/api/system/status", { cache: "no-store" })
      if (res.ok) {
        const data = await res.json()
        setSystemStatus({
          connected: data.connected ?? true,
          status: data.status ?? "idle",
          running: data.running ?? false,
          camera_connected: data.camera_connected ?? false,
          fps: data.fps ?? 0,
          vibration_active: data.vibration_active ?? false,
          hw_status: data.hw_status ?? { conveyor: "unknown", vibration: "unknown", servo: "unknown", scales: "unknown", camera: "unknown" },
          bins: data.bins && Object.keys(data.bins).length > 0 ? data.bins : DEFAULT_BINS,
          recent_events: data.recent_events ?? [],
        })
      } else {
        setSystemStatus((prev) => ({ ...prev, connected: false }))
      }
    } catch {
      setSystemStatus((prev) => ({ ...prev, connected: false }))
    }
  }, [])

  useEffect(() => {
    pollStatus()
    intervalRef.current = setInterval(pollStatus, POLL_INTERVAL)
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [pollStatus])

  const handleStart = async () => {
    try {
      await fetch("/api/system/start", { method: "POST" })
      setTimeout(pollStatus, 500)
    } catch (e) {
      console.error("Start error:", e)
    }
  }

  const handleStop = async () => {
    try {
      await fetch("/api/system/stop", { method: "POST" })
      setTimeout(pollStatus, 500)
    } catch (e) {
      console.error("Stop error:", e)
    }
  }

  const streamUrl = systemStatus.running && systemStatus.camera_connected
    ? `${SYSTEM_API}/system/stream`
    : null

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-card/50 backdrop-blur-sm sticky top-0 z-20">
        <div className="container mx-auto px-4 py-3 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2">
            <div className="p-2 rounded-xl gradient-green">
              <Leaf className="h-5 w-5 text-white" />
            </div>
            <h1 className="text-lg font-bold text-foreground">VeggieFeed</h1>
          </Link>
          <div className="flex items-center gap-3">
            {systemStatus.connected ? (
              <Badge className="bg-emerald-900/60 text-emerald-300 border-0 text-xs flex items-center gap-1">
                <Wifi className="h-3 w-3" /> Connected
              </Badge>
            ) : (
              <Badge className="bg-red-900/60 text-red-300 border-0 text-xs flex items-center gap-1">
                <WifiOff className="h-3 w-3" /> Disconnected
              </Badge>
            )}
            {systemStatus.running && systemStatus.fps > 0 && (
              <Badge className="bg-zinc-800 text-zinc-300 border-0 text-xs flex items-center gap-1">
                <Gauge className="h-3 w-3" /> {systemStatus.fps.toFixed(1)} FPS
              </Badge>
            )}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-5">
        {/* System Control Row */}
        <div className="mb-5">
          <SystemControl
            status={systemStatus.status}
            running={systemStatus.running}
            vibrationActive={systemStatus.vibration_active}
            connected={systemStatus.connected}
            hwStatus={systemStatus.hw_status}
            onStart={handleStart}
            onStop={handleStop}
          />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          {/* Left: Camera Feed + Log (2/3) */}
          <div className="lg:col-span-2 space-y-4">
            {/* Camera Feed */}
            <Card className="bg-card/50 border-border overflow-hidden">
              <CardContent className="p-0">
                <div className="relative aspect-video bg-black">
                  {streamUrl ? (
                    <>
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={streamUrl}
                        alt="YOLO11n Camera Feed"
                        className="w-full h-full object-contain"
                      />
                      {/* Live indicator */}
                      <div className="absolute top-3 left-3 flex items-center gap-1.5">
                        <span className="relative flex h-2.5 w-2.5">
                          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                          <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-red-500"></span>
                        </span>
                        <span className="text-[10px] font-medium text-white/80 bg-black/50 px-1.5 py-0.5 rounded">
                          LIVE
                        </span>
                      </div>
                    </>
                  ) : (
                    <div className="flex items-center justify-center h-full">
                      <div className="text-center">
                        <Leaf className="h-12 w-12 text-white/10 mx-auto mb-3" />
                        <p className="text-white/30 text-sm">
                          {systemStatus.running
                            ? "Connecting to camera…"
                            : "Start the system to view camera feed"}
                        </p>
                        <p className="text-white/20 text-xs mt-1">
                          YOLO11n · IMX500 AI Camera
                        </p>
                      </div>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Classification Log */}
            <ClassificationLog events={systemStatus.recent_events} />
          </div>

          {/* Right: Bin Status (1/3) */}
          <div>
            <h3 className="text-sm font-medium text-white/60 mb-3 tracking-wide uppercase">
              Animal Feed Bins
            </h3>
            <BinStatusPanel bins={systemStatus.bins} />
          </div>
        </div>
      </main>
    </div>
  )
}
