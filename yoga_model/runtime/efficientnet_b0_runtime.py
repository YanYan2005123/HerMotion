from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import torch
from torch import Tensor, nn


class Conv2dNormActivation(nn.Sequential):
    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        kernel_size: int = 3,
        stride: int = 1,
        groups: int = 1,
        norm_layer: Callable[[int], nn.Module] | None = nn.BatchNorm2d,
        activation_layer: Callable[..., nn.Module] | None = nn.SiLU,
    ) -> None:
        padding = (kernel_size - 1) // 2
        layers: list[nn.Module] = [
            nn.Conv2d(in_channels, out_channels, kernel_size, stride, padding, groups=groups, bias=norm_layer is None)
        ]
        if norm_layer is not None:
            layers.append(norm_layer(out_channels))
        if activation_layer is not None:
            layers.append(activation_layer(inplace=True))
        super().__init__(*layers)


class SqueezeExcitation(nn.Module):
    def __init__(self, input_channels: int, squeeze_channels: int) -> None:
        super().__init__()
        self.avgpool = nn.AdaptiveAvgPool2d(1)
        self.fc1 = nn.Conv2d(input_channels, squeeze_channels, 1)
        self.fc2 = nn.Conv2d(squeeze_channels, input_channels, 1)

    def forward(self, x: Tensor) -> Tensor:
        scale = self.avgpool(x)
        scale = torch.nn.functional.silu(self.fc1(scale), inplace=True)
        scale = torch.sigmoid(self.fc2(scale))
        return scale * x


class StochasticDepth(nn.Module):
    def __init__(self, p: float) -> None:
        super().__init__()
        self.p = p

    def forward(self, x: Tensor) -> Tensor:
        if not self.training or self.p == 0.0:
            return x
        survival = 1.0 - self.p
        shape = [x.shape[0]] + [1] * (x.ndim - 1)
        noise = torch.empty(shape, dtype=x.dtype, device=x.device).bernoulli_(survival)
        return x * noise / survival


@dataclass
class MBConvConfig:
    expand_ratio: int
    kernel: int
    stride: int
    input_channels: int
    out_channels: int
    repeats: int


class MBConv(nn.Module):
    def __init__(self, cnf: MBConvConfig, stochastic_depth_prob: float) -> None:
        super().__init__()
        expanded_channels = cnf.input_channels * cnf.expand_ratio
        layers: list[nn.Module] = []
        if expanded_channels != cnf.input_channels:
            layers.append(Conv2dNormActivation(cnf.input_channels, expanded_channels, kernel_size=1))
        layers.append(
            Conv2dNormActivation(
                expanded_channels,
                expanded_channels,
                kernel_size=cnf.kernel,
                stride=cnf.stride,
                groups=expanded_channels,
            )
        )
        layers.append(SqueezeExcitation(expanded_channels, max(1, cnf.input_channels // 4)))
        layers.append(
            Conv2dNormActivation(
                expanded_channels,
                cnf.out_channels,
                kernel_size=1,
                norm_layer=nn.BatchNorm2d,
                activation_layer=None,
            )
        )
        self.block = nn.Sequential(*layers)
        self.stochastic_depth = StochasticDepth(stochastic_depth_prob)
        self.out_channels = cnf.out_channels
        self.use_res_connect = cnf.stride == 1 and cnf.input_channels == cnf.out_channels

    def forward(self, x: Tensor) -> Tensor:
        result = self.block(x)
        if self.use_res_connect:
            result = self.stochastic_depth(result) + x
        return result


class EfficientNetB0(nn.Module):
    def __init__(self, num_classes: int = 82, dropout: float = 0.2) -> None:
        super().__init__()
        configs = [
            MBConvConfig(1, 3, 1, 32, 16, 1),
            MBConvConfig(6, 3, 2, 16, 24, 2),
            MBConvConfig(6, 5, 2, 24, 40, 2),
            MBConvConfig(6, 3, 2, 40, 80, 3),
            MBConvConfig(6, 5, 1, 80, 112, 3),
            MBConvConfig(6, 5, 2, 112, 192, 4),
            MBConvConfig(6, 3, 1, 192, 320, 1),
        ]
        layers: list[nn.Module] = [Conv2dNormActivation(3, 32, kernel_size=3, stride=2)]
        total_blocks = sum(c.repeats for c in configs)
        block_id = 0
        for base in configs:
            stage: list[nn.Module] = []
            for repeat in range(base.repeats):
                cnf = MBConvConfig(**vars(base))
                if repeat > 0:
                    cnf.input_channels = cnf.out_channels
                    cnf.stride = 1
                stage.append(MBConv(cnf, 0.2 * block_id / total_blocks))
                block_id += 1
            layers.append(nn.Sequential(*stage))
        layers.append(Conv2dNormActivation(320, 1280, kernel_size=1))
        self.features = nn.Sequential(*layers)
        self.avgpool = nn.AdaptiveAvgPool2d(1)
        self.classifier = nn.Sequential(nn.Dropout(p=dropout, inplace=True), nn.Linear(1280, num_classes))

    def forward(self, x: Tensor) -> Tensor:
        x = self.features(x)
        x = self.avgpool(x)
        x = torch.flatten(x, 1)
        return self.classifier(x)


def load_checkpoint(path: str) -> tuple[EfficientNetB0, list[str], dict]:
    checkpoint = torch.load(path, map_location="cpu", weights_only=False)
    if checkpoint.get("architecture") != "efficientnet_b0":
        raise ValueError(f"Unsupported architecture: {checkpoint.get('architecture')!r}")
    classes = checkpoint["classes"]
    model = EfficientNetB0(num_classes=len(classes))
    model.load_state_dict(checkpoint["model"], strict=True)
    model.eval()
    return model, classes, checkpoint
