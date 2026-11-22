"""Baut den KI-Upscaler (Real-ESRGAN general x4v3, BSD-3) als ONNX für das Programm.

Aufruf (im Build-Workflow): python tools/make_upscaler.py <gewichte.pth> <ziel.onnx>
Die Netzarchitektur (SRVGGNetCompact) ist hier nachgebaut, damit kein basicsr nötig ist."""
import sys

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F


class SRVGGNetCompact(nn.Module):
    def __init__(self, num_in_ch=3, num_out_ch=3, num_feat=64, num_conv=32, upscale=4):
        super().__init__()
        self.upscale = upscale
        self.body = nn.ModuleList()
        self.body.append(nn.Conv2d(num_in_ch, num_feat, 3, 1, 1))
        self.body.append(nn.PReLU(num_parameters=num_feat))
        for _ in range(num_conv):
            self.body.append(nn.Conv2d(num_feat, num_feat, 3, 1, 1))
            self.body.append(nn.PReLU(num_parameters=num_feat))
        self.body.append(nn.Conv2d(num_feat, num_out_ch * upscale * upscale, 3, 1, 1))
        self.upsampler = nn.PixelShuffle(upscale)

    def forward(self, x):
        out = x
        for layer in self.body:
            out = layer(out)
        out = self.upsampler(out)
        return out + F.interpolate(x, scale_factor=self.upscale, mode='nearest')


src, dst = sys.argv[1], sys.argv[2]
sd = torch.load(src, map_location='cpu')
sd = sd.get('params_ema') or sd.get('params') or sd
net = SRVGGNetCompact()
net.load_state_dict(sd, strict=True)
net.eval()
x = torch.rand(1, 3, 64, 96)
kw = dict(input_names=['input'], output_names=['output'], opset_version=17,
          dynamic_axes={'input': {2: 'h', 3: 'w'}, 'output': {2: 'H', 3: 'W'}})
try:
    torch.onnx.export(net, x, dst, dynamo=False, **kw)
except TypeError:
    torch.onnx.export(net, x, dst, **kw)
import onnxruntime as ort  # noqa: E402
s = ort.InferenceSession(dst, providers=['CPUExecutionProvider'])
y = s.run(None, {'input': x.numpy()})[0]
with torch.no_grad():
    ref = net(x).numpy()
err = float(np.abs(y - ref).max())
print('ONNX ok, Ausgabe', y.shape, 'max. Abweichung', err)
if y.shape != (1, 3, 256, 384) or err > 1e-3:
    raise SystemExit('ONNX-Umwandlung fehlerhaft')
