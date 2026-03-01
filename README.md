# VeggieFeed

Automated vegetable waste peel classification and sorting system built with a Raspberry Pi 5, the Raspberry Pi AI Camera (IMX500), and a YOLO11n neural network. A Next.js web dashboard provides real-time monitoring, live MJPEG video feed with bounding-box overlays, and classification analytics.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Raspberry Pi 5                             │
│                                                                 │
│  ┌────────────────┐     ┌──────────────────┐                   │
│  │ IMX500 Camera   │────▶│ YOLO11n Model    │                   │
│  │ (AI inference)  │     │ (12 peel classes) │                   │
│  └────────────────┘     └────────┬─────────┘                   │
│                                  │                              │
│  ┌─────────────┐    ┌───────────▼──────────┐                   │
│  │ Flask API    │◀──▶│ Main Orchestrator    │                   │
│  │ (port 5000)  │    │ (sorting logic)      │                   │
│  └──────┬──────┘    └───────────┬──────────┘                   │
│         │ MJPEG /stream         │                               │
│         │ /classify             │ GPIO                          │
│         │ /status         ┌─────▼───────────┐                  │
│         │                 │ Hardware Control  │                  │
│         │                 │ • Conveyor motor  │                  │
│         │                 │ • 4× Servo bins   │                  │
│         │                 │ • 3× IR sensors   │                  │
│         │                 │ • Weight sensor   │                  │
│         │                 │ • LED / Buzzer    │                  │
│         │                 └─────────────────┘                   │
└─────────┼───────────────────────────────────────────────────────┘
          │
          ▼
┌────────────────────────┐
│  Next.js Dashboard     │
│  • Live MJPEG feed     │
│  • Classification log  │
│  • Nutrition data      │
│  • Feed recommendations│
└────────────────────────┘
```

## Supported Classes (12)

| # | Class | Sorting Bin |
|---|-------|-------------|
| 1 | Carrot Peels | 0 — Root veggies |
| 2 | Tomato Skins | 0 |
| 3 | Bell Pepper Scraps | 0 |
| 4 | Potato Skins | 1 — Tubers |
| 5 | Cucumber Peels | 1 |
| 6 | Onion Skins | 2 — Aromatics |
| 7 | Broccoli Stems | 2 |
| 8 | Celery | 2 |
| 9 | Cabbage Leaves | 3 — Leafy greens |
| 10 | Lettuce | 3 |
| 11 | Cauliflower Leaves | 3 |
| 12 | Spinach | 3 |

## Directory Structure

```
veggiefeed/
├── mainproject/                  # Next.js web dashboard
│   ├── app/
│   │   ├── page.tsx              # Landing page (video grid)
│   │   ├── layout.tsx            # Root layout
│   │   ├── globals.css           # Global styles
│   │   ├── fonts.ts              # Font configuration
│   │   ├── api/
│   │   │   ├── classify-enhanced/route.ts   # Classification endpoint
│   │   │   ├── stream/route.ts              # MJPEG proxy from Pi
│   │   │   ├── pi-status/route.ts           # Pi inference status
│   │   │   ├── classes/route.ts             # Class list
│   │   │   └── health/route.ts              # Health check
│   │   ├── dashboard/page.tsx    # Main dashboard (Live + Capture tabs)
│   │   ├── app/page.tsx          # App classification page
│   │   └── auth/                 # Login / Signup pages
│   ├── components/
│   │   ├── LiveFeed.tsx          # MJPEG stream viewer with overlays
│   │   ├── CameraCapture.tsx     # Photo capture + classification
│   │   ├── ClassificationResults.tsx
│   │   ├── DynamicFrameLayout.tsx
│   │   ├── FrameComponent.tsx
│   │   ├── AuthProvider.tsx
│   │   └── ui/                   # shadcn/ui components
│   ├── lib/
│   │   ├── classes.ts            # Class names + definitions
│   │   └── utils.ts              # Tailwind merge utility
│   ├── public/                   # Videos + placeholder images
│   └── package.json
│
├── raspi_system/                 # Raspberry Pi backend
│   ├── main.py                   # System orchestrator (entry point)
│   ├── requirements.txt          # Python dependencies
│   ├── inference/
│   │   └── veggiefeed_inference.py   # IMX500 + YOLO11n inference
│   ├── hardware/
│   │   └── hardware_controller.py    # GPIO (servos, motors, sensors)
│   ├── api/
│   │   └── api_server.py            # Flask REST API + MJPEG stream
│   ├── training/
│   │   ├── train_yolo11n.py          # Fine-tune YOLO11n
│   │   ├── export_to_imx500.py       # Export to IMX500 RPK format
│   │   └── dataset.yaml             # Dataset configuration
│   ├── scripts/
│   │   └── collect_training_data.py  # Capture training images
│   ├── models/
│   │   └── coco_pretrained/          # Pre-trained YOLO11n COCO model
│   └── data/
│       ├── veggie_peel_labels.txt
│       ├── coco_labels.txt
│       └── images/{train,val}/       # Training data (per-class dirs)
│
├── .gitignore
└── README.md                     # This file
```

## Quick Start

### Prerequisites

- Raspberry Pi 5 with Raspberry Pi AI Camera (IMX500)
- Raspberry Pi OS (Bookworm 64-bit)
- Node.js 18+ and pnpm
- Python 3.11+

### 1. Pi Backend

```bash
# Install system packages
sudo apt update
sudo apt install python3-picamera2 python3-opencv python3-flask

# Install Python dependencies
cd raspi_system
pip install -r requirements.txt

# Test with the pre-trained COCO model (no custom training needed yet)
python main.py \
  --model models/coco_pretrained/imx500_network_yolo11n_pp.rpk \
  --task detect \
  --coco \
  --simulate
```

### 2. Web Dashboard

```bash
cd mainproject
cp .env.local.example .env.local
# Edit .env.local — set PI_API_URL to your Pi's address (default: http://localhost:5000)

pnpm install
pnpm dev
```

Open `http://localhost:3000` in your browser.

### 3. Train a Custom Model

```bash
cd raspi_system

# Capture training images (interactive)
python scripts/collect_training_data.py --split train
python scripts/collect_training_data.py --split val

# Train
cd training
python train_yolo11n.py --task classify --epochs 100

# Export to IMX500
python export_to_imx500.py \
  --weights runs/classify/veggiefeed_cls/weights/best.pt \
  --task classify

# Run with the custom model
cd ..
python main.py --model models/exported/imx500_network_veggiefeed_yolo11n.rpk --task classify
```

## Hardware Wiring (GPIO BCM)

| Component | Pin | Notes |
|-----------|-----|-------|
| Conveyor Enable | 17 | L298N ENA (PWM) |
| Conveyor IN1 | 27 | Direction |
| Conveyor IN2 | 22 | Direction |
| Servo Bin 0 | 12 | Root veggies |
| Servo Bin 1 | 13 | Tubers |
| Servo Bin 2 | 18 | Aromatics |
| Servo Bin 3 | 19 | Leafy greens |
| IR Entry | 5 | Object entering belt |
| IR Classify | 6 | Under camera |
| IR Exit | 16 | At diverter |
| Weight SCK | 20 | HX711 clock |
| Weight DT | 21 | HX711 data |
| Status LED | 25 | Visual |
| Buzzer | 24 | Audio |

## API Endpoints (Pi Flask Server — port 5000)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | System health |
| `GET` | `/status` | Full status + latest inference |
| `GET` | `/classes` | Supported vegetable classes |
| `GET` | `/stream` | MJPEG live video stream |
| `GET` | `/frame` | Single JPEG frame |
| `POST` | `/classify` | Latest camera classification |
| `POST` | `/classify-image` | Classify uploaded image |
| `GET` | `/hardware/status` | Hardware status |
| `POST` | `/hardware/conveyor` | Control conveyor |
| `POST` | `/hardware/divert` | Manual bin divert |

## Tech Stack

- **Hardware**: Raspberry Pi 5, IMX500 AI Camera, L298N motor driver, SG90 servos, IR sensors, HX711 load cell
- **AI/ML**: YOLO11n (Ultralytics), IMX500 on-device inference via picamera2
- **Backend**: Python 3.11, Flask, picamera2, RPi.GPIO
- **Frontend**: Next.js 14, TypeScript, Tailwind CSS, Radix UI, shadcn/ui

## License

This project is for educational and research purposes.
