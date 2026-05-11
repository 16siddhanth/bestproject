import { type NextRequest, NextResponse } from "next/server"

// ── Raspberry Pi YOLO11n Classification Server ────────────────
const PI_API_URL = process.env.PI_API_URL || "http://localhost:5000"

// ── Nutrition data (USDA approximate per 100g) ───────────────
const NUTRITION_DATA: Record<string, { protein: number; fiber: number; moisture: number; energy: number }> = {
  "Carrot Peels": { protein: 0.9, fiber: 2.8, moisture: 88.0, energy: 41 },
  "Potato Skins": { protein: 2.6, fiber: 2.2, moisture: 79.0, energy: 87 },
  "Onion Skins": { protein: 1.1, fiber: 1.7, moisture: 89.0, energy: 40 },
  "Tomato Skins": { protein: 0.9, fiber: 1.2, moisture: 94.0, energy: 18 },
  "Cucumber Peels": { protein: 0.7, fiber: 1.0, moisture: 95.0, energy: 15 },
  "Cabbage Leaves": { protein: 1.3, fiber: 2.5, moisture: 92.0, energy: 25 },

  "Bell Pepper Scraps": { protein: 1.0, fiber: 2.1, moisture: 92.0, energy: 31 },
  "Broccoli Stems": { protein: 2.8, fiber: 2.6, moisture: 89.0, energy: 34 },
  "Cauliflower Leaves": { protein: 1.9, fiber: 2.0, moisture: 92.0, energy: 25 },

}

// ── Feed recommendations per class ───────────────────────────
const FEED_RECOMMENDATIONS: Record<string, Array<{ animalType: string; suitability: string; processingRequired: string[]; nutritionalBenefit: string }>> = {
  "Carrot Peels": [
    { animalType: "Cattle", suitability: "High", processingRequired: ["Chopping", "Mixing with feed"], nutritionalBenefit: "Rich in beta-carotene and fiber, excellent for dairy cattle." },
    { animalType: "Poultry", suitability: "Medium", processingRequired: ["Drying", "Grinding"], nutritionalBenefit: "Good source of vitamins A and K for egg production." },
  ],
  "Potato Skins": [
    { animalType: "Pigs", suitability: "High", processingRequired: ["Cooking", "Mashing"], nutritionalBenefit: "High energy content suitable for pig fattening." },
    { animalType: "Cattle", suitability: "Medium", processingRequired: ["Chopping", "Ensiling"], nutritionalBenefit: "Starch-rich supplement for ruminant diets." },
  ],
  "Onion Skins": [
    { animalType: "Cattle", suitability: "Low", processingRequired: ["Drying", "Small quantities only"], nutritionalBenefit: "Contains quercetin antioxidants, use sparingly due to strong flavor." },
  ],
  "Tomato Skins": [
    { animalType: "Poultry", suitability: "High", processingRequired: ["Drying", "Grinding"], nutritionalBenefit: "Lycopene-rich, improves egg yolk color and antioxidant status." },
    { animalType: "Pigs", suitability: "Medium", processingRequired: ["Mixing with feed"], nutritionalBenefit: "Good palatability and vitamin C content." },
  ],
  "Cucumber Peels": [
    { animalType: "Cattle", suitability: "High", processingRequired: ["Chopping"], nutritionalBenefit: "High moisture content helps with hydration, good fiber source." },
    { animalType: "Goats", suitability: "High", processingRequired: ["Fresh feeding"], nutritionalBenefit: "Palatable and hydrating, easily digestible." },
  ],
  "Cabbage Leaves": [
    { animalType: "Cattle", suitability: "High", processingRequired: ["Chopping", "Wilting"], nutritionalBenefit: "Excellent roughage with good vitamin K content." },
    { animalType: "Poultry", suitability: "Medium", processingRequired: ["Shredding"], nutritionalBenefit: "Provides variety and micronutrients in poultry diets." },
  ],

  "Bell Pepper Scraps": [
    { animalType: "Poultry", suitability: "High", processingRequired: ["Chopping", "Removing seeds"], nutritionalBenefit: "Vitamin C-rich, supports immune function." },
    { animalType: "Pigs", suitability: "Medium", processingRequired: ["Chopping", "Mixing"], nutritionalBenefit: "Good palatability and vitamin content." },
  ],
  "Broccoli Stems": [
    { animalType: "Cattle", suitability: "High", processingRequired: ["Chopping", "Ensiling"], nutritionalBenefit: "High protein for a vegetable, supports milk production." },
    { animalType: "Goats", suitability: "High", processingRequired: ["Chopping"], nutritionalBenefit: "Nutrient-dense and palatable for goats." },
  ],
  "Cauliflower Leaves": [
    { animalType: "Cattle", suitability: "High", processingRequired: ["Chopping", "Fresh or ensiled"], nutritionalBenefit: "Good protein and fiber balance for ruminants." },
    { animalType: "Goats", suitability: "High", processingRequired: ["Fresh feeding"], nutritionalBenefit: "Readily consumed, good nutritional profile." },
  ],

}

// ── Helpers ───────────────────────────────────────────────────

function pickColorForLabel(label: string) {
  const l = label.toLowerCase()
  if (l.includes("carrot") || l.includes("orange")) return "#f97316"
  if (l.includes("leafy")) return "#22c55e"
  if (l.includes("tomato") || l.includes("pepper")) return "#ef4444"
  if (l.includes("onion")) return "#a3a3a3"
  if (l.includes("cucumber") || l.includes("broccoli") || l.includes("cabbage") || l.includes("cauliflower")) return "#16a34a"
  if (l.includes("potato")) return "#d4a574"

  return "#f59e0b"
}

// ── YOLO11n Pi Classifier (sole backend) ─────────────────────

async function callPiClassifier(imageUrl?: string, imageBase64?: string) {
  const piUrl = process.env.PI_API_URL || PI_API_URL

  try {
    // First try /classify (latest camera inference result from YOLO11n)
    const classifyRes = await fetch(`${piUrl}/classify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ imageUrl, imageBase64 }),
      signal: AbortSignal.timeout(5000),
    })

    if (classifyRes.ok) {
      const data = await classifyRes.json()
      if (data?.success && data?.classification?.top3) {
        return data
      }
    }

    // If the camera isn't running, try /classify-image (software YOLO fallback)
    if (imageBase64) {
      const imgRes = await fetch(`${piUrl}/classify-image`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ imageBase64 }),
        signal: AbortSignal.timeout(15000),
      })
      if (imgRes.ok) {
        const data = await imgRes.json()
        if (data?.success) return data
      }
    }
  } catch (err) {
    console.log("Pi YOLO11n classifier not reachable:", (err as Error).message)
  }

  return null
}

// ── Main POST handler ────────────────────────────────────────

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { imageUrl, imageBase64 } = body
    const started = Date.now()

    // Call the Raspberry Pi YOLO11n classifier (sole classification backend)
    const piResult = await callPiClassifier(imageUrl, imageBase64)

    if (!piResult?.classification?.top3 || piResult.classification.top3.length === 0) {
      return NextResponse.json(
        {
          success: false,
          error: "Classification unavailable. Ensure the Pi YOLO11n server is running at " + PI_API_URL,
        },
        { status: 502 },
      )
    }

    const top3 = piResult.classification.top3.map((item: any) => ({
      label: item.label,
      confidence: typeof item.confidence === "number" ? item.confidence : 0,
      color: item.color || pickColorForLabel(item.label),
    }))

    const primary = top3[0]
    const primaryLabel = primary.label

    // Fill in nutrition and recommendations from local lookup if not provided by Pi
    const nutrition = piResult.nutrition ?? NUTRITION_DATA[primaryLabel] ?? null
    const recommendations = piResult.recommendations?.length
      ? piResult.recommendations
      : FEED_RECOMMENDATIONS[primaryLabel] ?? []

    return NextResponse.json({
      success: true,
      classification: {
        top3,
        primaryLabel,
        confidence: primary.confidence,
      },
      nutrition: nutrition ?? undefined,
      recommendations: recommendations.length ? recommendations : undefined,
      processingTime: Date.now() - started,
      timestamp: new Date().toISOString(),
    })
  } catch (error) {
    console.error("Classification error:", error)
    return NextResponse.json({ success: false, error: "Classification failed" }, { status: 500 })
  }
}
