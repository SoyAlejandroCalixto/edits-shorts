"""Genera trabajo/<nombre>/subs.json: trozos de subtítulo de 2–4 palabras con sus tiempos.

Uso: python motor/subtitulos.py trabajo/<nombre>
Después Claude revisa subs.json y corrige el texto (nombres propios, palabras mal oídas) sin tocar los tiempos.
No sobrescribe un subs.json existente salvo con --forzar.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from comun import CONFIG, cargar_palabras  # noqa: E402

S = CONFIG["subtitulos"]


def limpiar(w: str) -> str:
    return re.sub(r"[.,;:!¡?¿…\"]", "", w).upper()


def trozos(palabras: list[dict]) -> list[dict]:
    out, actual = [], []

    def cerrar():
        if actual:
            out.append({"s": actual[0]["s"], "e": actual[-1]["e"], "texto": " ".join(limpiar(w["w"]) for w in actual)})
            actual.clear()

    for i, w in enumerate(palabras):
        if actual:
            texto = " ".join(limpiar(x["w"]) for x in actual + [w])
            if (len(actual) >= S["max_palabras"] or len(texto) > S["max_caracteres"]
                    or w["s"] - actual[-1]["e"] > 0.35):
                cerrar()
        actual.append(w)
        if re.search(r"[.?!…,]$", w["w"]):
            cerrar()
    cerrar()
    # Sin huecos parpadeantes: cada trozo dura hasta el siguiente (máx. 0,4 s de cola tras la última palabra)
    for a, b in zip(out, out[1:]):
        a["e"] = round(min(b["s"], a["e"] + 0.4) if b["s"] - a["e"] > 0.4 else b["s"], 3)
    if out:
        out[-1]["e"] = round(out[-1]["e"] + 0.3, 3)
    return [t for t in out if t["texto"]]


def main():
    trabajo = Path(sys.argv[1]).resolve()
    dst = trabajo / "subs.json"
    if dst.exists() and "--forzar" not in sys.argv:
        print(f"{dst} ya existe (usa --forzar para regenerarlo)")
        return
    palabras = cargar_palabras(trabajo)
    subs = trozos(palabras)
    dst.write_text(json.dumps(subs, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"{len(subs)} subtítulos -> {dst}")
    # Whisper estira palabras (sobre todo la primera de una frase) cuando suena el reel o el público: el subtítulo
    # salía segundos antes de que hablara. Avisa de las sospechosas para comprobar con la boca (ver.py --boca)
    for w in palabras:
        if w["e"] - w["s"] > S.get("palabra_max", 0.6) * (1 + len(w["w"]) / 8):
            print(f"  ¿estirada? {w['w']!r} {w['s']:.2f}-{w['e']:.2f}: mira dónde empieza a hablar con "
                  f"python motor/ver.py <bruto> --boca {max(0, w['s'] - 0.3):.1f} {w['e'] + 0.3:.1f}")


if __name__ == "__main__":
    main()
