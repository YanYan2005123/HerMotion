# 舌象模型落地说明

当前产品包含两条路径：

1. 可立即运行的浏览器规则路径：MediaPipe 面部关键点定位口部区域，再对 30 秒多帧舌面颜色进行质量控制和规则汇总。
2. 真实训练模型路径：使用 TonguExpert 人工标签训练 MobileNetV3-Small 共享骨干与两个分类头，分别识别舌苔颜色和舌质颜色。前端通过 `http://127.0.0.1:8766` 判断真实权重是否在线，离线时明确显示 `RULE FALLBACK`。

## 已完成的真实训练

- 数据：TonguExpert `L1_Labels_Manual.txt`，只使用人工标签，不使用预测标签充当真值。
- 舌苔颜色：white、light_yellow、yellow。
- 舌质颜色：light、regular、dark。
- 切分：SID 唯一的 70%/15%/15% 训练、验证、独立测试切分，固定随机种子 `20260814`。
- 独立测试集：舌苔准确率 91.38%、宏 F1 92.35%（58）；舌质准确率 78.85%、宏 F1 79.21%（52）；两头平均宏 F1 85.78%。
- 权重：`models/tongue/tongueexpert_multitask.pth`。
- 部署模型：`models/tongue/tongueexpert_multitask.ts`。
- 完整指标：`models/tongue/tongueexpert_metrics.json`。

## 数据与模型

- TOM：轻量舌体分割模型，MIT，论文报告 95.22% mIoU；官方 Hugging Face 提供约 48.5 MB 的 `TOM_S.pth`。
- TongueSAM：MIT，提供 TongueSet3（1,000 张舌体分割图）和预训练权重。
- TMC-Tongue：Dryad DOI `10.5061/dryad.1c59zw48r`，6,719 张图，20 类 COCO/TXT/XML 标注。
- TonguExpert：5,992 人，包含舌质颜色、舌苔颜色、裂纹和齿痕等人工表型，可用于后续多头分类器；使用前需再次核对下载包条款。

产品只保留 0–12 类可见舌象特征。TMC-Tongue 中将舌面区域映射到脏器的 13–19 类不进入产品输出。

## 复现训练与启动

```bash
python3 -m venv .venv-tongue
source .venv-tongue/bin/activate
pip install -r tongue_model/requirements.txt
python tongue_model/train_tongueexpert.py --root data/tongueexpert/extracted --epochs 12 --batch 16
uvicorn tongue_model.service:app --host 127.0.0.1 --port 8766
```

这是健康关怀 Demo，不应输出疾病、气血或体质诊断。出现持续疼痛、溃疡、出血、无法解释的颜色变化或其他明显不适时，建议用户咨询医生或牙医。
