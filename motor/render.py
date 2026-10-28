"""Renderiza un short 1080x1920@30 a salida/short-N.mp4.

Uso: python motor/render.py trabajo/<nombre> [--salida ruta.mp4]

Lee trabajo/<nombre>/decisiones.json y subs.json:
{
  "video": "brutos/x.mp4",
  "pantalla": [{"desde": 0, "centro": [640, 520], "ancho": 1000}, ...],   recorte de pantalla por tramo (s del bruto,
                 píxeles del bruto 1920x1080); se mantiene hasta el siguiente "desde". ancho <= 1040.
                 "seguir": [[t, x, y], ...] opcional: el centro va en línea recta de punto a punto (jugadas: seguir
                 al que lleva el balón)
                 "centro_zoom": [x, y] opcional: centro durante el mini-zoom (la capa baja 128 px y la cámara tapa sus
                 128 px de arriba); puede quedar por encima del bruto para que lo de arriba (caras) no quede tapado
  "imagenes": [{"t": "L5:3", "archivo": "imagenes/x.jpg"}, ...],          con cam shot; "dur" o "hasta" opcional;
                 "modo": "abajo" (debajo de la cara, sin deformar; por defecto, config "imagen_modo") o "estirar"
                 (solo memes: deformada a toda la pantalla 1080x1920)
  "completa": [{"desde": 2.67, "hasta": 4.53, "modo": "estirar"}, ...],   tramos del propio bruto a pantalla completa
                 (tapan cámara y pantalla; los subtítulos siguen encima). "estirar" = el fotograma 16:9 deformado a
                 9:16 (memes); "proporcion" = recorte 9:16 sin deformar centrado en "centro": [x, y] del bruto
  "zooms": [[2.0, 5.5], ...]                                              opcional: fuerza los tramos de mini-zoom ([] = ninguno)
  "cara_encima": [x, y, w, h]                                             opcional: tapa esa caja del bruto (la cámara de
                 otro que reacciona dentro del vídeo) con la cámara del usuario, rellenándola sin deformar
  "reel": [x, y, w, h]                                                    opcional: el short es solo esa caja del bruto (un
                 reel vertical) a pantalla completa, sin la cámara de arriba; el mini-zoom acerca hacia
                 "centro_zoom": [x, y] (por defecto el centro de cara_encima). Sin imágenes ni "completa"
  "titulos": [{"desde": 0, "hasta": 1.565, "texto": "¿VENDER A\\NMBAPPÉ?"}]  título grande en el centro (\\N = salto
                 de línea)
}
Tiempos "t": "L5" = inicio de la línea, "L5:3" = inicio de su palabra 3 (0 = primera), o segundos.
"""
import argparse
import json
import re
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


# Palabras que, en mayúscula y sin puntuación delante, marcan el inicio de una frase (Whisper a veces no pone puntos)
INICIOS = set("""y o pero que lo la el los las es fue era sea no ni han ha hay necesitan primero segundo tercero
    además entonces porque pues culpa tú te yo a en con para por si cuando como mientras luego claro""".split())


def cortes_camara(video: Path) -> list[tuple[float, float]]:
    """Cortes del bruto (jump cuts) vistos en la cámara: [(t del primer fotograma nuevo, fuerza), ...].
    Fuerza = diferencia entre fotogramas / mediana local; un gesto da picos con la mediana alta, un corte no."""
    import numpy as np
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=r_frame_rate",
                        "-of", "csv=p=0", str(video)], capture_output=True, text=True, check=True)
    num, _, den = r.stdout.split()[0].partition("/")
    fps = float(num) / float(den or 1)
    w, h = 138, 104
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vf",
                        f"crop={CAM['w']}:{CAM['h']}:{CAM['x']}:{CAM['y']},scale={w}:{h},format=gray",
                        "-f", "rawvideo", "-"], capture_output=True, check=True)
    f = np.frombuffer(r.stdout, np.uint8).reshape(-1, h, w).astype(np.float32)
    d = np.abs(np.diff(f, axis=0)).mean(axis=(1, 2))
    C = CONFIG["cortes"]
    out = []
    for i in range(len(d)):
        fuerza = d[i] / max(float(np.median(d[max(0, i - 15):i + 16])), 0.1)
        if d[i] >= C["min"] and fuerza >= C["fuerza"] and d[i] == d[max(0, i - 3):i + 4].max():
            out.append(((i + 1) / fps, fuerza))
    return out


def niveles_voz(video: Path):
    """Nivel del audio en dB cada 10 ms (para afinar los inicios de palabra de Whisper)."""
    import numpy as np
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000",
                        "-f", "f32le", "-"], capture_output=True, check=True)
    a = np.frombuffer(r.stdout, np.float32)
    n = len(a) // 160
    return 20 * np.log10(np.sqrt((a[:n * 160].reshape(n, 160).astype(np.float64) ** 2).mean(axis=1)) + 1e-9)


def arranque_voz(db, s: float) -> float:
    """Inicio real de la palabra que Whisper da en s (llega hasta ~0,25 s tarde): tras el silencio más hondo de los
    0,4 s previos, el primer instante en que la voz sube. Sin silencio claro (≥ 20 dB por debajo), s tal cual."""
    if db is None:
        return s
    i1 = min(round(s * 100), len(db) - 1)
    i0 = max(0, i1 - 40)
    if i1 - i0 < 3:
        return s
    m = i0 + int(db[i0:i1].argmin())
    ref = float(db[m:min(i1 + 10, len(db))].max())
    if ref - db[m] < 20:
        return s
    umbral = db[m] + 0.6 * (ref - db[m])
    k = next(k for k in range(m, len(db)) if db[k] >= umbral)
    return min(s, k / 100 - 0.01)


def fronteras_frase(palabras: list[dict], cortes=(), db=None) -> list[float]:
    """Inicios de frase: tras coma, punto, etc. o en una palabra en mayúscula que suele abrir frase.
    Si hay un corte del bruto entre la palabra anterior y la que abre frase, la frontera es el corte (Whisper da el
    inicio de palabra hasta ~0,25 s tarde y el zoom quedaba desfasado del corte). Un corte fuerte en una pausa también
    abre frase aunque el texto no lo marque. Sin corte, la frontera es el arranque real de la voz (arranque_voz), no el
    inicio de Whisper, para no cambiar de plano a mitad de la palabra."""
    C = CONFIG["cortes"]
    out = []
    for a, b in zip(palabras, palabras[1:]):
        w = b["w"].strip("¿¡\"'")
        texto = bool(re.search(r"[,.;:?!…]$", a["w"]) or (w[:1].isupper() and w.lower().strip(",.") in INICIOS))
        m = C["margen"] if texto else 0.1   # sin puntuación, solo si el corte cae en la pausa entre palabras
        cerca = [(t, f) for t, f in cortes if a["e"] - m <= t <= b["s"] + m and (texto or f >= C["fuerza_sola"])]
        if cerca:
            t = min(cerca, key=lambda c: abs(c[0] - b["s"]))[0]   # el corte suele caer justo antes de hablar
            if not out or t - 0.002 > out[-1]:
                # Un pelo antes del fotograma del corte: con 3 decimales (1.567 > 1.5667) se perdía el primero
                out.append(t - 0.002)
            continue
        if texto:
            t = max(arranque_voz(db, b["s"]), a["e"] - 0.1)
            if not out or t > out[-1]:
                out.append(t)
    return out


def tramos_zoom(fronteras: list[float], dur: float) -> list[list[float]]:
    """Alterna normal / mini-zoom solo en inicios de frase; las frases cortas se juntan hasta durar frase_min.
    El primer plano es siempre normal (regla del canal: nunca se empieza con zoom)."""
    zoom, ini, out = False, 0.0, []
    for t in fronteras:
        if t - ini >= Z["frase_min"] and dur - t >= Z["frase_min"]:
            if zoom:
                out.append([ini, t])
            zoom, ini = not zoom, t
    if zoom:
        out.append([ini, dur])
    return out


def en_zoom(zooms) -> str:
    return "+".join(f"(gte(t,{a:.3f})*lt(t,{b:.3f}))" for a, b in zooms) or "0"


def factor_camara(zooms, f1=W / CAM["w"]) -> str:
    """Escala de la cámara: reposo = cabe a 1080 de ancho (o f1); mini-zoom = x factor con zoom lento desde su
    inicio."""
    f2 = f1 * Z["factor"]
    expr = f"{f1:.5f}"
    for a, b in zooms:
        expr = f"if(gte(t,{a:.3f})*lt(t,{b:.3f}),{f2:.5f}*(1+{Z['lento_por_segundo']}*(t-{a:.3f})),{expr})"
    return expr


def alinear_pantalla(tramos: list[dict], fronteras: list[float]) -> list[dict]:
    """Mueve cada cambio de recorte al inicio de frase más cercano a ≤ 3 s (salvo "exacto": true) y quita los que se
    pisan."""
    out = []
    for p in sorted(tramos, key=lambda p: p["desde"]):
        cerca = [f for f in fronteras if abs(f - p["desde"]) <= 3.0]
        if p["desde"] > 0 and not p.get("exacto") and cerca:
            p = {**p, "desde": min(cerca, key=lambda f: abs(f - p["desde"]))}
        if out and p["desde"] <= out[-1]["desde"]:
            out[-1] = p
        else:
            out.append(p)
    return out


def seguir_expr(puntos: list, i: int) -> str:
    """Centro que se mueve en línea recta entre los puntos [t, x, y] de "seguir" (coordenada i: 1 = x, 2 = y)."""
    puntos = sorted(puntos)
    expr = f"{puntos[-1][i]:.3f}"
    for (t0, *a), (t1, *b) in reversed(list(zip(puntos, puntos[1:]))):
        v0, v1 = a[i - 1], b[i - 1]
        expr = f"if(lt(t,{t1:.3f}),{v0:.3f}+({v1 - v0:.3f})*(t-{t0:.3f})/{t1 - t0:.3f},{expr})"
    return f"if(lt(t,{puntos[0][0]:.3f}),{puntos[0][i]:.3f},{expr})"


def pantalla_expr(tramos: list[dict], clave) -> str:
    """Valor por tramos de pantalla (escala, centro x o centro y) en función de t; clave puede devolver una expresión."""
    tramos = sorted(tramos, key=lambda p: p["desde"])
    num = lambda v: v if isinstance(v, str) else f"{v:.5f}"
    expr = num(clave(tramos[0]))
    for p in tramos[1:]:
        expr = f"if(gte(t,{p['desde']:.3f}),{num(clave(p))},{expr})"
    return expr


def ajustar_a_imagenes(fronteras: list[float], imagenes: list[dict]) -> list[float]:
    """Un cambio de plano a pocos fotogramas de donde empieza o acaba una imagen se mueve justo a ese borde: si no,
    queda un fotograma suelto con la imagen ya quitada y el plano todavía sin cambiar (o al revés)."""
    bordes = [t for im in imagenes for t in (im["a"], im["b"])]
    out = []
    for f in fronteras:
        cerca = [t for t in bordes if abs(t - f) <= CONFIG["ajuste_imagen"]]
        out.append(min(cerca, key=lambda t: abs(t - f)) if cerca else f)
    return sorted(set(out))


def escribir_ass(subs: list[dict], dst: Path, titulos=()):
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
    pos = f"\\an5\\pos({W // 2},{SUB['y']})"
    d = SUB["difusa"]   # halo negro difuminado y semitransparente, sin desplazamiento, detrás del texto
    halo = f"{pos}\\1a&HFF&\\3c&H000000&\\3a{d['alfa']}\\bord{d['borde']}\\blur{d['blur']}\\shad0"
    # Entrada de cada subtítulo: zoom-in de 0 a 100 % en entrada_ms con curva ease (ease-in-out: acelera la primera
    # mitad y frena la segunda; \t solo admite una curva potencial, así que van dos); la salida es de golpe. El texto
    # entra desenfocado (entrada_blur) y se enfoca a la vez que el zoom, como un desenfoque de movimiento.
    e = SUB["entrada_ms"]
    m = e // 2
    zoom = f"\\fscx0\\fscy0\\t(0,{m},2,\\fscx50\\fscy50)\\t({m},{e},0.5,\\fscx100\\fscy100)"
    filas = []
    for s in subs:
        filas.append(f"Dialogue: 0,{ts(s['s'])},{ts(s['e'])},S,,0,0,0,,{{{halo}{zoom}}}{s['texto']}")
        filas.append(f"Dialogue: 1,{ts(s['s'])},{ts(s['e'])},S,,0,0,0,,"
                     f"{{{pos}\\blur{SUB['entrada_blur']}{zoom}\\t(0,{e},\\blur0)}}{s['texto']}")
    # Títulos: mismo estilo que los subtítulos pero más grandes, en el centro y blancos (o el "color" "#RRGGBB" que
    # se pida). Cada línea va en su propio Dialogue para controlar el interlineado (libass no lo permite). Entran con
    # zoom-in rápido con ease-in (de menos a más rápido, 0 -> 100 % en entrada_ms; un evento por fotograma, porque
    # \move es lineal) y luego crecen despacio hasta zoom_final, sin transición de salida; las líneas se separan con
    # el mismo zoom para no pisarse.
    T = CONFIG["titulo"]
    for t in titulos:
        c = t.get("color", T["color"]).lstrip("#")
        color = f"\\1c&H{c[4:6]}{c[2:4]}{c[0:2]}&"
        n = max(1, round(T["entrada_ms"] / 1000 * FPS))
        medio = 0.5 / FPS   # cada evento cubre su fotograma de centro a centro (los tiempos ASS van en centésimas)
        zf = round(T["zoom_final"] * 100)
        partes = t["texto"].split("\\N")
        for i, linea in enumerate(partes):
            off = (i - (len(partes) - 1) / 2) * T["tam"] * T["interlineado"]
            # (inicio, fin, y inicial, y final, escala inicial, escala final): fotogramas de entrada y zoom lento
            tramos = []
            for k in range(n):
                z = ((k + 1) / (n + 1)) ** T["aceleracion"]
                tramos.append((t["a"] + max(0, k - 0.5) / FPS, t["a"] + k / FPS + medio, off * z, off * z,
                               z * 100, z * 100))
            tramos.append((t["a"] + n / FPS - medio, t["b"], off, off * T["zoom_final"], 100, zf))
            for a, b, y0, y1, z0, z1 in tramos:
                ms = round((b - a) * 1000)
                tag = (f"\\an5\\move({W // 2},{T['y'] + y0:.0f},{W // 2},{T['y'] + y1:.0f},0,{ms})\\fs{T['tam']}"
                       f"\\fscx{z0:.1f}\\fscy{z0:.1f}\\t(0,{ms},\\fscx{z1:.1f}\\fscy{z1:.1f})")
                filas.append(f"Dialogue: 2,{ts(a)},{ts(b)},S,,0,0,0,,{{{halo.replace(pos, tag)}}}{linea}")
                filas.append(f"Dialogue: 3,{ts(a)},{ts(b)},S,,0,0,0,,"
                             f"{{{tag}{color}\\shad{T['sombra']}\\blur0}}{linea}")
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
        if im.get("hasta") is not None:
            b = tiempo(im["hasta"]) - 0.1
        elif im.get("dur"):
            b = a + im["dur"]
        else:
            b = next((e for e in fins if e - a >= CONFIG["imagen_min_dur"]), dur)
        imagenes.append({"archivo": im["archivo"], "a": a, "b": min(b + 0.1, dur),
                         "modo": im.get("modo", CONFIG.get("imagen_modo", "abajo"))})
    imagenes.sort(key=lambda i: i["a"])
    for x, y in zip(imagenes, imagenes[1:]):
        x["b"] = min(x["b"], y["a"])

    fronteras = ajustar_a_imagenes(fronteras_frase(palabras, cortes_camara(video), niveles_voz(video)), imagenes)
    zooms = dec["zooms"] if "zooms" in dec else tramos_zoom(fronteras, dur)   # [] = sin mini-zoom
    pant = dec.get("pantalla") or [{"desde": 0, **CONFIG["pantalla_por_defecto"]}]
    pant = alinear_pantalla(pant, fronteras)
    esc = pantalla_expr(pant, lambda p: W / min(p["ancho"], 1040))
    cx = pantalla_expr(pant, lambda p: seguir_expr(p["seguir"], 1) if p.get("seguir") else p["centro"][0])
    cy = pantalla_expr(pant, lambda p: seguir_expr(p["seguir"], 2) if p.get("seguir") else p["centro"][1])
    fcam = factor_camara(zooms)
    zz = en_zoom(zooms)
    # "centro_zoom": centro durante el mini-zoom (la capa de abajo baja (CAM_HZ - CAM_H) / 2 y la cámara tapa otro
    # tanto de arriba); puede subir por encima del bruto: ese relleno negro queda escondido bajo la cámara
    cxz = pantalla_expr(pant, lambda p: p.get("centro_zoom", [None])[0] or 0)
    cyz = pantalla_expr(pant, lambda p: p.get("centro_zoom", [0, 0])[1])
    hay_cz = pantalla_expr(pant, lambda p: 1 if p.get("centro_zoom") else 0)
    cz = f"(({zz})*{hay_cz})"
    cx = f"if({cz},{cxz},{cx})"
    cy = f"if({cz},{cyz},{cy})"
    tapa = (CAM_HZ - CAM_H) // 2

    # Medio fotograma antes: los cortes del bruto caen justo en un fotograma (2.6667) y redondeado a 3 decimales
    # (2.667) se perdía el primero, que salía partido (cámara ya con el meme, abajo todavía sin él)
    medio = 0.5 / FPS
    completa = [{**c, "a": tiempo(c["desde"]) - medio, "b": tiempo(c["hasta"]) - medio}
                for c in dec.get("completa", [])]
    ass = trabajo / "subs.ass"
    titulos = [{**t, "a": tiempo(t["desde"]), "b": tiempo(t["hasta"])} for t in dec.get("titulos", [])]
    escribir_ass(subs, ass, titulos)

    cara = dec.get("cara_encima")
    entradas = ["-i", rel(video)]
    fc = [f"color=c=black:s={W}x{H}:r={FPS}:d={dur:.3f}[lienzo]",
          f"[0:v]fps={FPS},split={2 + len(completa) + bool(cara)}[vc][{'vs0' if cara else 'vs'}]"
          f"{''.join(f'[vf{k}]' for k in range(len(completa)))}{'[vcara]' if cara else ''}",
          # Cámara: recorte del bruto con relleno transparente debajo, escala por fotograma, centrada arriba
          f"[vc]crop={CAM['w']}:{CAM['h']}:{CAM['x']}:{CAM['y']},format=yuva420p,"
          f"pad={CAM['w']}:{PAD}:0:0:color=black@0,"
          f"scale=w='trunc({CAM['w']}*{fcam}/2)*2':h='trunc({PAD}*{fcam}/2)*2':eval=frame,"
          # Centrado con el tamaño real de cada fotograma: iw/ih de crop se fijan con el primero (plano normal) y
          # el mini-zoom salía recortado desde la izquierda
          f"crop={W}:{CAM_HZ}:x='(trunc({CAM['w']}*{fcam}/2)*2-{W})/2':"
          f"y='max(0,(trunc({PAD}*{fcam}/2)*2*{CAM['h']}/{PAD}-{CAM_HZ})/2)'[cam]",
          # Pantalla: recorte por tramo escalado a la capa de abajo
          f"[vs]scale=w='trunc(1920*{esc}/2)*2':h='trunc(1080*{esc}/2)*2':eval=frame,"
          f"pad=w=iw:h=ih+{tapa}:x=0:y={tapa}:color=black:eval=frame,"
          # Límites con el tamaño escalado de cada tramo: iw/ih de crop se quedan con los del primer fotograma
          f"crop={W}:{BOT}:x='max(0,min(trunc(1920*{esc}/2)*2-{W},{cx}*{esc}-{W // 2}))':"
          f"y='max({tapa}*(1-{cz}),min(trunc(1080*{esc}/2)*2+{tapa}-{BOT},{cy}*{esc}-{BOT // 2}+{tapa}))'[p0]"]
    if cara:
        # La cámara del usuario encima de la del otro reactor, en el bruto antes de recortar la pantalla
        x, y, w, h = cara
        fc.append(f"[vcara]crop={CAM['w']}:{CAM['h']}:{CAM['x']}:{CAM['y']},"
                  f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1[cara]")
        fc.append(f"[vs0][cara]overlay={x}:{y}[vs]")
    reel = dec.get("reel")
    if reel:
        # Solo el reel a pantalla completa (con cara_encima ya puesta), sin la cámara de arriba; el mini-zoom
        # acerca hacia su "centro_zoom" (por defecto el centro de cara_encima), que se queda quieto en pantalla
        rx, ry, rw, rh = reel
        x, y, w, h = cara or reel
        zx, zy = dec.get("centro_zoom") or [x + w / 2, y + h / 2]
        fx, fy = (zx - rx) / rw, (zy - ry) / rh
        fr = factor_camara(zooms, max(W / rw, H / rh) + 1e-4)   # sin el pelo, trunc deja 1918 de alto
        sw, sh = f"trunc({rw}*{fr}/2)*2", f"trunc({rh}*{fr}/2)*2"
        if imagenes or completa:
            sys.exit("reel: sin imágenes ni tramos a pantalla completa")
        fc_reel = [f"[0:v]fps={FPS},split=2[vs0][vcara]", *fc[-2:],
              f"[vs]crop={rw}:{rh}:{rx}:{ry},scale=w='{sw}':h='{sh}':eval=frame,"
              f"crop={W}:{H}:x='({sw}-{W})*{fx:.4f}':y='({sh}-{H})*{fy:.4f}',setsar=1,"
              f"subtitles={rel(ass)}:fontsdir=fuentes,format=yuv420p[vout]"]
    ult = "p0"
    encima = []   # capas a pantalla completa por encima de la cámara: (etiqueta, a, b)
    for k, im in enumerate(imagenes, start=1):
        entradas += ["-loop", "1", "-framerate", str(FPS), "-t", f"{im['b'] - im['a'] + 1 / FPS:.3f}", "-i", im["archivo"]]
        ancho, alto = (W, H) if im["modo"] == "estirar" else (W, BOT)
        ajuste = f"scale={W}:{H}" if im["modo"] == "estirar" else             f"scale={W}:{BOT}:force_original_aspect_ratio=increase,crop={W}:{BOT}"
        # Aparece y desaparece de golpe; mientras está, zoom lento constante (como los títulos) desde el centro.
        # Con perspective (remuestreo subpíxel): con scale+crop el tamaño y el recorte van a píxeles enteros
        # y la imagen vibra. m = margen recortado a cada lado, en fracción del tamaño.
        m = f"((1-1/(1+{CONFIG['zoom_imagen_por_segundo']}*in/{FPS}))/2)"
        ajuste += (f",format=gbrp,perspective=x0='W*{m}':y0='H*{m}':x1='W*(1-{m})':y1='H*{m}':"
                   f"x2='W*{m}':y2='H*(1-{m})':x3='W*(1-{m})':y3='H*(1-{m})':interpolation=cubic:eval=frame")
        fc.append(f"[{k}:v]{ajuste},setsar=1,format=yuv420p,setpts=PTS-STARTPTS+{im['a']:.3f}/TB[i{k}]")
        if im["modo"] == "estirar":
            encima.append((f"i{k}", im["a"], im["b"]))
            continue
        fc.append(f"[{ult}][i{k}]overlay=eof_action=pass:enable='gte(t,{im['a']:.3f})*lt(t,{im['b']:.3f})'[p{k}]")
        ult = f"p{k}"
    for k, c in enumerate(completa):
        if c.get("modo", "estirar") == "estirar":
            ajuste = f"scale={W}:{H}"
        else:
            cw = round(1080 * W / H / 2) * 2
            x = max(0, min(1920 - cw, c["centro"][0] - cw // 2))
            ajuste = f"crop={cw}:1080:{x}:0,scale={W}:{H}"
        # Un fotograma de más: overlay descarta el último fotograma de la capa al llegar a su fin (el "enable" corta)
        fc.append(f"[vf{k}]trim={c['a']:.3f}:{c['b'] + 1 / FPS:.3f},{ajuste},setsar=1,format=yuv420p[c{k}]")
        encima.append((f"c{k}", c["a"], c["b"]))
    # La capa de abajo baja con la cámara en mini-zoom y se centra en el hueco que queda
    fc.append(f"[lienzo][{ult}]overlay=x=0:y='{CAM_H}+({CAM_HZ}-{CAM_H})/2*({zz})':eval=frame[l1]")
    fc.append("[l1][cam]overlay=0:0[e0]")
    for j, (et, a, b) in enumerate(encima, start=1):
        fc.append(f"[e{j - 1}][{et}]overlay=0:0:eof_action=pass:enable='gte(t,{a:.3f})*lt(t,{b:.3f})'[e{j}]")
    fc.append(f"[e{len(encima)}]subtitles={rel(ass)}:fontsdir=fuentes,format=yuv420p[vout]")

    if reel:
        fc = fc_reel
    amix = ["[0:a]"]
    base = 1 + len(imagenes)
    # Cam shot al entrar cada imagen y swoosh al zoom-in de cada título
    sonidos = [(im["a"], "recursos/cam shot.wav") for im in imagenes] + \
              [(t["a"], "recursos/swoosh.wav") for t in titulos]
    for j, (a, wav) in enumerate(sonidos):
        entradas += ["-i", wav]
        fc.append(f"[{base + j}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={round(a * 1000)}:all=1[s{j}]")
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
    print(f"{len(zooms)} mini-zooms, {len(pant)} tramos de pantalla, {len(imagenes)} imágenes, "
          f"{len(completa)} tramos a pantalla completa -> {salida}")


if __name__ == "__main__":
    main()
