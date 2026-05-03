#!/usr/bin/env python3
"""
VeggieFeed — Main System Orchestrator
======================================

Starts and coordinates all components of the vegetable peel sorting system:
  1. IMX500 AI Camera inference engine
  2. Hardware controller (servos, sensors, conveyor)
  3. REST API server (Flask)
  4. Sorting logic (ties inference results to hardware actions)

Usage:
    # Full system (on Raspberry Pi with IMX500 camera):
    python main.py --model models/coco_pretrained/imx500_network_yolo11n_pp.rpk

    # With custom fine-tuned model:
    python main.py --model training/runs/classify/veggiefeed_cls/weights/best.pt --task software

    # Development/testing mode (no hardware):
    python main.py --simulate --model training/runs/classify/veggiefeed_cls/weights/best.pt --task software

    # COCO pre-trained model for initial testing:
    python main.py --model models/coco_pretrained/imx500_network_yolo11n_pp.rpk --coco --simulate
"""

import argparse
import logging
import os
import signal
import sys
import threading
import time

# Setup path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from inference.veggiefeed_inference import (
    VEGGIE_CLASSES, VEGGIE_TO_BIN, inference_state,
    run_classification_inference, run_detection_inference, run_software_inference,
)
from hardware.hardware_controller import HardwareController
from api.api_server import create_app, set_inference_state, set_hardware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("veggiefeed.main")


class VeggieFeedSystem:
    """
    Main system orchestrator.

    Workflow:
    1. Object enters conveyor → IR entry sensor triggers
    2. Conveyor moves object to classification zone
    3. IR classify sensor triggers → capture + classify
    4. Classification result determines target bin
    5. Object continues to exit zone
    6. IR exit sensor triggers → activate servo diverter
    7. Servo diverts to correct bin, then resets
    8. Repeat
    """

    # Timing constants
    CLASSIFY_SETTLE_TIME = 0.3    # Wait for stable classification (seconds)
    CLASSIFY_TIMEOUT = 3.0        # Max time to wait for classification
    DIVERT_DELAY = 0.5           # Delay between classification and divert

    def __init__(self, hardware: HardwareController, args):
        self.hw = hardware
        self.args = args
        self._running = False
        self._pending_classification = None  # Stores result until divert
        self._sort_thread = None

    def start(self):
        """Start the sorting system."""
        self._running = True

        # Register IR sensor callbacks
        self.hw.on_ir_entry(self._on_entry)
        self.hw.on_ir_classify(self._on_classify_zone)
        self.hw.on_ir_exit(self._on_exit_zone)
        self.hw.start_ir_monitoring()

        # Start conveyor
        self.hw.start_conveyor()
        self.hw.blink_led(3)
        self.hw.beep(0.1, 2)

        logger.info("Sorting system STARTED")
        logger.info("Waiting for objects on conveyor...")

    def stop(self):
        """Stop the sorting system."""
        self._running = False
        self.hw.stop_conveyor()
        self.hw.stop_ir_monitoring()
        self.hw.reset_all_servos()
        self.hw.set_led(False)
        logger.info("Sorting system STOPPED")

    def _on_entry(self):
        """Called when an object enters the conveyor."""
        logger.info(">> Object detected at ENTRY")
        self.hw.set_led(True)
        self._pending_classification = None

    def _on_classify_zone(self):
        """Called when an object reaches the classification zone (under camera)."""
        logger.info(">> Object in CLASSIFICATION zone")

        # Slow or pause conveyor for better classification
        self.hw.slow_conveyor()

        # Wait for stable classification
        start = time.time()
        best_result = None
        best_confidence = 0

        while time.time() - start < self.CLASSIFY_TIMEOUT:
            result = inference_state.get_top_result()
            if result and result.confidence > best_confidence:
                best_result = result
                best_confidence = result.confidence

            # If we have a high-confidence result, accept it early
            if best_confidence > 0.7:
                break

            time.sleep(self.CLASSIFY_SETTLE_TIME)

        if best_result:
            self._pending_classification = best_result
            logger.info(
                f"   Classified: {best_result.label} "
                f"({best_result.confidence:.1%}) → Bin {best_result.bin_id}"
            )
            self.hw.beep(0.05, 1)
        else:
            logger.warning("   Classification failed — no result")
            # Default to bin 0
            from inference.veggiefeed_inference import ClassificationResult
            self._pending_classification = ClassificationResult(
                label="Unknown",
                confidence=0.0,
                bin_id=0,
                timestamp=time.time(),
            )

        # Resume conveyor
        self.hw.start_conveyor()

    def _on_exit_zone(self):
        """Called when an object reaches the divert/exit zone."""
        logger.info(">> Object at EXIT/DIVERT zone")

        if self._pending_classification:
            bin_id = self._pending_classification.bin_id
            label = self._pending_classification.label
            logger.info(f"   Diverting [{label}] to Bin {bin_id}")
            self.hw.divert_to_bin(bin_id)
            self._pending_classification = None
        else:
            # No classification available — send to default bin
            logger.warning("   No classification — sending to default bin 0")
            self.hw.divert_to_bin(0)

        self.hw.set_led(False)

    def get_stats(self) -> dict:
        """Get sorting statistics."""
        return {
            "bin_counts": dict(self.hw.bin_counts),
            "total_sorted": sum(self.hw.bin_counts.values()),
            "bin_weights": dict(self.hw.bin_weights),
            "conveyor_state": self.hw.conveyor_state.name,
            "is_running": self._running,
        }


def main():
    parser = argparse.ArgumentParser(description="VeggieFeed Sorting System")
    parser.add_argument("--model", type=str,
                       default="/home/project1/final/bestproject/raspi_system/models/coco_pretrained/imx500_network_yolo11n_pp.rpk",
                       help="Path to model (.rpk for IMX500, .pt for software)")
    parser.add_argument("--task", type=str, default="detect",
                       choices=["classify", "detect", "software"],
                       help="Inference mode")
    parser.add_argument("--labels", type=str, default=None,
                       help="Path to labels file")
    parser.add_argument("--threshold", type=float, default=0.30,
                       help="Detection confidence threshold")
    parser.add_argument("--coco", action="store_true",
                       help="Use COCO→Veggie label mapping (pre-trained model)")
    parser.add_argument("--simulate", action="store_true",
                       help="Simulate hardware (no GPIO)")
    parser.add_argument("--headless", action="store_true", default=True,
                       help="No camera preview window (default: True on Pi)")
    parser.add_argument("--preview", action="store_true",
                       help="Show camera preview window (overrides --headless)")
    parser.add_argument("--api-port", type=int, default=5000,
                       help="API server port (default: 5000)")
    parser.add_argument("--no-api", action="store_true",
                       help="Disable API server")
    parser.add_argument("--no-sort", action="store_true",
                       help="Disable sorting logic (inference only)")
    args = parser.parse_args()

    print()
    print("=" * 60)
    print("  VeggieFeed — Vegetable Peel Sorting System")
    print("=" * 60)
    print(f"  Model:     {args.model}")
    print(f"  Task:      {args.task}")
    print(f"  COCO map:  {args.coco}")
    print(f"  Hardware:  {'SIMULATED' if args.simulate else 'LIVE GPIO'}")
    print(f"  API:       {'disabled' if args.no_api else f'port {args.api_port}'}")
    print(f"  Sorting:   {'disabled' if args.no_sort else 'enabled'}")
    print("=" * 60)
    print()

    # --preview overrides --headless
    if args.preview:
        args.headless = False

    # ── Initialize hardware ──
    hw = HardwareController(simulate=args.simulate)

    # ── Initialize sorting system ──
    sorter = None
    if not args.no_sort:
        sorter = VeggieFeedSystem(hw, args)

    # ── Start API server in background thread ──
    if not args.no_api:
        flask_app = create_app(inference_state, hw)
        api_thread = threading.Thread(
            target=lambda: flask_app.run(
                host="0.0.0.0",
                port=args.api_port,
                debug=False,
                use_reloader=False,
            ),
            daemon=True,
        )
        api_thread.start()
        logger.info(f"API server started on port {args.api_port}")

    # ── Start sorting if enabled ──
    if sorter:
        sorter.start()

    # ── Graceful shutdown ──
    def shutdown(signum, frame):
        print("\n[INFO] Shutting down...")
        if sorter:
            sorter.stop()
        hw.cleanup()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # ── Load labels ──
    # When using the COCO pre-trained model, always load COCO labels
    # (regardless of --coco flag) so that class IDs 0-79 map correctly.
    # The --coco flag controls whether to FILTER down to veggie-only classes.
    coco_path = os.path.join(BASE_DIR, "data", "coco_labels.txt")
    is_coco_model = "coco" in os.path.basename(args.model).lower() or "yolo11n_pp" in args.model

    labels = VEGGIE_CLASSES
    if args.labels:
        with open(args.labels, 'r') as f:
            labels = [line.strip() for line in f.readlines() if line.strip()]
    elif args.coco or is_coco_model:
        if os.path.exists(coco_path):
            with open(coco_path, 'r') as f:
                labels = [line.strip() for line in f.readlines()]
            logger.info(f"Loaded COCO labels ({len(labels)} classes)")
            # Auto-enable coco mapping when using COCO model
            if is_coco_model and not args.coco:
                args.coco = True
                logger.info("Auto-enabled COCO→Veggie mapping for COCO model")

    # ── Start inference (blocks main thread) ──
    try:
        if args.task == "classify":
            run_classification_inference(
                model_path=args.model,
                labels=labels,
                headless=args.headless,
            )
        elif args.task == "detect":
            run_detection_inference(
                model_path=args.model,
                labels=labels,
                threshold=args.threshold,
                headless=args.headless,
                use_coco_mapping=args.coco,
            )
        elif args.task == "software":
            run_software_inference(
                model_path=args.model,
                labels=labels,
                threshold=args.threshold,
                headless=args.headless,
            )
    except Exception as e:
        logger.error(f"Inference failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if sorter:
            sorter.stop()
        hw.cleanup()


if __name__ == "__main__":
    main()
