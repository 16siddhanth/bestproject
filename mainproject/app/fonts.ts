import { Inter } from "next/font/google"

const ppEditorialNewUltralightItalic = {
  className: "font-pp-editorial",
  style: {
    fontFamily: "PPEditorialNew-UltralightItalic",
    fontWeight: "200",
    fontStyle: "italic",
  },
  variable: "--font-pp-editorial",
} as const

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter",
})

export { ppEditorialNewUltralightItalic, inter }
