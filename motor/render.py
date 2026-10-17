"""Renderiza un short 1080x1920@30 a salida/short-N.mp4.

Uso: python motor/render.py trabajo/<nombre> [--salida ruta.mp4]

Lee trabajo/<nombre>/decisiones.json y subs.json:
{
  "video": "brutos/x.mp4",
  "pantalla": [{"desde": 0, "centro": [640, 520], "ancho": 1000}, ...],   recorte de pantalla por tramo (s del bruto,
                 píxeles del bruto 1920x1080); se mantiene hasta el siguiente "desde". ancho <= 1040.
  "imagenes": [{"t": "L5:3", "archivo": "imagenes/x.jpg"}, ...],          abajo, con cam shot; "dur" opcional
  "zooms": [[2.0, 5.5], ...]                                              opcional: fuerza los tramos de mini-zoom
}
Tiempos "t": "L5" = inicio de la línea, "L5:3" = inicio de su palabra 3 (0 = primera), o segundos.
"""
import argparse
import json
import random
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from comun import CONFIG, RAIZ, cargar_palabras, lineas  # noqa: E402

W, H, FPS = CONFIG["salida"]["ancho"], CONFIG["salida"]["alto"], CONFIG["salida"]["fps"]
CAM, Z, SUB = CONFIG["camara"], CONFIG["zoom"], CONFIG["subtitulos"]
CAM_H = round(W * CAM["h"] / CAM["w"] / 2) * 2          # altura de la cámara en reposo (807)
CAM_HZ = round(CAM_H * Z["factor"] / 2) * 2             # altura de la cámara en mini-zoom (1062)
BOT = H - CAM_H                                          # alto de la capa de abajo (1113)
PAD = round(CAM["h"] * CAM_HZ / CAM_H / 2) * 2 + 4       # alto de la cámara con relleno transparente debajo


def ff(args: list[str]):
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", *args], cwd=RAIZ, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"ffmpeg falló:\n{r.stderr[-3000:]}")


def rel(p) -> str:
    """Rutas relativas a RAIZ: evitan los ':' de C:\\ dentro de los filtros de ffmpeg."""
    return Path(p).resolve().relative_to(RAIZ).as_posix()


def duracion(p: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True, check=True)
    return float(r.stdout)


def tramos_zoom(subs: list[dict], dur: float) -> list[list[float]]:
    """Alterna normal / mini-zoom cambiando siempre al empezar un subtítulo."""
    rnd = random.Random(Z["semilla"])
    zoom, ini, out = Z["empieza_con_zoom"], 0.0, []
    objetivo = rnd.uniform(*Z["dur_zoom" if zoom else "dur_normal"])
    for s in subs[1:]:
        if s["s"] - ini >= objetivo and dur - s["s"] > 1.5:
            if zoom:
                out.append([ini, s["s"]])
            zoom, ini = not zoom, s["s"]
            objetivo = rnd.uniform(*Z["dur_zoom" if zoom else "dur_normal"])
    if zoom:
        out.append([ini, dur])
    return out


def en_zoom(zooms) -> str:
    return "+".join(f"(gte(t,{a:.3f})*lt(t,{b:.3f}))" for a, b in zooms) or "0"


def factor_camara(zooms) -> str:
    """Escala de la cámara: reposo = cabe a 1080 de ancho; mini-zoom = x factor con zoom lento desde su inicio."""
    f1 = W / CAM["w"]
    f2 = f1 * Z["factor"]
    expr = f"{f1:.5f}"
    for a, b in zooms:
        expr = f"if(gte(t,{a:.3f})*lt(t,{b:.3f}),{f2:.5f}*(1+{Z['lento_por_segundo']}*(t-{a:.3f})),{expr})"
    return expr


def pantalla_expr(tramos: list[dict], clave) -> str:
    """Valor por tramos de pantalla (escala, centro x o centro y) en función de t."""
    tramos = sorted(tramos, key=lambda p: p["desde"])
    expr = f"{clave(tramos[0]):.5f}"
    for p in tramos[1:]:
        expr = f"if(gte(t,{p['desde']:.3f}),{clave(p):.5f},{expr})"
    return expr


def escribir_ass(subs: list[dict], dst: Path):
    def ts(s):
        return f"{int(s // 3600)}:{int(s % 3600 // 60):02d}:{s % 60:05.2f}"
    cab = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
ScaledBorderAndShadow: yes
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: S,Sofia Sans Black,{SUB['tam']},{SUB['color']},{SUB['color']},&H00000000,&H00000000,0,-1,0,0,100,100,0,0,1,0,{SUB['sombra']},5,40,40,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    filas = [f"Dialogue: 0,{ts(s['s'])},{ts(s['e'])},S,,0,0,0,,{{\\an5\\pos({W // 2},{SUB['y']})\\blur0}}{s['texto']}"
             for s in subs]
    dst.write_text(cab + "\n".join(filas) + "\n", encoding="utf-8")


def siguiente_salida() -> Path:
    n = 1
    while (RAIZ / "salida" / f"short-{n}.mp4").exists():
        n += 1
    return RAIZ / "salida" / f"short-{n}.mp4"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("trabajo")
    ap.add_argument("--salida")
    args = ap.parse_args()

    trabajo = Path(args.trabajo).resolve()
    dec = json.loads((trabajo / "decisiones.json").read_text(encoding="utf-8"))
    subs = json.loads((trabajo / "subs.json").read_text(encoding="utf-8"))
    palabras = cargar_palabras(trabajo)
    lin = {l["id"]: l for l in lineas(palabras)}
    video = RAIZ / dec["video"]
    dur = duracion(video)

    def tiempo(t) -> float:
        if isinstance(t, (int, float)):
            return float(t)
        lid, _, k = t.partition(":")
        l = lin[lid]
        return palabras[min(l["i0"] + int(k or 0), l["i1"])]["s"]

    # Imágenes: desde su palabra hasta el fin de frase que deje al menos imagen_min_dur
    fins = sorted(l["e"] for l in lin.values())
    imagenes = []
    for im in dec.get("imagenes", []):
        a = tiempo(im["t"])
        if im.get("dur"):
            b = a + im["dur"]
        else:
            b = next((e for e in fins if e - a >= CONFIG["imagen_min_dur"]), dur)
        imagenes.append({"archivo": im["archivo"], "a": a, "b": min(b + 0.1, dur)})
    imagenes.sort(key=lambda i: i["a"])
    for x, y in zip(imagenes, imagenes[1:]):
        x["b"] = min(x["b"], y["a"])

    zooms = dec.get("zooms") or tramos_zoom(subs, dur)
    pant = dec.get("pantalla") or [{"desde": 0, **CONFIG["pantalla_por_defecto"]}]
    esc = pantalla_expr(pant, lambda p: W / min(p["ancho"], 1040))
    cx = pantalla_expr(pant, lambda p: p["centro"][0])
    cy = pantalla_expr(pant, lambda p: p["centro"][1])
    fcam = factor_camara(zooms)
    zz = en_zoom(zooms)

    ass = trabajo / "subs.ass"
    escribir_ass(subs, ass)

    entradas = ["-i", rel(video)]
    fc = [f"color=c=black:s={W}x{H}:r={FPS}:d={dur:.3f}[lienzo]",
          f"[0:v]fps={FPS},split[vc][vs]",
          # Cámara: recorte del bruto con relleno transparente debajo, escala por fotograma, centrada arriba
          f"[vc]crop={CAM['w']}:{CAM['h']}:{CAM['x']}:{CAM['y']},format=yuva420p,"
          f"pad={CAM['w']}:{PAD}:0:0:color=black@0,"
          f"scale=w='trunc({CAM['w']}*{fcam}/2)*2':h='trunc({PAD}*{fcam}/2)*2':eval=frame,"
          f"crop={W}:{CAM_HZ}:x='(iw-{W})/2':y='max(0,(ih*{CAM['h']}/{PAD}-{CAM_HZ})/2)'[cam]",
          # Pantalla: recorte por tramo escalado a la capa de abajo
          f"[vs]scale=w='trunc(1920*{esc}/2)*2':h='trunc(1080*{esc}/2)*2':eval=frame,"
          f"crop={W}:{BOT}:x='max(0,min(iw-{W},{cx}*{esc}-{W // 2}))':y='max(0,min(ih-{BOT},{cy}*{esc}-{BOT // 2}))'[p0]"]
    ult = "p0"
    for k, im in enumerate(imagenes, start=1):
        entradas += ["-loop", "1", "-framerate", str(FPS), "-t", f"{im['b'] - im['a']:.3f}", "-i", im["archivo"]]
        fc.append(f"[{k}:v]scale={W}:{BOT}:force_original_aspect_ratio=increase,crop={W}:{BOT},setsar=1,"
                  f"format=yuv420p,setpts=PTS-STARTPTS+{im['a']:.3f}/TB[i{k}]")
        fc.append(f"[{ult}][i{k}]overlay=eof_action=pass:enable='between(t,{im['a']:.3f},{im['b']:.3f})'[p{k}]")
        ult = f"p{k}"
    # La capa de abajo baja con la cámara en mini-zoom y se centra en el hueco que queda
    fc.append(f"[lienzo][{ult}]overlay=x=0:y='{CAM_H}+({CAM_HZ}-{CAM_H})/2*({zz})':eval=frame[l1]")
    fc.append(f"[l1][cam]overlay=0:0,subtitles={rel(ass)}:fontsdir=fuentes,format=yuv420p[vout]")

    amix = ["[0:a]"]
    base = 1 + len(imagenes)
    for j, im in enumerate(imagenes):
        entradas += ["-i", "recursos/cam shot.wav"]
        fc.append(f"[{base + j}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={round(im['a'] * 1000)}:all=1[s{j}]")
        amix.append(f"[s{j}]")
    fc.append(f"{''.join(amix)}amix=inputs={len(amix)}:normalize=0:duration=first,alimiter=limit=0.97[aout]"
              if len(amix) > 1 else "[0:a]anull[aout]")

    script = trabajo / "filtro.txt"
    script.write_text(";\n".join(fc), encoding="utf-8")
    salida = Path(args.salida).resolve() if args.salida else siguiente_salida()
    salida.parent.mkdir(parents=True, exist_ok=True)
    ff([*entradas, "-/filter_complex", rel(script), "-map", "[vout]", "-map", "[aout]", "-t", f"{dur:.3f}",
        "-r", str(FPS), *CONFIG["encoder"], "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart", rel(salida)])
    print(f"{len(zooms)} mini-zooms, {len(pant)} tramos de pantalla, {len(imagenes)} imágenes -> {salida}")


if __name__ == "__main__":
    main()
