"use client"

import { useState } from "react"
import DynamicFrameLayout from "../components/DynamicFrameLayout"
import { ppEditorialNewUltralightItalic, inter } from "./fonts"
import Image from "next/image"
import Link from "next/link"
import { Button } from "@/components/ui/button"

export default function Home() {
  const [headerSize] = useState(1.2) // 120% is the default size
  const [textSize] = useState(0.8) // 80% is the default size

  return (
    <div
      className={`min-h-screen bg-[#141414] flex items-center justify-center p-8 ${ppEditorialNewUltralightItalic.variable} ${inter.variable}`}
    >
      <div className="w-full h-full flex flex-col md:flex-row items-start gap-8 md:gap-8">
        {/* Left Content */}
        <div className="w-full md:w-[260px] flex-shrink-0 flex flex-col justify-between h-full">
          <div className="flex flex-col gap-16">
            <h1
              className={`${ppEditorialNewUltralightItalic.className} text-4xl md:text-6xl font-light italic tracking-tighter leading-[130%] text-primary`}
              style={{ fontSize: `${4 * headerSize}rem` }}
            >
              Smarter
              <br />
              Feed from
              <br />
              Veggie Waste
            </h1>
            <div
              className={`${inter.className} flex flex-col gap-12 text-white text-sm font-light max-w-[300px]`}
              style={{ fontSize: `${0.875 * textSize}rem` }}
            >
              <div className="space-y-6">
                <div className="h-px bg-white/10 w-full" />
                <p>
                  Use AI to classify vegetable waste and turn it into optimal feed inputs. Reduce costs, improve animal
                  health, and minimize environmental impact across your farm operations.
                </p>
                <p>
                  Works with photos and short video clips. Drag-and-drop your samples, get instant nutrition insights and
                  tailored recommendations for different livestock.
                </p>
                <div className="h-px bg-white/10 w-full" />
              </div>
            </div>
            <div className="flex gap-3">
              <Link href="/auth/signup">
                <Button className="bg-[#34c759] hover:bg-[#2fb453] text-black">Get started</Button>
              </Link>
              <Link href="/app">
                <Button variant="outline" className="border-white/20 text-white hover:bg-white/10">
                  Try demo
                </Button>
              </Link>
            </div>
            <div className="mt-6 w-8 h-8 relative opacity-80">
              <Image src="/placeholder-logo.svg" alt="VeggieFeed" fill className="object-contain" />
            </div>
          </div>
        </div>

        {/* Right Content */}
        <div className="w-full md:flex-grow h-[60vh] md:h-[80vh]">
          <DynamicFrameLayout />
        </div>
      </div>
    </div>
  )
}
