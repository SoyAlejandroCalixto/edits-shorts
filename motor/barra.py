"""Animación de una barra rellenándose (p. ej. posesión 33 % -> 66 %) como clip para la capa de abajo.

Uso desde decisiones.json, como una imagen más (va abajo, debajo de la cara):
  {"t": "L3:8", "hasta": 18.931, "barra": {"de": 33, "a": 66, "anim": [15.9, 17.7]}}
  "anim" = [inicio, fin] del llenado en s del bruto (antes queda quieta en "de", después en "a"); por defecto
  empieza 0,4 s tras aparecer y dura el 60 % del tiempo en pantalla. Opcional: "sufijo" ("%" por defecto),
  "fondo" ("#232323" o una imagen, p. ej. "imagenes/estadio.webp": la rellena, difuminada "desenfoque" px y
  oscurecida a "oscurecer"), "color_numero" ("#FFC83D").

Fondo (color o imagen difuminada), barra blanca con el relleno de rojo (al empezar) a verde (al acabar) según avanza, y el número
encima en dorado con la misma sombra dura y halo negro que los subtítulos. render.py llama a generar().

Prueba suelta: python motor/barra.py trabajo/barra.mp4 --dur 3.7
"""
import argparse
import colorsys
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).parent))
from comun import RAIZ  # noqa: E402

FUENTE = RAIZ / "fuentes" / "SofiaSans-BlackItalic.ttf"


def _rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _suave(x: float) -> float:
    """Ease-in-out (smootherstep): arranca y frena suave."""
    x = min(1.0, max(0.0, x))
    return x * x * x * (x * (6 * x - 15) + 10)


def _rect_redondo(w: int, h: int, r: float, ss: int = 4) -> np.ndarray:
    """Máscara 0..1 de un rectángulo con esquinas redondas, con antialias (supermuestreo ss x ss)."""
    im = Image.new("L", (w * ss, h * ss), 0)
    ImageDraw.Draw(im).rounded_rectangle([0, 0, w * ss - 1, h * ss - 1], radius=r * ss, fill=255)
    return np.asarray(im.resize((w, h), Image.LANCZOS), np.float32) / 255


def generar(dst: Path, dur: float, w: int, h: int, fps: int, de: float = 33, a: float = 66,
            anim: tuple[float, float] | None = None, sufijo: str = "%", fondo: str = "#232323",
            color_numero: str = "#FFC83D", desenfoque: float = 7, oscurecer: float = 0.8):
    """Escribe en dst un clip w x h de dur s. anim = (inicio, fin) del llenado en s desde el inicio del clip."""
    t0, t1 = anim if anim else (min(0.4, dur * 0.2), min(0.4, dur * 0.2) + dur * 0.6)
    bw, bh = round(w * 0.82), round(w * 0.105)            # barra
    bx, by = (w - bw) // 2, round(h * 0.47)
    borde = max(4, bh // 14)                               # margen blanco alrededor del relleno
    fondo_barra = _rect_redondo(bw, bh, bh / 2)
    base = np.empty((h, w, 3), np.float32)
    if fondo.startswith("#"):
        base[:] = np.array(_rgb(fondo), np.float32)
    else:
        # Imagen de fondo: rellena todo (como object-fit: cover), difuminada y algo oscurecida para que resalten
        # la barra y el número
        img = Image.open(RAIZ / fondo).convert("RGB")
        k = max(w / img.width, h / img.height)
        img = img.resize((round(img.width * k), round(img.height * k)), Image.LANCZOS)
        x0, y0 = (img.width - w) // 2, (img.height - h) // 2
        img = img.crop((x0, y0, x0 + w, y0 + h)).filter(ImageFilter.GaussianBlur(desenfoque))
        base[:] = np.asarray(img, np.float32) * oscurecer
    sombra = _rect_redondo(bw, bh, bh / 2)                 # sombra suave bajo la barra
    sombra = np.asarray(Image.fromarray((sombra * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(14)),
                        np.float32) / 255 * 0.55
    sy = by + bh // 6
    base[sy:sy + bh, bx:bx + bw] *= (1 - sombra)[..., None]
    base[by:by + bh, bx:bx + bw] = (base[by:by + bh, bx:bx + bw] * (1 - fondo_barra)[..., None]
                                    + 255 * fondo_barra[..., None])
    iw, ih = bw - 2 * borde, bh - 2 * borde
    fuente = ImageFont.truetype(str(FUENTE), round(w * 0.26))
    oro = _rgb(color_numero)
    ny = by - round(h * 0.03)                              # base del número, encima de la barra

    proc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
                             "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "fast", "-crf", "8",
                             "-pix_fmt", "yuv420p", str(dst)], stdin=subprocess.PIPE)
    for n in range(max(1, round(dur * fps))):
        t = n / fps
        p = _suave((t - t0) / max(t1 - t0, 1e-3))
        frac = (de + (a - de) * p) / 100
        valor = round(de + (a - de) * p)
        # Rojo -> verde por el tono (pasando por naranja y amarillo, sin el marrón de mezclar en RGB)
        color = np.array(colorsys.hsv_to_rgb(p * 120 / 360, 0.82, 0.93), np.float32) * 255
        f = base.copy()
        lw = iw * frac
        if lw >= 1:
            m = _rect_redondo(max(int(np.ceil(lw)), ih), ih, ih / 2)
            m = m[:, :iw]
            y0, x0 = by + borde, bx + borde
            reg = f[y0:y0 + ih, x0:x0 + m.shape[1]]
            reg[:] = reg * (1 - m[..., None]) + color * m[..., None]
        im = Image.fromarray(f.clip(0, 255).astype(np.uint8))
        texto = f"{valor}{sufijo}"
        # Halo negro difuminado + sombra dura, como los subtítulos
        capa = Image.new("L", (w, h), 0)
        d = ImageDraw.Draw(capa)
        d.text((w // 2, ny), texto, font=fuente, anchor="ms", fill=255, stroke_width=10, stroke_fill=255)
        halo = capa.filter(ImageFilter.GaussianBlur(12)).point(lambda v: v * 0.5)
        im.paste((0, 0, 0), (0, 0), halo)
        dura = Image.new("L", (w, h), 0)
        ImageDraw.Draw(dura).text((w // 2 + 14, ny + 14), texto, font=fuente, anchor="ms", fill=255)
        im.paste((0, 0, 0), (0, 0), dura)
        ImageDraw.Draw(im).text((w // 2, ny), texto, font=fuente, anchor="ms", fill=oro)
        proc.stdin.write(im.tobytes())
    proc.stdin.close()
    if proc.wait():
        raise RuntimeError("ffmpeg falló al escribir la barra")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("salida")
    ap.add_argument("--dur", type=float, default=3.7)
    ap.add_argument("--de", type=float, default=33)
    ap.add_argument("--a", type=float, default=66)
    args = ap.parse_args()
    generar(Path(args.salida), args.dur, 1080, 1250, 30, args.de, args.a)
    print(args.salida)
