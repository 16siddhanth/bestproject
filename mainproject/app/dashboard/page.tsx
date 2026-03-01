"use client"

import { useState, useEffect } from "react"
import { Leaf, Settings, LogOut, BarChart3, Camera, Users, TrendingUp, Video } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import CameraCapture from "@/components/CameraCapture"
import ClassificationResults from "@/components/ClassificationResults"
import LiveFeed from "@/components/LiveFeed"
import Link from "next/link"
import { useRouter } from "next/navigation"

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

export default function Dashboard() {
  const [classificationData, setClassificationData] = useState<ClassificationData | null>(null)
  const [isClassifying, setIsClassifying] = useState(false)
  const [noVegetable, setNoVegetable] = useState(false)
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const router = useRouter()

  useEffect(() => {
    // Check authentication status
    const authStatus = localStorage.getItem("veggiefeed_auth")
    if (!authStatus) {
      router.push("/auth/login")
    } else {
      setIsAuthenticated(true)
    }
  }, [router])

  const handleLogout = () => {
    localStorage.removeItem("veggiefeed_auth")
    router.push("/")
  }

  const handleImageCapture = async (imageData: string) => {
    setIsClassifying(true)
    setNoVegetable(false)
    try {
      const response = await fetch("/api/classify-enhanced", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          imageBase64: imageData,
          userId: "authenticated-user",
        }),
      })

      const result = await response.json()
      if (result.success) {
        // Detect a no-vegetable case: empty top3 or low confidence top-1
        const top3 = result?.classification?.top3 || []
        const top1 = top3[0]
        const lowConfidence = top1?.confidence !== undefined ? top1.confidence < 30 : true
        const invalidLabel = typeof top1?.label !== "string" || !top1.label

        if (!top3.length || lowConfidence || invalidLabel) {
          setNoVegetable(true)
          setClassificationData(null)
        } else {
          setNoVegetable(false)
          setClassificationData(result)
        }
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

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-muted-foreground">Loading...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-card/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-3 sm:py-4 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2">
            <div className="p-1.5 sm:p-2 rounded-xl gradient-green">
              <Leaf className="h-5 w-5 sm:h-6 sm:w-6 text-white" />
            </div>
            <h1 className="text-lg sm:text-xl font-bold text-foreground">VeggieFeed</h1>
          </Link>
          <div className="flex items-center gap-2 sm:gap-4">
            <Badge className="bg-green-100 text-green-800 border-green-200 text-xs sm:text-sm px-2 sm:px-3">
              Pro Account
            </Badge>
            <Button variant="ghost" size="sm" className="p-2">
              <Settings className="h-4 w-4" />
            </Button>
            <Button variant="ghost" size="sm" onClick={handleLogout} className="p-2">
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </header>

      {/* Dashboard Content */}
      <main className="container mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8">
        {/* Welcome Section */}
        <div className="mb-6 sm:mb-8">
          <h1 className="text-2xl sm:text-3xl font-bold mb-2">Welcome back!</h1>
          <p className="text-muted-foreground text-sm sm:text-base">
            Ready to optimize your feed management with AI-powered analysis.
          </p>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 lg:gap-6 mb-6 sm:mb-8">
          <Card className="card-green border-green-200">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2 px-3 sm:px-6 pt-3 sm:pt-6">
              <CardTitle className="text-xs sm:text-sm font-medium text-green-800">Classifications Today</CardTitle>
              <Camera className="h-3 w-3 sm:h-4 sm:w-4 text-green-600" />
            </CardHeader>
            <CardContent className="px-3 sm:px-6 pb-3 sm:pb-6">
              <div className="text-xl sm:text-2xl font-bold text-green-800">24</div>
              <p className="text-xs text-green-600">+12% from yesterday</p>
            </CardContent>
          </Card>

          <Card className="card-green border-green-200">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2 px-3 sm:px-6 pt-3 sm:pt-6">
              <CardTitle className="text-xs sm:text-sm font-medium text-green-800">Feed Efficiency</CardTitle>
              <TrendingUp className="h-3 w-3 sm:h-4 sm:w-4 text-green-600" />
            </CardHeader>
            <CardContent className="px-3 sm:px-6 pb-3 sm:pb-6">
              <div className="text-xl sm:text-2xl font-bold text-green-800">94%</div>
              <p className="text-xs text-green-600">+2% this week</p>
            </CardContent>
          </Card>

          <Card className="card-green border-green-200">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2 px-3 sm:px-6 pt-3 sm:pt-6">
              <CardTitle className="text-xs sm:text-sm font-medium text-green-800">Waste Reduced</CardTitle>
              <BarChart3 className="h-3 w-3 sm:h-4 sm:w-4 text-green-600" />
            </CardHeader>
            <CardContent className="px-3 sm:px-6 pb-3 sm:pb-6">
              <div className="text-xl sm:text-2xl font-bold text-green-800">1.2t</div>
              <p className="text-xs text-green-600">This month</p>
            </CardContent>
          </Card>

          <Card className="card-green border-green-200">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2 px-3 sm:px-6 pt-3 sm:pt-6">
              <CardTitle className="text-xs sm:text-sm font-medium text-green-800">Animals Fed</CardTitle>
              <Users className="h-3 w-3 sm:h-4 sm:w-4 text-green-600" />
            </CardHeader>
            <CardContent className="px-3 sm:px-6 pb-3 sm:pb-6">
              <div className="text-xl sm:text-2xl font-bold text-green-800">156</div>
              <p className="text-xs text-green-600">Across 3 farms</p>
            </CardContent>
          </Card>
        </div>

        {/* Main Classification Interface */}
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 sm:gap-8">
          {/* Camera Section with Tabs: Live Feed vs Manual Capture */}
          <div className="xl:col-span-2">
            <Tabs defaultValue="live" className="w-full">
              <div className="flex items-center justify-between mb-4 sm:mb-6">
                <div>
                  <h2 className="text-xl sm:text-2xl font-bold mb-1">Vegetable Waste Classification</h2>
                  <p className="text-muted-foreground text-sm sm:text-base leading-relaxed">
                    Real-time YOLO11n inference with bounding boxes and classification
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

              {/* Live Feed Tab — shows MJPEG stream from Pi with bounding boxes */}
              <TabsContent value="live" className="mt-0">
                <LiveFeed
                  onClassification={(results) => {
                    if (results.length > 0) {
                      const primary = results[0]
                      setNoVegetable(false)
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

              {/* Manual Capture Tab — browser camera snapshot */}
              <TabsContent value="capture" className="mt-0">
                <CameraCapture onImageCapture={handleImageCapture} onImageUpload={handleImageUpload} />
              </TabsContent>
            </Tabs>
          </div>

          {/* Results Section */}
          <div className="xl:col-span-1">
            <ClassificationResults
              results={classificationData?.classification.top3}
              nutrition={classificationData?.nutrition}
              recommendations={classificationData?.recommendations}
              isLoading={isClassifying}
              noVegetable={noVegetable}
            />
          </div>
        </div>
      </main>
    </div>
  )
}
