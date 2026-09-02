"""SignTransformer — the word-level sign classifier.

An encoder-only transformer over a sequence of normalized landmark frames.
2.24M parameters at the default settings with 100 classes (measured, not
estimated — run `python src/model.py`). Small enough to train on a free Colab
T4 in well under an hour, and to export to a ~9MB ONNX file that a $7/month
CPU container serves comfortably.

Why a transformer rather than an LSTM or a 3D CNN:
  * Self-attention lets the model relate the start of a sign to its end
    directly, which matters for signs distinguished by a repeated movement.
  * Landmarks are already a compact representation, so we do not need
    convolutional feature extraction — that work was done by MediaPipe.
  * It exports cleanly to ONNX for CPU inference.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

import torch
import torch.nn as nn

from features import FEATURE_DIMS, SEQUENCE_LENGTH


@dataclass
class ModelConfig:
    """Everything needed to rebuild the architecture for a checkpoint.

    Saved alongside the weights so a checkpoint is self-describing — you never
    have to remember which hyperparameters produced a given .pt file.
    """

    num_classes: int
    input_dim: int = FEATURE_DIMS       # 332
    sequence_length: int = SEQUENCE_LENGTH  # 64
    d_model: int = 256
    nhead: int = 8
    num_layers: int = 4
    dim_feedforward: int = 512
    dropout: float = 0.1

    def to_dict(self) -> dict:
        return asdict(self)


class SignTransformer(nn.Module):
    """(batch, sequence_length, input_dim) -> (batch, num_classes) logits."""

    def __init__(self, config: ModelConfig) -> None:
        super().__init__()
        self.config = config

        # Project raw landmark features into the model's working width.
        self.input_projection = nn.Sequential(
            nn.Linear(config.input_dim, config.d_model),
            nn.LayerNorm(config.d_model),
        )

        # A learned summary token. After attention it has looked at every frame,
        # so its final state is the clip-level representation we classify.
        self.cls_token = nn.Parameter(torch.zeros(1, 1, config.d_model))

        # Learned positional embeddings. Clips are always exactly
        # sequence_length frames after resampling, so a fixed-size learned
        # table is simpler and slightly stronger than sinusoidal encoding here.
        self.positional = nn.Parameter(
            torch.zeros(1, config.sequence_length + 1, config.d_model)
        )
        self.dropout = nn.Dropout(config.dropout)

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=config.d_model,
            nhead=config.nhead,
            dim_feedforward=config.dim_feedforward,
            dropout=config.dropout,
            activation="gelu",
            batch_first=True,
            norm_first=True,  # pre-norm: markedly more stable on small datasets
        )
        self.encoder = nn.TransformerEncoder(
            encoder_layer,
            num_layers=config.num_layers,
            # The nested-tensor fast path breaks ONNX export. We are not using
            # padding masks (every clip is resampled to a fixed length), so we
            # lose nothing by turning it off.
            enable_nested_tensor=False,
        )

        self.norm = nn.LayerNorm(config.d_model)
        self.head = nn.Linear(config.d_model, config.num_classes)

        self._init_weights()

    def _init_weights(self) -> None:
        nn.init.trunc_normal_(self.cls_token, std=0.02)
        nn.init.trunc_normal_(self.positional, std=0.02)
        nn.init.zeros_(self.head.bias)
        nn.init.trunc_normal_(self.head.weight, std=0.02)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        batch_size = x.shape[0]

        x = self.input_projection(x)                       # (B, T, d_model)
        cls = self.cls_token.expand(batch_size, -1, -1)    # (B, 1, d_model)
        x = torch.cat([cls, x], dim=1)                     # (B, T+1, d_model)
        x = self.dropout(x + self.positional)

        x = self.encoder(x)
        return self.head(self.norm(x[:, 0]))               # classify the CLS token

    @torch.no_grad()
    def predict_proba(self, x: torch.Tensor) -> torch.Tensor:
        self.eval()
        return torch.softmax(self(x), dim=-1)

    def num_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)


def build_model(num_classes: int, **overrides) -> SignTransformer:
    return SignTransformer(ModelConfig(num_classes=num_classes, **overrides))


if __name__ == "__main__":
    # Smoke test: shapes line up and gradients flow.
    model = build_model(num_classes=100)
    batch = torch.randn(4, SEQUENCE_LENGTH, FEATURE_DIMS)
    logits = model(batch)

    print(f"parameters : {model.num_parameters():,}")
    print(f"input      : {tuple(batch.shape)}")
    print(f"logits     : {tuple(logits.shape)}")

    assert logits.shape == (4, 100)
    logits.sum().backward()
    assert model.cls_token.grad is not None, "gradients are not reaching the CLS token"

    probs = model.predict_proba(batch)
    assert torch.allclose(probs.sum(-1), torch.ones(4), atol=1e-5)
    print("smoke test passed")
