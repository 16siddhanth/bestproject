"use client"

import type React from "react"

import { useState, useRef, useCallback, useEffect } from "react"
import { Camera, Upload, X, Check } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"

interface CameraCaptureProps {
  onImageCapture: (imageData: string) => void
  onImageUpload: (file: File) => void
}

export default function CameraCapture({ onImageCapture, onImageUpload }: CameraCaptureProps) {
  const [isStreaming, setIsStreaming] = useState(false)
  const [capturedImage, setCapturedImage] = useState<string | null>(null)
  const [showPreview, setShowPreview] = useState(false)
  const [cameraError, setCameraError] = useState<string | null>(null)
  const [isStarting, setIsStarting] = useState(true)
  const [hasStream, setHasStream] = useState(false)
  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([])
  const [selectedDeviceId, setSelectedDeviceId] = useState<string | undefined>(undefined)

  const startCamera = useCallback(async () => {
    try {
      setIsStarting(true)
      setCameraError(null)
      
      // Stop any existing stream first
      if (videoRef.current?.srcObject) {
        const stream = videoRef.current.srcObject as MediaStream
        stream.getTracks().forEach((track) => track.stop())
        videoRef.current.srcObject = null
      }
      
      // Try a few constraint fallbacks for broader compatibility
      const tryConstraints = async () => {
        const attempts: MediaStreamConstraints[] = [
          // If a specific device is selected, try it first
          selectedDeviceId ? { video: { deviceId: { exact: selectedDeviceId } } } : { video: { width: { ideal: 1280, min: 640 }, height: { ideal: 720, min: 480 }, facingMode: { ideal: "environment" } } },
          { video: { width: { ideal: 1280, min: 640 }, height: { ideal: 720, min: 480 }, facingMode: { ideal: "user" } } },
          { video: true },
        ]
        let lastErr: any
        for (const c of attempts) {
          try {
            return await navigator.mediaDevices.getUserMedia(c)
          } catch (e) {
            lastErr = e
            console.warn("getUserMedia failed, trying next constraints", c, e)
          }
        }
        throw lastErr
      }

      const stream = await tryConstraints()

      // Save stream immediately and mark available so video can render
      streamRef.current = stream
      setHasStream(true)
      setIsStarting(false)
      
      // If video is already mounted, bind and try play
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        try {
          await videoRef.current.play()
        } catch (playError) {
          console.warn("video.play() was blocked or failed; relying on canplay event", playError)
        }
      }
    } catch (error) {
      console.error("Error accessing camera:", error)
      setCameraError(`Unable to access camera: ${error instanceof Error ? error.message : 'Unknown error'}`)
      setIsStarting(false)
    }
  }, [selectedDeviceId])

  // Whenever we have a stream and the video element mounts/changes, bind the stream
  useEffect(() => {
    if (videoRef.current && streamRef.current && videoRef.current.srcObject !== streamRef.current) {
      videoRef.current.srcObject = streamRef.current
      videoRef.current.play().catch((e) => console.warn("video.play() failed in effect", e))
    }
  }, [hasStream])

  // Auto-start camera when component mounts
  useEffect(() => {
    let timeoutId: NodeJS.Timeout
    
    const initCamera = async () => {
      // Check if camera is available first
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        setCameraError("Camera not supported in this browser")
        setIsStarting(false)
        return
      }

      // Enumerate devices so user can switch if needed
      try {
        const list = await navigator.mediaDevices.enumerateDevices()
        const vids = list.filter((d) => d.kind === "videoinput")
        setDevices(vids)
        // Restore last device
        const saved = typeof window !== "undefined" ? localStorage.getItem("veggiefeed_camera_device") : null
        if (saved) setSelectedDeviceId(saved)
      } catch (e) {
        console.warn("enumerateDevices failed", e)
      }
      
      // Small delay to ensure component is fully mounted
      timeoutId = setTimeout(() => {
        startCamera()
      }, 100)
    }
    
    initCamera()
    
    return () => {
      clearTimeout(timeoutId)
      // Cleanup camera stream
      if (videoRef.current?.srcObject) {
        const stream = videoRef.current.srcObject as MediaStream
        stream.getTracks().forEach((track) => track.stop())
        videoRef.current.srcObject = null
      }
    }
  }, [startCamera])

  const stopCamera = useCallback(() => {
    if (videoRef.current?.srcObject) {
      const stream = videoRef.current.srcObject as MediaStream
      stream.getTracks().forEach((track) => track.stop())
      videoRef.current.srcObject = null
      setIsStreaming(false)
    }
  }, [])

  // One-tap classify: capture and immediately send upstream
  const classifyNow = useCallback(() => {
    if (videoRef.current && canvasRef.current && (isStreaming || hasStream)) {
      const canvas = canvasRef.current
      const video = videoRef.current
      canvas.width = video.videoWidth
      canvas.height = video.videoHeight
      const ctx = canvas.getContext("2d")
      if (ctx) {
        ctx.drawImage(video, 0, 0)
        const imageData = canvas.toDataURL("image/jpeg", 0.8)
        onImageCapture(imageData)
      }
    }
  }, [onImageCapture, isStreaming, hasStream])

  const captureImage = useCallback(() => {
    if (videoRef.current && canvasRef.current && (isStreaming || hasStream)) {
      const canvas = canvasRef.current
      const video = videoRef.current

      canvas.width = video.videoWidth
      canvas.height = video.videoHeight

      const ctx = canvas.getContext("2d")
      if (ctx) {
        ctx.drawImage(video, 0, 0)
        const imageData = canvas.toDataURL("image/jpeg", 0.8)
        setCapturedImage(imageData)
        setShowPreview(true)
        // Don't stop camera - keep it running
      }
    }
  }, [isStreaming, hasStream])

  const confirmCapture = useCallback(() => {
    if (capturedImage) {
      onImageCapture(capturedImage)
      setShowPreview(false)
      setCapturedImage(null)
    }
  }, [capturedImage, onImageCapture])

  const retakePhoto = useCallback(() => {
    setCapturedImage(null)
    setShowPreview(false)
    // Camera is already running, no need to restart
  }, [])

  const handleFileUpload = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0]
      if (file && file.type.startsWith("image/")) {
        onImageUpload(file)
        // Reset file input
        if (fileInputRef.current) {
          fileInputRef.current.value = ""
        }
      }
    },
    [onImageUpload],
  )

  return (
    <Card className="card-veggie">
      <CardContent className="p-4 sm:p-6">
        <div className="relative aspect-video bg-muted rounded-lg overflow-hidden mb-4 sm:mb-6">
          {showPreview && capturedImage ? (
            // Preview captured image
            <img
              src={capturedImage || "/placeholder.svg"}
              alt="Captured vegetable waste"
              className="w-full h-full object-cover"
            />
          ) : hasStream ? (
            // Live camera feed with overlay classify button
            <>
              <video 
                ref={videoRef} 
                autoPlay 
                playsInline 
                muted 
                className="w-full h-full object-cover"
                onLoadedMetadata={() => {
                  console.log("Video metadata loaded")
                  setIsStreaming(true)
                  setIsStarting(false)
                }}
                onCanPlay={() => {
                  console.log("Video can play")
                  setIsStreaming(true)
                  setIsStarting(false)
                }}
              />
              {/* Camera controls overlay */}
              <div className="absolute bottom-3 sm:bottom-4 left-1/2 transform -translate-x-1/2">
                <Button
                  onClick={classifyNow}
                  size="lg"
                  className="btn-primary rounded-full w-12 h-12 sm:w-16 sm:h-16 p-0 shadow-lg"
                >
                  <Camera className="h-5 w-5 sm:h-6 sm:w-6" />
                </Button>
              </div>
            </>
          ) : cameraError ? (
            // Error state
            <div className="flex items-center justify-center h-full">
              <div className="text-center p-4">
                <Camera className="h-8 w-8 sm:h-12 sm:w-12 text-destructive mx-auto mb-2" />
                <p className="text-destructive text-sm sm:text-base mb-2">{cameraError}</p>
                <Button onClick={startCamera} variant="outline" size="sm">
                  Try Again
                </Button>
              </div>
            </div>
          ) : isStarting ? (
            // Loading state
            <div className="flex items-center justify-center h-full">
              <div className="text-center p-4">
                <Camera className="h-8 w-8 sm:h-12 sm:w-12 text-muted-foreground mx-auto mb-2 animate-pulse" />
                <p className="text-muted-foreground text-sm sm:text-base">Starting camera...</p>
                <p className="text-xs text-muted-foreground mt-1">Please allow camera access when prompted</p>
              </div>
            </div>
          ) : (
            // Manual start fallback
            <div className="flex items-center justify-center h-full">
              <div className="text-center p-4">
                <Camera className="h-8 w-8 sm:h-12 sm:w-12 text-muted-foreground mx-auto mb-2" />
                <p className="text-muted-foreground text-sm sm:text-base mb-2">Camera not started</p>
                <Button onClick={startCamera} variant="outline" size="sm">
                  Start Camera
                </Button>
              </div>
            </div>
          )}
        </div>

        {/* Action buttons */}
        <div className="flex flex-col sm:flex-row gap-3 sm:gap-4">
          {showPreview ? (
            <>
              <Button onClick={confirmCapture} className="btn-primary flex-1 py-2.5 sm:py-3">
                <Check className="h-4 w-4 mr-2" />
                Use This Image
              </Button>
              <Button onClick={retakePhoto} variant="outline" className="flex-1 bg-transparent py-2.5 sm:py-3">
                <X className="h-4 w-4 mr-2" />
                Retake
              </Button>
            </>
          ) : (
            <>
              {devices.length > 1 && (
                <div className="w-full">
                  <label className="text-xs text-muted-foreground">Camera</label>
                  <select
                    className="mt-1 w-full rounded-md bg-card border border-border px-3 py-2 text-sm"
                    value={selectedDeviceId || ""}
                    onChange={(e) => {
                      const id = e.target.value || undefined
                      setSelectedDeviceId(id)
                      if (id) localStorage.setItem("veggiefeed_camera_device", id)
                      setTimeout(() => startCamera(), 0)
                    }}
                  >
                    <option value="">Default camera</option>
                    {devices.map((d) => (
                      <option key={d.deviceId} value={d.deviceId}>
                        {d.label || `Camera ${d.deviceId.slice(-4)}`}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              <Button onClick={() => fileInputRef.current?.click()} variant="outline" className="flex-1 py-2.5 sm:py-3">
                <Upload className="h-4 w-4 mr-2" />
                Upload Image
              </Button>
              {!hasStream && (
                <Button 
                  onClick={startCamera}
                  className="btn-primary flex-1 py-2.5 sm:py-3"
                  disabled={isStarting}
                >
                  <Camera className="h-4 w-4 mr-2" />
                  {isStarting ? "Starting..." : "Start Camera"}
                </Button>
              )}
            </>
          )}
        </div>

        {/* Hidden file input */}
        <input ref={fileInputRef} type="file" accept="image/*" onChange={handleFileUpload} className="hidden" />

        {/* Hidden canvas for image capture */}
        <canvas ref={canvasRef} className="hidden" />
      </CardContent>
    </Card>
  )
}
