# VeggieFeed — Camera-Only Test Plan (IMX500 AI Camera)

Use this guide when you **only** have the Raspberry Pi AI Camera (IMX500) connected — no conveyor, servos, IR sensors, or weight sensor yet.

---

## How It Works Right Now

The pre-trained model (`imx500_network_yolo11n_pp.rpk`) was trained on the **COCO dataset** — 80 general classes. It has **never seen vegetable peels**.

The system auto-detects you're using a COCO model and loads all 80 COCO labels. With `--coco` mapping enabled, **only real produce items** are detected and mapped to our veggie classes:

| COCO object | Mapped to | Why |
|-------------|-----------|-----|
| `broccoli`  | Broccoli Stems | Direct match |
| `carrot`    | Carrot Peels | Direct match |

Only exact matches are kept. Everything else (person, banana, apple, cup, etc.) is **filtered out**.

### Stream overlay behavior
- **When a veggie is detected**: thick colored bounding box + label + confidence %
- **When nothing is detected**: yellow text "VeggieFeed | No peel detected" so you know the stream is alive
- **Always shown**: FPS counter + detection count at the bottom

---

## Camera-Only Build & Test Steps

### 1. Install runtime dependencies

```bash
sudo apt update
sudo apt install -y \
  python3-flask python3-flask-cors \
  python3-numpy python3-opencv \
  python3-picamera2 python3-simplejpeg
```

### 2. Verify camera hardware

```bash
rpicam-hello --timeout 3000
rpicam-hello --list-cameras
```

You should see the IMX500 listed. If not, check the ribbon cable and run `sudo raspi-config` → Interface → Camera.

### 3. Start the backend (camera real, hardware simulated)

```bash
cd /home/projectmain/raspi_system

PYTHONNOUSERSITE=1 python3 main.py \
  --model models/coco_pretrained/imx500_network_yolo11n_pp.rpk \
  --task detect \
  --simulate
```

- The system auto-detects the COCO model, loads COCO labels, and enables veggie mapping
- `--task detect` uses the IMX500 on-chip inference accelerator
- `--simulate` simulates GPIO hardware only; camera inference is **real**
- `--headless` is on by default (no preview window needed over SSH)
- Default threshold is 0.30 (lowered for better detection on produce)

### 4. Open the live stream

Wait for "Network Firmware Upload: 100%" then open in any browser:

```
http://localhost:5000/stream
```

You should immediately see a live camera feed with:
- "VeggieFeed | No peel detected" text (when nothing veggie-like is visible)
- FPS + detection count at the bottom

### 5. Test with produce

Hold these in front of the camera:

| Hold this | Expected bounding box label |
|-----------|-----------------------------|
| Carrot    | Carrot Peels                |
| Broccoli  | Broccoli Stems              |

You should see a **thick colored bounding box** with the veggie class label and confidence percentage.

### 6. Verify API from a second terminal

```bash
curl http://localhost:5000/health
curl http://localhost:5000/status
curl -o /tmp/frame.jpg http://localhost:5000/frame
```

### 7. Connect the Next.js dashboard

```bash
cd /home/projectmain/mainproject
cp .env.local.example .env.local
# Edit .env.local → PI_API_URL=http://localhost:5000

pnpm install
pnpm dev
```

Open `http://<host>:3000/dashboard`:
- **Live tab**: MJPEG stream with bounding boxes
- **Capture tab**: snap and classify

---

## Camera-Only Validation Checklist

- [ ] `rpicam-hello --list-cameras` shows IMX500
- [ ] `main.py` starts, firmware uploads to 100%
- [ ] `http://<ip>:5000/stream` shows live video with "No peel detected" overlay
- [ ] Holding a banana/apple shows a thick bounding box with veggie label
- [ ] `/health` returns healthy, `/status` shows `is_running: true`
- [ ] Dashboard Live tab shows stream
- [ ] System runs stable for 15+ minutes

---

## What Comes Next

1. **Collect vegetable peel images** using the AI camera (`scripts/collect_training_data.py`)
2. **Train YOLO11n** on your 12 peel classes (`training/train_yolo11n.py`)
3. **Export to IMX500 RPK** (`training/export_to_imx500.py`)
4. **Re-run with your custom model** — then actual veggie peels will be detected with real class names and bounding boxes, no COCO mapping needed

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `numpy.dtype size changed` | Run with `PYTHONNOUSERSITE=1` prefix |
| `No module named 'flask_cors'` | `sudo apt install python3-flask-cors` |
| Camera not found | Check ribbon cable, `sudo raspi-config` → Interface → Camera, verify with `rpicam-hello` |
| No detections even with produce | Lower threshold: `--threshold 0.2` |
| Stream shows "No peel detected" with produce visible | Wait 15-20s after firmware upload for first inference results |
| Low FPS | Normal for IMX500 detection mode (~10-15 FPS) |
| Stream not loading in browser | Check firewall; try `curl -I http://localhost:5000/stream` |
