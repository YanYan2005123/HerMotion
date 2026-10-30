from __future__ import annotations

import argparse
from pathlib import Path

from ultralytics import YOLO

NAMES = [
    "healthy_appearance", "peeling_coating", "red_tongue", "purple_tongue",
    "enlarged_tongue", "thin_tongue", "red_dots", "fissured_tongue",
    "tooth_marks", "white_coating", "yellow_coating", "black_coating",
    "smooth_coating", "renal_depression", "renal_protrusion",
    "hepatobiliary_depression", "hepatobiliary_protrusion",
    "spleen_stomach_depression", "heart_lung_protrusion", "heart_lung_depression",
]


def write_yaml(root: Path, output: Path) -> None:
    names = "\n".join(f"  {i}: {name}" for i, name in enumerate(NAMES))
    output.write_text(
        f"path: {root.resolve()}\ntrain: train/images\nval: val/images\ntest: test/images\nnames:\n{names}\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the TMC-Tongue observable-feature detector")
    parser.add_argument("--data-root", type=Path, required=True, help="Extracted YOLO txt dataset root")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--device", default="0")
    parser.add_argument("--model", default="yolo11n.pt")
    args = parser.parse_args()
    yaml_path = Path(__file__).with_name("tmc_tongue.yaml")
    write_yaml(args.data_root, yaml_path)
    model = YOLO(args.model)
    model.train(
        data=str(yaml_path), epochs=args.epochs, imgsz=640, batch=args.batch,
        device=args.device, project="runs/tongue", name="tmc_yolo11n",
        patience=18, cos_lr=True, close_mosaic=10,
    )


if __name__ == "__main__":
    main()

