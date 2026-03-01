# VeggieFeed — Raspberry Pi Sorting System

Complete vegetable peel classification and sorting system using:
- **Raspberry Pi 5** — main controller
- **Raspberry Pi AI Camera (IMX500)** — on-device neural network inference
- **YOLO11n** — fine-tuned for 12 vegetable peel classes
- **Conveyor belt** with DC motor + L298N driver
- **4 servo-actuated diverter bins**
- **IR sensors** for object detection along the conveyor
- **HX711 weight sensor** for bin weight monitoring
- **Next.js web dashboard** for real-time monitoring

## System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     Raspberry Pi 5                           │
│                                                              │
│  ┌─────────────────┐    ┌──────────────────┐                │
│  │  IMX500 Camera   │───▶│  YOLO11n Model   │                │
│  │  (AI inference)  │    │  (classification) │                │
│  └─────────────────┘    └───────┬──────────┘                │
│                                 │                            │
│  ┌──────────────┐    ┌─────────▼──────────┐                 │
│  │  Flask API    │◀──▶│  Main Orchestrator │                 │
│  │  (port 5000)  │    │  (sorting logic)   │                 │
│  └──────┬───────┘    └─────────┬──────────┘                 │
│         │                      │                             │
│         │            ┌─────────▼──────────┐                 │
│         │            │  Hardware Controller│                 │
│         │            │  • Conveyor (GPIO)  │                 │
│         │            │  • 4x Servos (PWM)  │                 │
│         │            │  • 3x IR Sensors    │                 │
│         │            │  • Weight Sensor    │                 │
│         │            └────────────────────┘                  │
│         │                                                    │
└─────────┼────────────────────────────────────────────────────┘
          │
          ▼
┌──────────────────────┐
│  Next.js Dashboard   │
│  (web browser)       │
│  • Camera preview    │
│  • Classification    │
│  • Nutrition data    │
│  • Feed advice       │
└──────────────────────┘
```

## Directory Structure

```
raspi_system/
├── main.py                         # System orchestrator (start here)
├── requirements.txt                # Python dependencies
├── inference/
│   └── veggiefeed_inference.py     # IMX500 camera + YOLO11n inference
├── hardware/
│   └── hardware_controller.py      # GPIO control (servos, motors, sensors)
├── api/
│   └── api_server.py               # Flask REST API + MJPEG stream
├── training/
│   ├── train_yolo11n.py            # Fine-tune YOLO11n
│   ├── export_to_imx500.py         # Export model to IMX500 RPK format
│   └── dataset.yaml                # Dataset configuration
├── scripts/
│   └── collect_training_data.py    # Capture training images
├── models/
│   ├── coco_pretrained/            # Pre-trained YOLO11n COCO model (.rpk)
│   └── exported/                   # Custom fine-tuned models (after export)
└── data/
    ├── veggie_peel_labels.txt      # Class labels
    ├── coco_labels.txt             # COCO labels (for pre-trained testing)
    └── images/                     # Training data (organize by class)
        ├── train/
        └── val/
```

## Quick Start

### 1. Install dependencies

```bash
# On Raspberry Pi OS:
sudo apt update
sudo apt install python3-picamera2 python3-opencv python3-flask

# Python packages:
cd raspi_system
pip install -r requirements.txt
```

### 2. Test with pre-trained COCO model (immediate testing)

The workspace includes a pre-trained YOLO11n model for COCO object detection.
You can test the system immediately with COCO-to-veggie class mapping:

```bash
python main.py \
  --model models/coco_pretrained/imx500_network_yolo11n_pp.rpk \
  --task detect \
  --coco \
  --simulate
```

### 3. Collect training data for vegetable peels

For accurate classification, you need to fine-tune on your specific vegetable peels:

```bash
# Capture training images (interactive — press keys to select class, SPACE to capture)
python scripts/collect_training_data.py --split train
python scripts/collect_training_data.py --split val

# Aim for 50-100+ images per class, 12 classes total
```

### 4. Train the custom YOLO11n model

```bash
cd training

# Classification mode (recommended — simpler, no bounding box annotation needed):
python train_yolo11n.py --task classify --epochs 100

# Detection mode (if you need bounding boxes — requires annotation):
python train_yolo11n.py --task detect --epochs 100 --imgsz 640
```

### 5. Export to IMX500 format

```bash
python training/export_to_imx500.py \
  --weights training/runs/classify/veggiefeed_cls/weights/best.pt \
  --task classify
```

### 6. Run the full system

```bash
# With fine-tuned model on IMX500:
python main.py --model exported_models/imx500_network_veggiefeed_yolo11n.rpk --task classify

# With software inference (no IMX500 needed):
python main.py --model training/runs/classify/veggiefeed_cls/weights/best.pt --task software

# Simulation mode (no hardware):
python main.py --model <path> --task software --simulate
```

### 7. Start the web dashboard

```bash
cd ../mainproject
cp .env.local.example .env.local
# Edit .env.local — set PI_API_URL to your Pi's IP
pnpm dev
```

## Hardware Wiring

### GPIO Pin Map (BCM numbering)

| Component | GPIO Pin | Notes |
|-----------|----------|-------|
| Conveyor Enable | 17 | L298N ENA (PWM) |
| Conveyor IN1 | 27 | Motor direction |
| Conveyor IN2 | 22 | Motor direction |
| Servo Bin 0 | 12 | PWM — Root veggies |
| Servo Bin 1 | 13 | PWM — Tubers |
| Servo Bin 2 | 18 | PWM — Aromatics |
| Servo Bin 3 | 19 | PWM — Leafy greens |
| IR Entry | 5 | Object entering |
| IR Classify | 6 | Object under camera |
| IR Exit | 16 | Object at diverter |
| Weight SCK | 20 | HX711 clock |
| Weight DT | 21 | HX711 data |
| Status LED | 25 | Visual indicator |
| Buzzer | 24 | Audio alert |

### Bin Assignment

| Bin | Classes | Servo GPIO |
|-----|---------|-----------|
| 0 | Carrot Peels, Tomato Skins, Bell Pepper Scraps | 12 |
| 1 | Potato Skins, Cucumber Peels | 13 |
| 2 | Onion Skins, Broccoli Stems, Celery | 18 |
| 3 | Cabbage Leaves, Lettuce, Cauliflower Leaves, Spinach | 19 |

## API Endpoints

The Flask API server runs on port 5000 by default.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /health | System health check |
| GET | /status | Full system status + latest inference |
| GET | /classes | Supported vegetable classes |
| GET | /stream | MJPEG live video stream |
| GET | /frame | Single JPEG frame |
| POST | /classify | Latest camera classification |
| POST | /classify-image | Classify uploaded image |
| GET | /hardware/status | Hardware status |
| POST | /hardware/conveyor | Control conveyor belt |
| POST | /hardware/divert | Manual bin divert |

## Sorting Workflow

1. Vegetable peel placed on conveyor belt
2. **IR Entry sensor** detects object → LED on
3. Conveyor moves object to classification zone
4. **IR Classify sensor** triggers → conveyor slows
5. **IMX500 camera** classifies the peel (YOLO11n)
6. Classification result determines target bin (0-3)
7. Conveyor resumes → object moves to exit zone
8. **IR Exit sensor** triggers → servo activates
9. Servo diverts peel into the correct bin
10. Servo returns to neutral → ready for next object

## Training Tips

- **Minimum 50 images per class** for reasonable results
- **100+ images per class** recommended for production
- Use varied lighting conditions and backgrounds
- Include different sizes, angles, and levels of freshness
- The `collect_training_data.py` script makes this easy
- Classification mode (`--task classify`) doesn't need bounding box annotations
- If using detection mode, annotate with tools like CVAT or LabelImg

## Troubleshooting

- **"Pi classifier not reachable"**: Ensure `main.py` is running on the Pi and the `PI_API_URL` in `.env.local` is correct
- **Low accuracy with COCO model**: Expected — the COCO model wasn't trained on vegetable peels. Fine-tune with your data.
- **Camera not found**: Check `rpicam-hello` works. The IMX500 needs firmware uploaded first.
- **Servo jitter**: Ensure adequate power supply (5V 4A+ for Pi 5 + servos)
- **GPIO errors**: Run with `sudo` or add user to `gpio` group
