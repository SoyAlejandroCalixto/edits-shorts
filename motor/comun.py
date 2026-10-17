"""Utilidades compartidas por los scripts del motor."""
import json
import re
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CONFIG = json.loads((RAIZ / "motor" / "config.json").read_text(encoding="utf-8"))


def slug(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z0-9]+", "-", t).strip("-").lower() or "video"


def carpeta_trabajo(video: Path) -> Path:
    d = RAIZ / "trabajo" / slug(video.stem)
    d.mkdir(parents=True, exist_ok=True)
    return d


def cargar_palabras(trabajo: Path) -> list[dict]:
    return json.loads((trabajo / "palabras.json").read_text(encoding="utf-8"))


def lineas(palabras: list[dict], hueco=0.5, max_dur=12.0) -> list[dict]:
    """Agrupa palabras en frases: corta en pausas > hueco, en fin de oración o a los max_dur s."""
    out, actual = [], []
    for i, w in enumerate(palabras):
        if actual and (w["s"] - actual[-1]["e"] > hueco or w["e"] - actual[0]["s"] > max_dur):
            out.append(actual)
            actual = []
        actual.append({**w, "i": i})
        if re.search(r"[.?!…]$", w["w"]):
            out.append(actual)
            actual = []
    if actual:
        out.append(actual)
    return [{"id": f"L{n + 1}", "s": l[0]["s"], "e": l[-1]["e"], "i0": l[0]["i"], "i1": l[-1]["i"],
             "texto": " ".join(w["w"] for w in l)} for n, l in enumerate(out)]


def empaquetar(palabras: list[dict]) -> str:
    cab = ("# Transcript (tiempos en s del bruto). Formato: ID inicio-fin (pausa previa) | texto\n"
           "# Palabras de una línea con tiempos: python motor/palabras.py <trabajo> L12\n")
    filas, prev = [], None
    for l in lineas(palabras):
        pausa = f" (+{l['s'] - prev:.1f})" if prev is not None and l["s"] - prev >= 1.0 else ""
        filas.append(f"{l['id']} {l['s']:.2f}-{l['e']:.2f}{pausa} | {l['texto']}")
        prev = l["e"]
    return cab + "\n".join(filas) + "\n"
