import { NextResponse } from "next/server"

const SYSTEM_API = process.env.SYSTEM_API_URL || "http://localhost:5001"

export async function GET() {
  try {
    const res = await fetch(`${SYSTEM_API}/system/status`, {
      signal: AbortSignal.timeout(3000),
      cache: "no-store",
    })
    if (!res.ok) {
      return NextResponse.json(
        { connected: false, error: "System controller returned " + res.status },
        { status: 502 }
      )
    }
    const data = await res.json()
    return NextResponse.json({ connected: true, ...data })
  } catch {
    return NextResponse.json(
      { connected: false, error: "Cannot reach system controller at " + SYSTEM_API },
      { status: 502 }
    )
  }
}

export const dynamic = "force-dynamic"
