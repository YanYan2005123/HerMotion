from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import pandas as pd
import torch
from PIL import Image
from torch import nn
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms
from torchvision.models import MobileNet_V3_Small_Weights, mobilenet_v3_small

COAT_CLASSES = ["white", "light_yellow", "yellow"]
BODY_CLASSES = ["light", "regular", "dark"]


class TongueDataset(Dataset):
    def __init__(self, rows: list[dict], image_dir: Path, transform) -> None:
        self.rows, self.image_dir, self.transform = rows, image_dir, transform

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int):
        row = self.rows[index]
        image = Image.open(self.image_dir / f"{row['SID']}.jpg").convert("RGB")
        return self.transform(image), row["coat"], row["body"]


class TongueMultiHead(nn.Module):
    def __init__(self, pretrained: bool = True) -> None:
        super().__init__()
        weights = MobileNet_V3_Small_Weights.DEFAULT if pretrained else None
        base = mobilenet_v3_small(weights=weights)
        self.features, self.pool = base.features, nn.AdaptiveAvgPool2d(1)
        self.dropout = nn.Dropout(0.25)
        self.coat = nn.Linear(576, len(COAT_CLASSES))
        self.body = nn.Linear(576, len(BODY_CLASSES))

    def forward(self, image):
        features = self.dropout(self.pool(self.features(image)).flatten(1))
        return self.coat(features), self.body(features)


def macro_f1(targets: list[int], predictions: list[int], classes: int) -> float:
    scores = []
    for cls in range(classes):
        tp = sum(t == cls and p == cls for t, p in zip(targets, predictions))
        fp = sum(t != cls and p == cls for t, p in zip(targets, predictions))
        fn = sum(t == cls and p != cls for t, p in zip(targets, predictions))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        scores.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    return sum(scores) / len(scores)


@torch.no_grad()
def evaluate(model, loader, device) -> dict:
    model.eval()
    results = {"coat_t": [], "coat_p": [], "body_t": [], "body_p": []}
    for images, coat, body in loader:
        coat_logits, body_logits = model(images.to(device))
        for labels, logits, key in ((coat, coat_logits, "coat"), (body, body_logits, "body")):
            valid = labels >= 0
            results[f"{key}_t"].extend(labels[valid].tolist())
            results[f"{key}_p"].extend(logits[valid.to(device)].argmax(1).cpu().tolist())
    metrics = {}
    for key, count in (("coat", 3), ("body", 3)):
        target, pred = results[f"{key}_t"], results[f"{key}_p"]
        metrics[f"{key}_accuracy"] = sum(a == b for a, b in zip(target, pred)) / max(1, len(target))
        metrics[f"{key}_macro_f1"] = macro_f1(target, pred, count)
        metrics[f"{key}_samples"] = len(target)
    metrics["mean_macro_f1"] = (metrics["coat_macro_f1"] + metrics["body_macro_f1"]) / 2
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Train real manual-label TonguExpert coating/body color heads")
    parser.add_argument("--root", type=Path, default=Path("data/tongueexpert/extracted"))
    parser.add_argument("--output", type=Path, default=Path("models/tongue"))
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--seed", type=int, default=20260814)
    args = parser.parse_args()
    random.seed(args.seed);torch.manual_seed(args.seed)
    labels = pd.read_csv(args.root / "Phenotypes/L1_Labels_Manual.txt", sep="\t")
    rows = []
    for _, row in labels.iterrows():
        coat = COAT_CLASSES.index(row.labels_tai) if pd.notna(row.labels_tai) else -1
        body = BODY_CLASSES.index(row.labels_zhi) if pd.notna(row.labels_zhi) else -1
        image = args.root / "TongueImage/Raw" / f"{row.SID}.jpg"
        if image.exists() and (coat >= 0 or body >= 0):
            rows.append({"SID": row.SID, "coat": coat, "body": body})
    random.shuffle(rows)
    n = len(rows); train_end, val_end = int(n * .70), int(n * .85)
    splits = {"train": rows[:train_end], "val": rows[train_end:val_end], "test": rows[val_end:]}
    image_dir = args.root / "TongueImage/Raw"
    train_transform = transforms.Compose([
        transforms.RandomResizedCrop(224, scale=(.78, 1.0), ratio=(.85, 1.15)),
        transforms.RandomHorizontalFlip(), transforms.RandomRotation(5),
        transforms.ColorJitter(brightness=.08, contrast=.08), transforms.ToTensor(),
        transforms.Normalize([.485, .456, .406], [.229, .224, .225]),
    ])
    eval_transform = transforms.Compose([
        transforms.Resize(256), transforms.CenterCrop(224), transforms.ToTensor(),
        transforms.Normalize([.485, .456, .406], [.229, .224, .225]),
    ])
    loaders = {
        name: DataLoader(TongueDataset(part, image_dir, train_transform if name == "train" else eval_transform), batch_size=args.batch, shuffle=name == "train", num_workers=0)
        for name, part in splits.items()
    }
    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    model = TongueMultiHead(pretrained=True).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=2e-4, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)
    criterion = nn.CrossEntropyLoss()
    args.output.mkdir(parents=True, exist_ok=True)
    best, history = -1.0, []
    for epoch in range(1, args.epochs + 1):
        model.train(); running = 0.0
        for images, coat, body in loaders["train"]:
            images, coat, body = images.to(device), coat.to(device), body.to(device)
            coat_logits, body_logits = model(images); losses = []
            if (coat >= 0).any(): losses.append(criterion(coat_logits[coat >= 0], coat[coat >= 0]))
            if (body >= 0).any(): losses.append(criterion(body_logits[body >= 0], body[body >= 0]))
            loss = sum(losses);optimizer.zero_grad();loss.backward();optimizer.step();running += float(loss.detach().cpu())
        scheduler.step();metrics = evaluate(model, loaders["val"], device);metrics.update({"epoch": epoch, "train_loss": running / max(1, len(loaders["train"]))});history.append(metrics)
        print(json.dumps(metrics, ensure_ascii=False), flush=True)
        if metrics["mean_macro_f1"] > best:
            best = metrics["mean_macro_f1"]
            torch.save({"state_dict": model.state_dict(), "coat_classes": COAT_CLASSES, "body_classes": BODY_CLASSES, "seed": args.seed}, args.output / "tongueexpert_multitask.pth")
    checkpoint = torch.load(args.output / "tongueexpert_multitask.pth", map_location="cpu", weights_only=True)
    export_model = TongueMultiHead(pretrained=False);export_model.load_state_dict(checkpoint["state_dict"]);export_model.eval()
    traced = torch.jit.trace(export_model, torch.zeros(1, 3, 224, 224));traced.save(str(args.output / "tongueexpert_multitask.ts"))
    test_metrics = evaluate(export_model.to(device), loaders["test"], device)
    report = {"dataset": "TonguExpert manual labels", "rows": n, "splits": {k: len(v) for k, v in splits.items()}, "classes": {"coat": COAT_CLASSES, "body": BODY_CLASSES}, "best_val_macro_f1": best, "test": test_metrics, "history": history}
    (args.output / "tongueexpert_metrics.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"final_test": test_metrics, "artifacts": ["tongueexpert_multitask.pth", "tongueexpert_multitask.ts"]}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
