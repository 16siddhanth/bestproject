import { NextResponse } from "next/server"
import { vegetableClasses } from "@/lib/classes"

export async function GET() {
  return NextResponse.json({
    classes: vegetableClasses,
    count: vegetableClasses.length,
    timestamp: new Date().toISOString(),
  })
}
