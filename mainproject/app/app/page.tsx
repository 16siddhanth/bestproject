"use client"

import { useState } from "react"
import { Leaf, Settings, Video, Camera } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import CameraCapture from "@/components/CameraCapture"
import ClassificationResults from "@/components/ClassificationResults"
import LiveFeed from "@/components/LiveFeed"
import Link from "next/link"

interface ClassificationData {
  classification: {
    top3: Array<{ label: string; confidence: number; color: string }>
    primaryLabel: string
    confidence: number
  }
  nutrition: {
    protein: number
    fiber: number
    moisture: number
    energy: number
  }
  recommendations: Array<{
    animalType: string
    suitability: "High" | "Medium" | "Low"
    processingRequired: string[]
    nutritionalBenefit: string
  }>
}

export default function VeggieFeedApp() {
  const [classificationData, setClassificationData] = useState<ClassificationData | null>(null)
  const [isClassifying, setIsClassifying] = useState(false)

  const handleImageCapture = async (imageData: string) => {
    setIsClassifying(true)
    try {
      const response = await fetch("/api/classify-enhanced", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          imageBase64: imageData,
          userId: "guest-user",
        }),
      })

      const result = await response.json()
      if (result.success) {
        setClassificationData(result)
      } else {
        alert("Classification failed. Please try again.")
      }
    } catch (error) {
      console.error("Classification error:", error)
      alert("Classification failed. Please try again.")
    } finally {
      setIsClassifying(false)
    }
  }

  const handleImageUpload = async (file: File) => {
    const reader = new FileReader()
    reader.onload = (e) => {
      if (e.target?.result) {
        handleImageCapture(e.target.result as string)
      }
    }
    reader.readAsDataURL(file)
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-card/50">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2">
            <div className="p-2 rounded-xl gradient-green">
              <Leaf className="h-6 w-6 text-white" />
            </div>
            <h1 className="text-xl font-bold text-foreground">VeggieFeed</h1>
          </Link>
          <div className="flex items-center gap-4">
            <Badge className="bg-green-100 text-green-800 border-green-200">Demo Mode</Badge>
            <Button variant="ghost" size="sm">
              <Settings className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Camera Section */}
          <div className="lg:col-span-2">
            <Tabs defaultValue="live" className="w-full">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="text-2xl font-bold mb-1">Vegetable Waste Classification</h2>
                  <p className="text-muted-foreground">
                    Real-time YOLO11n inference with bounding boxes
                  </p>
                </div>
                <TabsList className="grid grid-cols-2 w-[200px]">
                  <TabsTrigger value="live" className="flex items-center gap-1.5">
                    <Video className="h-3.5 w-3.5" />
                    Live
                  </TabsTrigger>
                  <TabsTrigger value="capture" className="flex items-center gap-1.5">
                    <Camera className="h-3.5 w-3.5" />
                    Capture
                  </TabsTrigger>
                </TabsList>
              </div>

              <TabsContent value="live" className="mt-0">
                <LiveFeed
                  onClassification={(results) => {
                    if (results.length > 0) {
                      const primary = results[0]
                      setClassificationData({
                        classification: {
                          top3: results,
                          primaryLabel: primary.label,
                          confidence: primary.confidence,
                        },
                        nutrition: null as any,
                        recommendations: null as any,
                      })
                    }
                  }}
                  pollInterval={1500}
                />
              </TabsContent>

              <TabsContent value="capture" className="mt-0">
                <CameraCapture onImageCapture={handleImageCapture} onImageUpload={handleImageUpload} />
              </TabsContent>
            </Tabs>
          </div>

          {/* Results Section */}
          <div>
            <ClassificationResults
              results={classificationData?.classification.top3}
              nutrition={classificationData?.nutrition}
              recommendations={classificationData?.recommendations}
              isLoading={isClassifying}
            />
          </div>
        </div>
      </main>
    </div>
  )
}
