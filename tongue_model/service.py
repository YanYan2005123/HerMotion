from __future__ import annotations

import io
import json
import os
from pathlib import Path

import torch
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
from torchvision import transforms

WEIGHT = Path(os.environ.get("TONGUE_MODEL", "models/tongue/tongueexpert_multitask.ts"))
METRICS = WEIGHT.with_name("tongueexpert_metrics.json")
MODEL = torch.jit.load(str(WEIGHT), map_location="cpu").eval() if WEIGHT.exists() else None
COAT_CLASSES = ["white", "light_yellow", "yellow"]
BODY_CLASSES = ["light", "regular", "dark"]
PREPROCESS = transforms.Compose([
    transforms.Resize(256), transforms.CenterCrop(224), transforms.ToTensor(),
    transforms.Normalize([.485, .456, .406], [.229, .224, .225]),
])

DISPLAY = {
    "coat:white": ("偏白苔观感", ["保持饮水和温和的常规口腔清洁，不要用力刮舌。"]),
    "coat:light_yellow": ("浅黄苔观感", ["先排除茶、咖啡、食物染色和暖光影响，再于白光下复测。"]),
    "coat:yellow": ("偏黄苔观感", ["先排除食物染色；持续黄苔或口腔不适时请咨询医生或牙医。"]),
    "body:light": ("舌质偏淡观感", ["优先保证规律饮食、补水和充分休息；持续伴随明显不适时请咨询专业人员。"]),
    "body:regular": ("舌质颜色较均匀", ["继续保持饮水、规律作息和均衡饮食。"]),
    "body:dark": ("舌质偏暗观感", ["先在自然白光下复测；若颜色变化持续或伴随不适，请寻求专业评估。"]),
}

app = FastAPI(title="Her Motion TongueExpert Service")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3001", "http://127.0.0.1:3001"], allow_methods=["GET", "POST"], allow_headers=["*"])


@app.get("/health")
def health() -> dict:
    report = json.loads(METRICS.read_text(encoding="utf-8")) if METRICS.exists() else None
    return {
        "model_loaded": MODEL is not None,
        "weight": str(WEIGHT),
        "dataset": "TonguExpert manual labels",
        "test_metrics": report.get("test") if report else None,
        "scope": "tongue coating color and tongue body color only",
    }


@app.post("/predict")
async def predict(request: Request) -> dict:
    if MODEL is None:
        raise HTTPException(503, "trained tongue weight is not installed")
    try:
        image = Image.open(io.BytesIO(await request.body())).convert("RGB")
    except Exception as exc:
        raise HTTPException(400, "invalid image") from exc
    tensor = PREPROCESS(image).unsqueeze(0)
    with torch.inference_mode():
        coat_logits, body_logits = MODEL(tensor)
        coat_prob, body_prob = coat_logits.softmax(1)[0], body_logits.softmax(1)[0]
    findings = []
    for head, classes, probs in (("coat", COAT_CLASSES, coat_prob), ("body", BODY_CLASSES, body_prob)):
        index = int(probs.argmax())
        source = f"{head}:{classes[index]}"
        label, advice = DISPLAY[source]
        findings.append({"source_label": source, "label": label, "confidence": round(float(probs[index]), 4), "advice": advice})
    return {
        "findings": findings,
        "model": "TongueExpert-MobileNetV3-Small multi-head",
        "disclaimer": "Observable image features only; not a disease, qi/blood, or constitution diagnosis.",
    }
