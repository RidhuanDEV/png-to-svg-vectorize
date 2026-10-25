"""Convert the official Real-ESRGAN weights (BSD-3-Clause, https://github.com/xinntao/Real-ESRGAN) to ONNX for the
optional "Enhance with AI" step. Run once by a maintainer; the app only downloads the resulting .onnx files.

    python tools/models/convert.py WEIGHTS_DIR OUT_DIR

Needs torch + onnx + onnxruntime (a separate environment: none of them ship with the app except onnxruntime).
The two network definitions below follow Real-ESRGAN / BasicSR (SRVGGNetCompact, RRDBNet) so the published weights
load unchanged. Weights are loaded with `weights_only=True`: no code from the downloaded file is executed.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

MODELS = {
    # name in the app         source weights (Real-ESRGAN release asset)          network
    'general-x4': ('realesr-general-x4v3.pth', 'compact'),
    'illustration-x4': ('RealESRGAN_x4plus_anime_6B.pth', 'rrdb6'),
}


class SRVGGNetCompact(nn.Module):
    def __init__(self, num_feat: int = 64, num_conv: int = 32, upscale: int = 4):
        super().__init__()
        self.upscale = upscale
        body: list[nn.Module] = [nn.Conv2d(3, num_feat, 3, 1, 1), nn.PReLU(num_parameters=num_feat)]
        for _ in range(num_conv):
            body += [nn.Conv2d(num_feat, num_feat, 3, 1, 1), nn.PReLU(num_parameters=num_feat)]
        body.append(nn.Conv2d(num_feat, 3 * upscale * upscale, 3, 1, 1))
        self.body = nn.ModuleList(body)
        self.upsampler = nn.PixelShuffle(upscale)

    def forward(self, x):
        out = x
        for layer in self.body:
            out = layer(out)
        out = self.upsampler(out)
        return out + F.interpolate(x, scale_factor=self.upscale, mode='nearest')


class ResidualDenseBlock(nn.Module):
    def __init__(self, num_feat: int = 64, num_grow_ch: int = 32):
        super().__init__()
        self.conv1 = nn.Conv2d(num_feat, num_grow_ch, 3, 1, 1)
        self.conv2 = nn.Conv2d(num_feat + num_grow_ch, num_grow_ch, 3, 1, 1)
        self.conv3 = nn.Conv2d(num_feat + 2 * num_grow_ch, num_grow_ch, 3, 1, 1)
        self.conv4 = nn.Conv2d(num_feat + 3 * num_grow_ch, num_grow_ch, 3, 1, 1)
        self.conv5 = nn.Conv2d(num_feat + 4 * num_grow_ch, num_feat, 3, 1, 1)
        self.lrelu = nn.LeakyReLU(negative_slope=0.2, inplace=True)

    def forward(self, x):
        x1 = self.lrelu(self.conv1(x))
        x2 = self.lrelu(self.conv2(torch.cat((x, x1), 1)))
        x3 = self.lrelu(self.conv3(torch.cat((x, x1, x2), 1)))
        x4 = self.lrelu(self.conv4(torch.cat((x, x1, x2, x3), 1)))
        x5 = self.conv5(torch.cat((x, x1, x2, x3, x4), 1))
        return x5 * 0.2 + x


class RRDB(nn.Module):
    def __init__(self, num_feat: int, num_grow_ch: int = 32):
        super().__init__()
        self.rdb1 = ResidualDenseBlock(num_feat, num_grow_ch)
        self.rdb2 = ResidualDenseBlock(num_feat, num_grow_ch)
        self.rdb3 = ResidualDenseBlock(num_feat, num_grow_ch)

    def forward(self, x):
        return self.rdb3(self.rdb2(self.rdb1(x))) * 0.2 + x


class RRDBNet(nn.Module):
    def __init__(self, num_feat: int = 64, num_block: int = 6, num_grow_ch: int = 32):
        super().__init__()
        self.conv_first = nn.Conv2d(3, num_feat, 3, 1, 1)
        self.body = nn.Sequential(*[RRDB(num_feat, num_grow_ch) for _ in range(num_block)])
        self.conv_body = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_up1 = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_up2 = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_hr = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_last = nn.Conv2d(num_feat, 3, 3, 1, 1)
        self.lrelu = nn.LeakyReLU(negative_slope=0.2, inplace=True)

    def forward(self, x):
        feat = self.conv_first(x)
        feat = feat + self.conv_body(self.body(feat))
        feat = self.lrelu(self.conv_up1(F.interpolate(feat, scale_factor=2, mode='nearest')))
        feat = self.lrelu(self.conv_up2(F.interpolate(feat, scale_factor=2, mode='nearest')))
        return self.conv_last(self.lrelu(self.conv_hr(feat)))


def build(kind: str) -> nn.Module:
    return SRVGGNetCompact() if kind == 'compact' else RRDBNet(num_block=6)


def load(kind: str, path: Path) -> nn.Module:
    state = torch.load(path, map_location='cpu', weights_only=True)
    state = state.get('params_ema') or state.get('params') or state
    net = build(kind)
    net.load_state_dict(state, strict=True)
    return net.eval()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def convert(weights_dir: Path, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for name, (src, kind) in MODELS.items():
        net = load(kind, weights_dir / src)
        dst = out_dir / f'{name}.onnx'
        sample = torch.rand(1, 3, 64, 64)
        torch.onnx.export(net, sample, dst, input_names=['input'], output_names=['output'], opset_version=17,
                          dynamic_axes={'input': {2: 'h', 3: 'w'}, 'output': {2: 'h4', 3: 'w4'}}, dynamo=False)
        # the ONNX graph must reproduce the PyTorch network
        import onnxruntime as ort
        sess = ort.InferenceSession(str(dst), providers=['CPUExecutionProvider'])
        x = torch.rand(1, 3, 48, 80)
        with torch.no_grad():
            ref = net(x).numpy()
        got = sess.run(None, {'input': x.numpy()})[0]
        err = float(np.abs(ref - got).max())
        assert got.shape == (1, 3, 192, 320), got.shape
        assert err < 1e-3, f'{name}: onnx differs from torch by {err}'
        manifest[name] = {'file': dst.name, 'bytes': dst.stat().st_size, 'sha256': sha256(dst), 'scale': 4,
                          'source': src, 'source_sha256': sha256(weights_dir / src), 'max_abs_error': err}
        print(f'{name}: {dst.stat().st_size / 1e6:.1f} MB, max |onnx - torch| = {err:.2e}')
    (out_dir / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return manifest


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    convert(Path(sys.argv[1]), Path(sys.argv[2]))
