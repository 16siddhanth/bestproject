import { NextResponse } from "next/server"

const SYSTEM_API = process.env.SYSTEM_API_URL || "http://localhost:5001"

/**
 * Proxy the MJPEG stream from the system controller.
 */
export async function GET() {
  try {
    const res = await fetch(`${SYSTEM_API}/system/stream`, {
      signal: AbortSignal.timeout(5000),
      // @ts-expect-error — Next.js extended RequestInit
      cache: "no-store",
    })

    if (!res.ok || !res.body) {
      return NextResponse.json(
        { error: "Stream not available from system controller" },
        { status: 502 }
      )
    }

    return new Response(res.body, {
      headers: {
        "Content-Type": res.headers.get("Content-Type") || "multipart/x-mixed-replace; boundary=frame",
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Connection": "keep-alive",
      },
    })
  } catch {
    return NextResponse.json(
      { error: "Cannot connect to system controller at " + SYSTEM_API },
      { status: 502 }
    )
  }
}

export const dynamic = "force-dynamic"
