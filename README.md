# VeggieFeed

Automated vegetable waste peel classification and sorting system built with a Raspberry Pi 5, the Raspberry Pi AI Camera (IMX500), and a YOLO11n neural network. A Next.js web dashboard provides real-time monitoring, live MJPEG video feed with bounding-box overlays, and intelligent animal feed distribution analytics.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Raspberry Pi 5                             │
│                                                                 │
│  ┌────────────────┐     ┌──────────────────┐                   │
│  │ IMX500 Camera   │────▶│ YOLO11n Model    │                   │
│  │ (AI inference)  │     │ (Classification) │                   │
│  └────────────────┘     └────────┬─────────┘                   │
│                                  │                              │
│  ┌─────────────┐    ┌───────────▼──────────┐                   │
│  │ Flask API    │◀──▶│ System Controller  │                   │
│  │ (port 5001)  │    │ (sorting logic)      │                   │
│  └──────┬──────┘    └───────────┬──────────┘                   │
│         │ MJPEG /stream         │                               │
│         │ /system/status        │ I2C / GPIO                    │
│         │                 ┌─────▼───────────┐                  │
│         │                 │ Hardware Control  │                  │
│         │                 │ • 2× Conveyor     │                  │
│         │                 │ • 1× Vibration    │                  │
│         │                 │ • 1× PCA9685 Servo│                  │
│         │                 │ • 4× MiniScales   │                  │
│         │                 └─────────────────┘                   │
└─────────┼───────────────────────────────────────────────────────┘
          │
          ▼
┌────────────────────────┐
│  Next.js Dashboard     │
│  • Start/Stop System   │
│  • Live MJPEG feed     │
│  • Classification log  │
│  • 4× Bin Status       │
│  • Nutrient Tracking   │
└────────────────────────┘
```

## How It Works

1. **Continuous Operation**: When the system is started via the dashboard, the dual conveyor motors begin moving. A vibration motor pulses for 5 seconds every 15 seconds to ensure waste peels do not clump.
2. **Detection & Capture**: The YOLO11n model continuously monitors the camera feed. Upon detecting a vegetable peel, the conveyor belt halts immediately.
3. **Classification**: The system waits 1.5 seconds for the object to settle, then captures a high-resolution frame. The YOLO11n neural network accurately classifies the vegetable peel (e.g., Potato Skins, Cabbage Leaves) and counts the number of visible peels.
4. **Nutrient Matching**: The peel's nutritional profile (calories, protein, fat, fiber, calcium, phosphorus) is evaluated against the feed requirements of four animal types: Cattle, Goats, Poultry, and Pigs.
5. **Sorting**: The peel is assigned to the bin of the animal that most needs those specific nutrients. The PCA9685 servo controller rotates the diverter arm to the appropriate bin (30°, 70°, 110°, 150°).
6. **Resumption**: The conveyor resumes operation. Four M5 MiniScales independently measure the accumulating weight in each bin to provide real-time updates to the dashboard.

## Supported Classes (13)

| Class | Optimal Bin | Base Nutrients |
|-------|-------------|----------------|
| Potato Skins | Evaluated live | High carbs/fiber |
| Onion Skins | Evaluated live | High moisture |
| Carrot Peels | Evaluated live | Balanced |
| Tomato Skins | Evaluated live | Low cal |
| Cucumber Peels| Evaluated live | High moisture |
| Brinjal Peels | Evaluated live | Fiber |
| Cabbage Leaves| Evaluated live | Calcium |
| Spinach | Evaluated live | Protein/Calcium |
| Bell Pepper Scraps | Evaluated live | Fiber |
| Lettuce | Evaluated live | High moisture |
| Broccoli Stems | Evaluated live | Protein |
| Cauliflower Leaves | Evaluated live | Protein |
| Celery | Evaluated live | Calcium |

## Directory Structure

```
veggiefeed/
├── mainproject/                  # Next.js web dashboard
│   ├── app/                      
│   │   ├── page.tsx              # Try Demo page (Start/Stop UI)
│   │   ├── dashboard/page.tsx    # Dashboard layout
│   │   └── api/system/           # API routes for system control
│   ├── components/               # React components (BinStatusPanel, ClassificationLog, etc.)
│   ├── nutrient_data.py          # Nutritional data & matching algorithm
│   └── system_controller.py      # Unified hardware/software orchestrator
│
├── raspi_system/                 # Raspberry Pi legacy / standalone scripts
│   ├── inference/                # YOLO11n inference wrappers
│   ├── hardware/                 # Standalone hardware drivers
│   └── models/                   # Neural network weights
│
└── README.md                     # This file
```

## Hardware Wiring (Raspberry Pi 5 GPIO / I2C)

| Component | Interface / Pin | Notes |
|-----------|-----------------|-------|
| **Power** | Pin 1 (3.3 V) | PCA9548A VIN, PCA9685 VCC |
| **I2C Bus** | Pin 3 (SDA), Pin 5 (SCL) | Shared by PCA9685 and PCA9548A |
| Belt Motor | Pin 7 (GPIO4), Pin 11 (GPIO17), Pin 13 (GPIO27), Pin 15 (GPIO22) | BTS7960 #1 (RPWM, LPWM, R_EN, L_EN) |
| Vibration Motor | Pin 12 (GPIO18), Pin 16 (GPIO23), Pin 18 (GPIO24), Pin 22 (GPIO25) | BTS7960 #2 (RPWM, LPWM, R_EN, L_EN) |
| Servo Controller | I2C (Address 0x40) | PCA9685 — Servo on Channel 0 |
| I2C Mux | I2C (Address 0x70) | PCA9548A (HW-617) — 4 downstream channels |
| Bin 0 Scale (Cattle) | Mux SD0 / SC0 | M5 MiniScale (Address 0x26) |
| Bin 1 Scale (Goats) | Mux SD1 / SC1 | M5 MiniScale (Address 0x26) |
| Bin 2 Scale (Poultry) | Mux SD2 / SC2 | M5 MiniScale (Address 0x26) |
| Bin 3 Scale (Pigs) | Mux SD3 / SC3 | M5 MiniScale (Address 0x26) |

## API Endpoints (Flask Server — port 5001)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | System health check |
| `POST` | `/system/start` | Start the belt motor and monitoring |
| `POST` | `/system/stop` | Stop all motors and inference |
| `GET` | `/system/status`| Current state, bin weights, and events |
| `GET` | `/system/stream`| MJPEG live video feed |
| `GET` | `/system/frame` | Single high-res JPEG frame |

## Tech Stack

- **Hardware**: Raspberry Pi 5, IMX500 AI Camera, 2× BTS7960 motor drivers, PCA9685 servo driver, PCA9548A I2C mux, 4× M5 MiniScales.
- **AI/ML**: YOLO11n (Ultralytics), IMX500 on-device inference via picamera2.
- **Backend**: Python 3.11, Flask.
- **Frontend**: Next.js 14, TypeScript, Tailwind CSS, shadcn/ui.
