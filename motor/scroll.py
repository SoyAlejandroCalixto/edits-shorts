"""Mide el scroll de la página del bruto fotograma a fotograma (a 30 fps, los del short) para que el recorte de abajo
lo siga con "seguir" y lo enfocado no se mueva.

Uso: python motor/scroll.py <bruto> <desde> <hasta> [--x 180 --w 400]
Imprime [t, desplazamiento vertical en px] en cada fotograma donde cambia (negativo = el contenido sube) respecto al
primero. En "seguir": y del centro = y antes del scroll + desplazamiento. --x/--w = columnas del bruto que se comparan
(una zona de la página sin la cámara ni el ratón encima).
"""
import argparse
import subprocess

import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("video")
ap.add_argument("desde", type=float)
ap.add_argument("hasta", type=float)
ap.add_argument("--x", type=int, default=180)
ap.add_argument("--w", type=int, default=400)
args = ap.parse_args()

a = round(args.desde * 30) / 30   # en la rejilla de 30 fps del short
H = 1000
r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{a:.4f}", "-t", f"{args.hasta - a:.3f}", "-i", args.video,
                    "-vf", f"fps=30,crop={args.w}:{H}:{args.x}:60,format=gray", "-f", "rawvideo", "-"],
                   capture_output=True, check=True)
f = np.frombuffer(r.stdout, np.uint8).reshape(-1, H, args.w).astype(np.float32)
ref, prev, out = f[0], None, []
for i, x in enumerate(f):
    err = {s: np.abs(ref[max(0, s):H + min(0, s)] - x[max(0, -s):H - max(0, s)]).mean() for s in range(-400, 401)}
    d = -min(err, key=err.get)
    if d != prev:
        out.append([round(a + i / 30, 3), d])
    prev = d
print(out)
