# VeggieFeed — Web Dashboard

Next.js 14 web dashboard for real-time monitoring of the VeggieFeed vegetable peel sorting system.

## Features

- **Live MJPEG Video Feed** — streams directly from the Pi camera with bounding-box overlays
- **Classification Results** — real-time display of detected vegetable peels with confidence scores
- **Nutrition Data** — per-class nutritional information for animal feed formulation
- **Feed Recommendations** — livestock suitability advice per peel type
- **Photo Capture Mode** — snap a photo and classify on demand
- **Responsive UI** — works on desktop and mobile

## Setup

```bash
# Install dependencies
pnpm install

# Configure environment
cp .env.local.example .env.local
# Edit .env.local — set PI_API_URL to the Raspberry Pi's Flask server address

# Development
pnpm dev

# Production build
pnpm build
pnpm start
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PI_API_URL` | `http://localhost:5000` | Raspberry Pi Flask API URL |

## API Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/api/classify-enhanced` | `POST` | Send image to Pi for YOLO11n classification |
| `/api/stream` | `GET` | Proxy MJPEG stream from Pi |
| `/api/pi-status` | `GET` | Poll Pi inference status |
| `/api/classes` | `GET` | List supported vegetable peel classes |
| `/api/health` | `GET` | Health check |

## Pages

| Path | Description |
|------|-------------|
| `/` | Landing page with video grid |
| `/dashboard` | Main monitoring dashboard (Live + Capture tabs) |
| `/app` | Standalone classification page |
| `/auth/login` | Login |
| `/auth/signup` | Sign up |

## Tech Stack

Next.js 14 · TypeScript · Tailwind CSS · Radix UI · shadcn/ui · pnpm