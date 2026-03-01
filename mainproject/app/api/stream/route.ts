import { NextResponse } from "next/server"

const PI_API_URL = process.env.PI_API_URL || "http://localhost:5000"

/**
 * Proxy the MJPEG video stream from the Pi YOLO11n inference server.
 * The frontend uses this as: <img src="/api/stream" />
 */
export async function GET() {
  try {
    const res = await fetch(`${PI_API_URL}/stream`, {
      signal: AbortSignal.timeout(5000),
      // @ts-expect-error — Next.js extended RequestInit
      cache: "no-store",
    })

    if (!res.ok || !res.body) {
      return NextResponse.json(
        { error: "Stream not available. Is the Pi YOLO11n server running?" },
        { status: 502 },
      )
    }

    // Forward the MJPEG multipart stream directly
    return new Response(res.body, {
      headers: {
        "Content-Type": res.headers.get("Content-Type") || "multipart/x-mixed-replace; boundary=frame",
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Connection": "keep-alive",
      },
    })
  } catch (err) {
    return NextResponse.json(
      { error: "Cannot connect to Pi server at " + PI_API_URL },
      { status: 502 },
    )
  }
}

export const dynamic = "force-dynamic"
