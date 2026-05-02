import { NextResponse } from "next/server"

const SYSTEM_API = process.env.SYSTEM_API_URL || "http://localhost:5001"

export async function POST() {
  try {
    const res = await fetch(`${SYSTEM_API}/system/start`, {
      method: "POST",
      signal: AbortSignal.timeout(5000),
    })
    const data = await res.json()
    return NextResponse.json(data)
  } catch {
    return NextResponse.json(
      { success: false, error: "Cannot reach system controller at " + SYSTEM_API },
      { status: 502 }
    )
  }
}

export const dynamic = "force-dynamic"
