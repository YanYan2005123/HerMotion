from __future__ import annotations

import argparse
import json
from collections import deque
from pathlib import Path

import torch
import numpy as np
from PIL import Image

from efficientnet_b0_runtime import load_checkpoint


MEAN = torch.tensor([0.485, 0.456, 0.406]).view(3, 1, 1)
STD = torch.tensor([0.229, 0.224, 0.225]).view(3, 1, 1)


def preprocess(image: Image.Image) -> torch.Tensor:
    image = image.convert("RGB")
    width, height = image.size
    if width < height:
        new_width, new_height = 256, round(height * 256 / width)
    else:
        new_height, new_width = 256, round(width * 256 / height)
    image = image.resize((new_width, new_height), Image.Resampling.BILINEAR)
    left, top = (new_width - 224) // 2, (new_height - 224) // 2
    image = image.crop((left, top, left + 224, top + 224))
    raw = np.asarray(image, dtype=np.uint8).copy()
    tensor = torch.from_numpy(raw).permute(2, 0, 1).float().div_(255.0)
    return tensor.sub_(MEAN).div_(STD).unsqueeze(0)


class YogaClassifier:
    def __init__(self, checkpoint: str | Path, gate_config: str | Path) -> None:
        self.model, self.classes, _ = load_checkpoint(str(checkpoint))
        self.config = json.loads(Path(gate_config).read_text(encoding="utf-8"))
        self.history: deque[str | None] = deque(maxlen=self.config["temporal"]["window"])

    @torch.inference_mode()
    def predict(self, image: Image.Image, selected_pose: str | None = None, static: bool = False) -> dict:
        logits = self.model(preprocess(image))[0]
        probabilities = logits.softmax(0)
        values, indices = probabilities.topk(3)
        top = [{"class": self.classes[i], "confidence": float(v)} for v, i in zip(values, indices)]
        confidence = top[0]["confidence"]
        margin = confidence - top[1]["confidence"]
        accepted = confidence >= self.config["confidence_threshold"] and margin >= self.config["margin_threshold"]
        mapped = self.config["class_to_pose"].get(top[0]["class"])
        selected_match = selected_pose is None or mapped == selected_pose
        current = mapped if accepted and selected_match else None
        if static:
            return {
                "accepted": current is not None,
                "reason": "accepted" if current is not None else ("low_confidence_or_margin" if not accepted else "selected_pose_mismatch"),
                "pose_id": current,
                "raw_pose_id": mapped,
                "confidence": confidence,
                "margin": margin,
                "top3": top,
                "frames_collected": 1,
            }
        self.history.append(current)
        required = self.config["temporal"]["required_matches"]
        stable = current is not None and sum(x == current for x in self.history) >= required
        reason = "accepted" if stable else (
            "low_confidence_or_margin" if not accepted else
            "selected_pose_mismatch" if not selected_match else "collecting_frames"
        )
        return {
            "accepted": stable,
            "reason": reason,
            "pose_id": current if stable else None,
            "raw_pose_id": mapped,
            "confidence": confidence,
            "margin": margin,
            "top3": top,
            "frames_collected": len(self.history),
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="HerMotion Yoga-82 safe classifier")
    parser.add_argument("image")
    parser.add_argument("--checkpoint", default="models/best.pt")
    parser.add_argument("--config", default="config/runtime_gate.json")
    parser.add_argument("--selected-pose")
    args = parser.parse_args()
    classifier = YogaClassifier(args.checkpoint, args.config)
    result = classifier.predict(Image.open(args.image), args.selected_pose)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
