# VeggieFeed — Remaining Steps to Complete the Project

This document is the execution checklist from the current project state (cleanup done, directory structure refined, YOLO11n-only flow in place, live stream integrated).

## Current Status

- YOLO11n COCO model moved to `raspi_system/models/coco_pretrained/`
- COCO labels moved to `raspi_system/data/coco_labels.txt`
- Next.js build passes

---

## Phase 1 — Hardware Assembly & Wiring

### Goal
Build the physical sorting line and verify all GPIO-connected components are powered and detectable.

### Tasks

1. Wire conveyor motor controller (L298N)
   - ENA → GPIO 17 (PWM)
   - IN1 → GPIO 27
   - IN2 → GPIO 22

2. Wire 4 servo diverters
   - Bin 0 servo → GPIO 12
   - Bin 1 servo → GPIO 13
   - Bin 2 servo → GPIO 18
   - Bin 3 servo → GPIO 19

3. Wire IR sensors
   - Entry IR → GPIO 5
   - Classify-zone IR → GPIO 6
   - Exit IR → GPIO 16

4. Wire weight sensor (HX711)
   - SCK → GPIO 20
   - DT → GPIO 21

5. Wire status outputs
   - LED → GPIO 25
   - Buzzer → GPIO 24

6. Mount IMX500 camera above classify zone
   - Top-down angle
   - Stable lighting
   - No conveyor vibration blur

### Exit Criteria
- All components connected
- No brownouts under load
- Servos can move to target angles without jitter

---

## Phase 2 — Pi Runtime Bring-up

### Goal
Confirm backend services run and camera inference is operational.

### Tasks

1. Install Pi system dependencies

```bash
sudo apt update
sudo apt install -y \
  python3-flask python3-flask-cors \
  python3-numpy python3-opencv \
  python3-picamera2 python3-simplejpeg
```

2. Install Python dependencies

```bash
cd /home/projectmain/raspi_system
pip install -r requirements.txt
```

3. Start system in COCO simulation mode

```bash
cd /home/projectmain/raspi_system
PYTHONNOUSERSITE=1 python3 main.py \
  --model models/coco_pretrained/imx500_network_yolo11n_pp.rpk \
  --task detect \
  --simulate
```

Note: `--coco` is auto-detected when using the COCO model. `PYTHONNOUSERSITE=1` avoids numpy ABI conflicts.

4. Verify API endpoints from another terminal

```bash
curl http://localhost:5000/health
curl http://localhost:5000/status
curl http://localhost:5000/classes
```

### Exit Criteria
- `main.py` launches without crash
- `/health` returns healthy response
- `/status` updates with inference state

---

## Phase 3 — Dashboard Integration Check

### Goal
Validate web app ↔ Pi API communication and live feed.

### Tasks

1. Configure web env

```bash
cd /home/projectmain/mainproject
cp .env.local.example .env.local
```

2. Edit `.env.local`
- Set `PI_API_URL` to Pi address (example: `http://192.168.1.50:5000`)

3. Run dashboard

```bash
pnpm install
pnpm dev
```

4. Validate in browser
- `http://<host>:3000/dashboard`
- Live tab shows MJPEG feed
- Capture tab can classify image

### Exit Criteria
- `/api/stream` proxies MJPEG successfully
- `/api/pi-status` reports connected
- `/api/classify-enhanced` returns class + recommendation

---

## Phase 4 — Data Collection for 12 Peel Classes

### Goal
Build a high-quality dataset for vegetable peel domain training.

### Tasks

1. Capture training images

```bash
cd /home/projectmain/raspi_system
python scripts/collect_training_data.py --split train
```

2. Capture validation images

```bash
python scripts/collect_training_data.py --split val
```

3. Data targets
- Minimum: 80 images/class (train)
- Recommended: 150–250 images/class (train)
- Validation: 20–40 images/class

4. Data quality requirements
- Different lighting conditions
- Different peel sizes, textures, freshness
- Background variation matching real conveyor environment
- Avoid extreme blur and severe occlusion

### Exit Criteria
- All 12 class folders populated in `train` and `val`
- Dataset class balance within ~20% spread

---

## Phase 5 — Model Training

### Goal
Train a peel-specialized YOLO11n model.

### Recommended Track (Classification)

```bash
cd /home/projectmain/raspi_system/training
python train_yolo11n.py --task classify --epochs 100
```

### Optional Track (Detection)
Use only if bounding-box localization is required; requires annotated labels.

```bash
python train_yolo11n.py --task detect --epochs 100 --imgsz 640
```

### Evaluation Checklist
- Inspect confusion matrix
- Check per-class precision/recall
- Identify commonly confused pairs (e.g., leafy classes)
- Save best checkpoint path

### Exit Criteria
- Stable validation performance
- Best checkpoint exported (`best.pt`)

---

## Phase 6 — Export for IMX500

### Goal
Convert trained model to camera-compatible RPK.

### Tasks

```bash
cd /home/projectmain/raspi_system/training
python export_to_imx500.py \
  --weights runs/classify/veggiefeed_cls/weights/best.pt \
  --task classify
```

### Post-Export
- Place final RPK under `raspi_system/models/exported/`
- Keep semantic naming (example: `imx500_network_veggiefeed_yolo11n.rpk`)

### Exit Criteria
- Valid `.rpk` generated
- Model load test passes with `main.py`

---

## Phase 7 — End-to-End Sorting Validation

### Goal
Run full conveyor + camera + servo workflow.

### Tasks

1. Launch backend with custom exported model

```bash
cd /home/projectmain/raspi_system
PYTHONNOUSERSITE=1 python3 main.py \
  --model models/exported/imx500_network_veggiefeed_yolo11n.rpk \
  --task classify
```

2. Run dashboard

```bash
cd /home/projectmain/mainproject
pnpm dev
```

3. Execute test runs
- 10 samples/class minimum
- Log class predicted vs true class
- Log bin assignment correctness

4. Tune if needed
- Confidence threshold
- Conveyor speed
- Servo timing/angles
- Sensor trigger thresholds

### Exit Criteria
- Sorting accuracy target met (define practical threshold, e.g., >=90% in controlled setup)
- No repeated mechanical jams
- Stable runtime for at least 1 hour

---

## Phase 8 — Production Readiness

### Goal
Make system robust for long-running real usage.

### Tasks

1. Service management
- Create `systemd` service for `raspi_system/main.py`
- Optional second service for `mainproject` production server

2. Observability
- Persist inference + sorting logs
- Add disk-safe log rotation

3. Reliability
- Auto-restart on failure
- Camera disconnect recovery path
- Sensor fault fallback mode

4. Security and access
- Restrict API exposure to local network
- Add dashboard authentication backend

5. Documentation and handoff
- SOP for startup/shutdown
- Calibration SOP
- Troubleshooting decision tree

### Exit Criteria
- Reboot-safe startup
- Failure recovery verified
- Operator handoff documentation complete

---

## Suggested Weekly Execution Plan

### Week 1
- Phase 1, 2, 3 (hardware + bring-up + dashboard link)

### Week 2
- Phase 4 (dataset collection)

### Week 3
- Phase 5, 6 (training + export)

### Week 4
- Phase 7, 8 (E2E validation + hardening)

---

## Immediate Next Action

Phase 2 bring-up is complete — `main.py` runs with the COCO model, API serves on port 5000, and MJPEG stream is working with correct colors. Next: verify the dashboard shows the live feed (Phase 3), then start collecting peel images (Phase 4).