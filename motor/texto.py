"""Texto con emojis a imagen RGBA, con el estilo de los títulos (Sofia Sans Black Italic, halo negro difuminado y
sombra dura), para cuando el texto lleva emojis: libass no pinta emojis en color.

Fuente de emojis: fuentes/AppleColorEmoji.ttf (solo para los emojis; el resto del texto, con la fuente del canal).
Es una fuente CBDT (mapas de bits PNG, solo el tamaño de 96 px): los emojis se sacan como PNG de la propia fuente
y se escalan al tamaño del texto. Las secuencias (banderas, ZWJ, tonos de piel) se resuelven con las ligaduras GSUB
de la fuente, sin necesitar raqm/harfbuzz.
"""
import io
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

RAIZ = Path(__file__).resolve().parent.parent
FUENTE = RAIZ / "fuentes" / "SofiaSans-BlackItalic.ttf"
EMOJI = RAIZ / "fuentes" / "AppleColorEmoji.ttf"


def es_emoji(c: str) -> bool:
    o = ord(c)
    return (o >= 0x1F000 or 0x2190 <= o <= 0x2BFF or o in (0x200D, 0xFE0F, 0x20E3, 0x00A9, 0x00AE, 0x203C, 0x2049)
            or 0x3030 <= o <= 0x303D or 0xE0020 <= o <= 0xE007F)


def tiene_emoji(texto: str) -> bool:
    return any(es_emoji(c) for c in texto)


@lru_cache(1)
def _emoji_font():
    """(cmap, ligaduras {tupla de glifos: glifo}, imágenes {glifo: datos PNG}) de la fuente de emojis."""
    from fontTools.ttLib import TTFont
    f = TTFont(EMOJI, lazy=True)
    cmap = f.getBestCmap()
    ligas = {}
    for lookup in f["GSUB"].table.LookupList.Lookup:
        for st in lookup.SubTable:
            if st.LookupType == 7:      # extensión
                st = st.ExtSubTable
            if getattr(st, "LookupType", None) != 4 and not hasattr(st, "ligatures"):
                continue
            for primero, lista in st.ligatures.items():
                for lig in lista:
                    ligas[(primero, *lig.Component)] = lig.LigGlyph
    return cmap, ligas, f["CBDT"].strikeData[0]


def _png_emoji(glifo: str) -> Image.Image | None:
    _, _, datos = _emoji_font()
    g = datos.get(glifo)
    if g is None:
        return None
    g.decompile()
    return Image.open(io.BytesIO(g.imageData)).convert("RGBA")


def _trozos(texto: str):
    """[("texto", s) | ("emoji", Image)]: cada racha de emojis se parte en glifos, con la ligadura más larga."""
    cmap, ligas, _ = _emoji_font()
    out, i = [], 0
    while i < len(texto):
        if not es_emoji(texto[i]):
            j = i
            while j < len(texto) and not es_emoji(texto[j]):
                j += 1
            out.append(("texto", texto[i:j]))
            i = j
            continue
        j = i
        while j < len(texto) and es_emoji(texto[j]):
            j += 1
        glifos = [cmap.get(ord(c)) for c in texto[i:j]]
        k = 0
        while k < len(glifos):
            if glifos[k] is None:          # selector de variante, ZWJ suelto…
                k += 1
                continue
            for n in range(len(glifos) - k, 0, -1):
                seq = tuple(g for g in glifos[k:k + n])
                if n == 1 or (None not in seq and seq in ligas):
                    g = seq[0] if n == 1 else ligas[seq]
                    im = _png_emoji(g)
                    if im is not None:
                        out.append(("emoji", im))
                    k += n
                    break
        i = j
    return out


def render(texto: str, tam: int, color: str = "#FFFFFF", interlineado: float = 0.74, sombra: int = 12,
           halo_borde: int = 6, halo_blur: int = 8, halo_alfa: float = 0.5, emoji_escala: float = 1.0) -> Image.Image:
    """Imagen RGBA recortada al contenido con margen, con el centro del bloque de líneas en su centro.
    tam = tamaño de fuente en el sentido de ASS (alto de línea, ascendente + descendente de Windows), para que
    coincida con los títulos de libass. Líneas separadas por "\\N" (o salto de línea)."""
    from fontTools.ttLib import TTFont
    t = TTFont(FUENTE, lazy=True)
    os2, upm = t["OS/2"], t["head"].unitsPerEm
    em = tam * upm / (os2.usWinAscent + os2.usWinDescent)
    fuente = ImageFont.truetype(str(FUENTE), round(em))
    cap = os2.sCapHeight / upm * em
    alto_emoji = round(cap * 1.45 * emoji_escala)
    hueco = round(em * 0.12)

    lineas = texto.replace("\\N", "\n").split("\n")
    paso = tam * interlineado
    margen = halo_borde + 3 * halo_blur + sombra + 4
    capas = []
    for linea in lineas:
        piezas = []
        for tipo, v in _trozos(linea):
            if tipo == "texto":
                piezas.append(("texto", v, fuente.getlength(v)))
            else:
                im = v.resize((round(v.width * alto_emoji / v.height), alto_emoji), Image.LANCZOS)
                # Entre dos emojis seguidos, un hueco pequeño
                pre = hueco if piezas and piezas[-1][0] == "emoji" else 0
                piezas.append(("emoji", im, im.width + pre))
        capas.append((piezas, sum(w for *_, w in piezas)))
    ancho_max = max(a for _, a in capas)
    W = round(ancho_max + 2 * margen + em * 0.3)
    H = round(paso * (len(lineas) - 1) + tam + 2 * margen)
    capa = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    letras = Image.new("L", (W, H), 0)      # solo el texto: la sombra dura no la llevan los emojis
    d = ImageDraw.Draw(capa)
    dl = ImageDraw.Draw(letras)
    for n, (piezas, ancho) in enumerate(capas):
        # Línea de base: el centro de las mayúsculas en el centro de su línea
        yc = H / 2 + (n - (len(lineas) - 1) / 2) * paso
        base = yc + cap / 2
        x = (W - ancho) / 2
        for tipo, v, w in piezas:
            if tipo == "texto":
                d.text((x, base), v, font=fuente, fill=color, anchor="ls")
                dl.text((x, base), v, font=fuente, fill=255, anchor="ls")
            else:
                capa.alpha_composite(v, (round(x + w - v.width), round(yc - v.height / 2)))
            x += w
    a = capa.getchannel("A")
    # Halo: borde negro difuminado y semitransparente, sin desplazamiento
    halo = a.filter(ImageFilter.MaxFilter(2 * halo_borde + 1)).filter(ImageFilter.GaussianBlur(halo_blur * 0.8))
    halo = halo.point(lambda v: round(v * halo_alfa))
    # Sombra dura negra desplazada abajo a la derecha (solo del texto)
    som = ImageChops.offset(letras, sombra, sombra)
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    negro = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    out.paste(negro, (0, 0), halo)
    out.alpha_composite(Image.composite(negro, Image.new("RGBA", (W, H), (0, 0, 0, 0)), som))
    out.alpha_composite(capa)
    return out


def secuencia(img: Image.Image, carpeta: Path, n: int, fps: int, entrada_ms: int, aceleracion: float,
              zoom_final: float) -> tuple[int, int]:
    """Fotogramas PNG (000.png…) con la animación de los títulos: zoom-in de 0 a 1 en entrada_ms con ease-in
    (aceleracion) y luego zoom lento constante hasta zoom_final en el último fotograma, desde el centro y subpíxel
    (transformación afín bicúbica, sin vibrar). Devuelve el tamaño de cada fotograma."""
    carpeta.mkdir(parents=True, exist_ok=True)
    for p in carpeta.glob("*.png"):
        p.unlink()
    W, H = (round(v * zoom_final / 2) * 2 + 4 for v in img.size)
    lienzo = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    lienzo.alpha_composite(img, ((W - img.width) // 2, (H - img.height) // 2))
    k_in = max(1, round(entrada_ms / 1000 * fps))
    for k in range(n):
        if k < k_in:
            z = ((k + 1) / (k_in + 1)) ** aceleracion
        else:
            z = 1 + (zoom_final - 1) * (k - k_in) / max(1, n - 1 - k_in)
        cx, cy = W / 2, H / 2
        # Afín de salida a entrada: x_in = (x_out - cx) / z + cx
        f = lienzo.transform((W, H), Image.AFFINE, (1 / z, 0, cx - cx / z, 0, 1 / z, cy - cy / z),
                             resample=Image.BICUBIC)
        f.save(carpeta / f"{k:03d}.png", compress_level=1)
    return W, H
