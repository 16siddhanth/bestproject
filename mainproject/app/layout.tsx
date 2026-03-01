import "./globals.css"
import { ppEditorialNewUltralightItalic, inter } from "./fonts"
import { AuthProvider } from "@/components/AuthProvider"
import type React from "react"

export const metadata = {
  title: "VeggieFeed — Smart feed from veggie waste",
  description: "AI-driven classification and nutrition insights for vegetable waste.",
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className={`${ppEditorialNewUltralightItalic.variable} ${inter.variable}`}>
      <body className={inter.className}>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  )
}
