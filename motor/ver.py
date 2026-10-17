"""Mirar un vídeo gastando pocos tokens.

Uso:
  python motor/ver.py <video> [--cada 3] [--ancho 320]   hoja de contactos (un fotograma cada N s con su tiempo)
  python motor/ver.py <video> --t 14.5                    un fotograma del bruto con cuadrícula de coordenadas
                                                         (cada 160 px del 1920x1080) para elegir recortes de pantalla
Escribe la imagen en trabajo/ e imprime su ruta.
"""
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from comun import RAIZ  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("video")
ap.add_argument("--cada", type=float, default=3)
ap.add_argument("--ancho", type=int, default=320)
ap.add_argument("--t", type=float)
a = ap.parse_args()
v = Path(a.video).resolve()
fuente = "fontfile=fuentes/SofiaSans-BlackItalic.ttf"

if a.t is not None:
    # Fotograma a 960x540 (escala 0,5): líneas cada 160 px del original, etiquetadas con su coordenada original
    lineas = []
    for x in range(160, 1920, 160):
        lineas.append(f"drawbox=x={x // 2}:y=0:w=1:h=540:color=cyan@0.7:t=fill")
        lineas.append(f"drawtext={fuente}:text='{x}':x={x // 2 + 2}:y=2:fontsize=14:fontcolor=cyan:box=1:boxcolor=black")
    for y in range(160, 1080, 160):
        lineas.append(f"drawbox=x=0:y={y // 2}:w=960:h=1:color=cyan@0.7:t=fill")
        lineas.append(f"drawtext={fuente}:text='{y}':x=2:y={y // 2 + 2}:fontsize=14:fontcolor=cyan:box=1:boxcolor=black")
    dst = RAIZ / "trabajo" / f"{v.stem}.t{a.t:g}.jpg"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(a.t), "-i", str(v), "-frames:v", "1", "-vf",
                    "scale=960:540," + ",".join(lineas), str(dst)], cwd=RAIZ, check=True)
else:
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                str(v)], capture_output=True, text=True, check=True).stdout)
    n = max(1, int(dur / a.cada))
    cols = 6 if a.ancho <= 320 else 4
    dst = RAIZ / "trabajo" / (v.stem + ".hoja.jpg")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(v), "-vf",
                    f"fps=1/{a.cada},scale={a.ancho}:-2,drawtext={fuente}:"
                    rf"text='%{{pts\:hms}}':x=4:y=4:fontsize=22:fontcolor=yellow:box=1,tile={cols}x{-(-n // cols)}",
                    "-frames:v", "1", str(dst)], cwd=RAIZ, check=True)
print(dst)
