"""Borra lo efímero del proyecto: el contenido de trabajo/ y salida/ (y cachés de Python).

Uso: python motor/limpiar.py [--brutos]
  --brutos  borra también los brutos de entrada (brutos/ y, si existe, imagenes/)
Las carpetas se conservan vacías. Imprime lo que borra.
"""
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
carpetas = ["trabajo", "salida"] + (["brutos", "imagenes"] if "--brutos" in sys.argv else [])

total = 0
for nombre in carpetas:
    d = RAIZ / nombre
    if not d.is_dir():
        continue
    for p in d.iterdir():
        total += sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.is_dir() else p.stat().st_size
        shutil.rmtree(p) if p.is_dir() else p.unlink()
        print(f"borrado {nombre}/{p.name}")
cache = RAIZ / "motor" / "__pycache__"
if cache.is_dir():
    shutil.rmtree(cache)
print(f"liberados {total / 1e6:.0f} MB")
