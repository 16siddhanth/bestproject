"use client"

import { BarChart3, Leaf, TrendingUp } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"

interface ClassificationResult {
  label: string
  confidence: number
  color: string
}

interface NutritionData {
  protein: number
  fiber: number
  moisture: number
  energy: number // kcal/kg
}

interface FeedRecommendation {
  animalType: string
  suitability: "High" | "Medium" | "Low"
  processingRequired: string[]
  nutritionalBenefit: string
}

interface ClassificationResultsProps {
  results?: ClassificationResult[]
  nutrition?: NutritionData
  recommendations?: FeedRecommendation[]
  isLoading?: boolean
  noVegetable?: boolean
}

export default function ClassificationResults({
  results,
  nutrition,
  recommendations,
  isLoading = false,
  noVegetable = false,
}: ClassificationResultsProps) {
  if (isLoading) {
    return (
      <div className="space-y-4 sm:space-y-6">
        <Card className="card-veggie">
          <CardHeader className="pb-3 sm:pb-6">
            <CardTitle className="flex items-center gap-2 text-base sm:text-lg">
              <BarChart3 className="h-4 w-4 sm:h-5 sm:w-5 animate-pulse" />
              Analyzing...
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="space-y-2 sm:space-y-3">
              <div className="h-3 sm:h-4 bg-muted rounded animate-pulse" />
              <div className="h-3 sm:h-4 bg-muted rounded animate-pulse w-3/4" />
              <div className="h-3 sm:h-4 bg-muted rounded animate-pulse w-1/2" />
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (noVegetable) {
    return (
      <div className="space-y-4 sm:space-y-6">
        <Card className="card-veggie">
          <CardHeader className="pb-3 sm:pb-6">
            <CardTitle className="flex items-center gap-2 text-base sm:text-lg">
              <BarChart3 className="h-4 w-4 sm:h-5 sm:w-5" />
              No vegetable detected
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="text-center text-muted-foreground py-6 sm:py-8">
              <p className="text-sm sm:text-base">Try a clearer image or different angle, then classify again.</p>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (!results) {
    return (
      <div className="space-y-4 sm:space-y-6">
        <Card className="card-veggie">
          <CardHeader className="pb-3 sm:pb-6">
            <CardTitle className="flex items-center gap-2 text-base sm:text-lg">
              <BarChart3 className="h-4 w-4 sm:h-5 sm:w-5" />
              Classification Results
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="text-center text-muted-foreground py-6 sm:py-8">
              <BarChart3 className="h-6 w-6 sm:h-8 sm:w-8 mx-auto mb-2 opacity-50" />
              <p className="text-sm sm:text-base">Capture an image to see results</p>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-4 sm:space-y-6">
      {/* Classification Results */}
      <Card className="card-veggie">
        <CardHeader className="pb-3 sm:pb-6">
          <CardTitle className="flex items-center gap-2 text-base sm:text-lg">
            <BarChart3 className="h-4 w-4 sm:h-5 sm:w-5" />
            Top Predictions
          </CardTitle>
          <CardDescription className="text-xs sm:text-sm">AI classification confidence scores</CardDescription>
        </CardHeader>
        <CardContent className="pt-0">
          <div className="space-y-3 sm:space-y-4">
            {results.map((result, index) => (
              <div key={index} className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-medium text-xs sm:text-sm truncate pr-2">{result.label}</span>
                  <Badge
                    variant={index === 0 ? "default" : "secondary"}
                    className={`text-xs flex-shrink-0 ${index === 0 ? "bg-primary text-primary-foreground" : ""}`}
                  >
                    {Math.round(result.confidence)}%
                  </Badge>
                </div>
                <Progress value={result.confidence} className="h-1.5 sm:h-2" />
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Nutrition Analysis */}
      {nutrition && (
        <Card className="card-veggie">
          <CardHeader className="pb-3 sm:pb-6">
            <CardTitle className="flex items-center gap-2 text-base sm:text-lg">
              <Leaf className="h-4 w-4 sm:h-5 sm:w-5" />
              Nutrition Analysis
            </CardTitle>
            <CardDescription className="text-xs sm:text-sm">Per 100g dry weight</CardDescription>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="grid grid-cols-2 gap-2 sm:gap-4">
              <div className="text-center p-2 sm:p-3 bg-muted rounded-lg">
                <div className="text-lg sm:text-2xl font-bold text-primary">{nutrition.protein}%</div>
                <div className="text-xs sm:text-sm text-muted-foreground">Protein</div>
              </div>
              <div className="text-center p-2 sm:p-3 bg-muted rounded-lg">
                <div className="text-lg sm:text-2xl font-bold text-secondary">{nutrition.fiber}%</div>
                <div className="text-xs sm:text-sm text-muted-foreground">Fiber</div>
              </div>
              <div className="text-center p-2 sm:p-3 bg-muted rounded-lg">
                <div className="text-lg sm:text-2xl font-bold text-chart-3">{nutrition.moisture}%</div>
                <div className="text-xs sm:text-sm text-muted-foreground">Moisture</div>
              </div>
              <div className="text-center p-2 sm:p-3 bg-muted rounded-lg">
                <div className="text-lg sm:text-2xl font-bold text-accent">{nutrition.energy}</div>
                <div className="text-xs sm:text-sm text-muted-foreground">kcal/kg</div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Feed Recommendations */}
      {recommendations && (
        <Card className="card-veggie">
          <CardHeader className="pb-3 sm:pb-6">
            <CardTitle className="flex items-center gap-2 text-base sm:text-lg">
              <TrendingUp className="h-4 w-4 sm:h-5 sm:w-5" />
              Feed Recommendations
            </CardTitle>
            <CardDescription className="text-xs sm:text-sm">Optimal animal feed applications</CardDescription>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="space-y-3 sm:space-y-4">
              {recommendations.map((rec, index) => (
                <div key={index} className="border border-border rounded-lg p-3 sm:p-4">
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-2">
                    <h4 className="font-medium text-sm sm:text-base">{rec.animalType}</h4>
                    <Badge
                      variant={
                        rec.suitability === "High" ? "default" : rec.suitability === "Medium" ? "secondary" : "outline"
                      }
                      className={`text-xs self-start sm:self-auto ${
                        rec.suitability === "High"
                          ? "bg-primary text-primary-foreground"
                          : rec.suitability === "Medium"
                            ? "bg-secondary text-secondary-foreground"
                            : ""
                      }`}
                    >
                      {rec.suitability} Suitability
                    </Badge>
                  </div>
                  <p className="text-xs sm:text-sm text-muted-foreground mb-2 leading-relaxed">
                    {rec.nutritionalBenefit}
                  </p>
                  {rec.processingRequired.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {rec.processingRequired.map((process, idx) => (
                        <Badge key={idx} variant="outline" className="text-xs">
                          {process}
                        </Badge>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
