"""Muestra las palabras de una o varias líneas con su índice y tiempos.

Uso: python motor/palabras.py trabajo/<nombre> L12 [L13 ...]
Sirve para elegir cortes dentro de una línea ("L12:3-L12:9").
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from comun import cargar_palabras, lineas  # noqa: E402

trabajo = Path(sys.argv[1])
pal = cargar_palabras(trabajo)
lin = {l["id"]: l for l in lineas(pal)}
for lid in sys.argv[2:]:
    l = lin[lid]
    print(lid, " ".join(f"{k}:{pal[i]['w']}@{pal[i]['s']:.2f}" for k, i in enumerate(range(l["i0"], l["i1"] + 1))))
