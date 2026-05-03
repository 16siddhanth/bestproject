import { NextResponse } from "next/server"

const SYSTEM_API = process.env.SYSTEM_API_URL || "http://localhost:5001"

/**
 * Proxy the MJPEG stream from the system controller.
 * MJPEG is a long-lived connection — no timeout on the stream itself.
 * We only timeout the initial connection (5s).
 */
export async function GET() {
  try {
    // Use a short timeout only for the initial TCP connection,
    // not for the ongoing MJPEG stream.
    const controller = new AbortController()
    const connectTimeout = setTimeout(() => controller.abort(), 5000)

    const res = await fetch(`${SYSTEM_API}/system/stream`, {
      signal: controller.signal,
      // @ts-expect-error — Next.js extended RequestInit
      cache: "no-store",
    })

    clearTimeout(connectTimeout)

    if (!res.ok || !res.body) {
      return NextResponse.json(
        { error: "Stream not available from system controller" },
        { status: 502 }
      )
    }

    // Stream the response body through without buffering
    return new Response(res.body, {
      headers: {
        "Content-Type": res.headers.get("Content-Type") || "multipart/x-mixed-replace; boundary=frame",
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Connection": "keep-alive",
      },
    })
  } catch {
    return NextResponse.json(
      { error: "Cannot connect to system controller stream" },
      { status: 502 }
    )
  }
}

export const dynamic = "force-dynamic"
