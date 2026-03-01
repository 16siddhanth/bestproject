import { NextResponse } from "next/server"

const PI_API_URL = process.env.PI_API_URL || "http://localhost:5000"

/**
 * Proxy the Pi's /status endpoint.
 * Returns inference results, detections (with bounding boxes), FPS, and hardware state.
 */
export async function GET() {
  try {
    const res = await fetch(`${PI_API_URL}/status`, {
      signal: AbortSignal.timeout(3000),
      cache: "no-store",
    })

    if (!res.ok) {
      return NextResponse.json(
        { connected: false, error: "Pi server returned " + res.status },
        { status: 502 },
      )
    }

    const data = await res.json()
    return NextResponse.json({ connected: true, ...data })
  } catch {
    return NextResponse.json(
      { connected: false, error: "Cannot reach Pi server at " + PI_API_URL },
      { status: 502 },
    )
  }
}

export const dynamic = "force-dynamic"
