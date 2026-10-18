---
name: editar-short
description: Edita un fragmento de vídeo largo de brutos/ como YouTube Short 1080x1920@30 con el estilo del canal (cámara arriba con mini-zoom periódico, pantalla abajo centrada en lo importante, imágenes que pida el usuario con cam shot, subtítulos amarillos) y lo renderiza en salida/short-N.mp4. Úsala cuando pida editar un short o cambiar algo de uno.
---

# Editar short

Todo desde la raíz con `mise exec -- python ...`. El fragmento ya viene recortado: **no se corta nada**.
Composición, mini-zoom y estilo de subtítulos son automáticos; tú decides solo los recortes de pantalla, dónde van
las imágenes que pida el usuario y la corrección de los subtítulos.

## Flujo

1. **Bruto**: el más reciente de `brutos/` (o el que diga). Las imágenes que pase van en `imagenes/`.
2. **Transcribe**: `mise exec -- python motor/transcribir.py "brutos/<video>.mp4"` (~30 s por short).
3. **Subtítulos**: `mise exec -- python motor/subtitulos.py trabajo/<slug>` → `subs.json` (trozos de ≤4 palabras).
   Léelo y corrige solo el `texto` (MAYÚSCULAS): nombres propios (DE JONG, XAVI, MBAPPÉ, GÜLER…), palabras mal oídas
   (usa el contexto del `transcript.md`) y nombres partidos entre dos trozos (pasa la palabra al trozo vecino).
   No toques los tiempos.
4. **Recortes de pantalla** (lo que va abajo, en píxeles del bruto 1920x1080):
   - Cambios de pantalla: `ffmpeg -hide_banner -i <bruto> -vf "crop=1300:1080:0:0,scale=480:-1,scdet=threshold=6" -an -f null - 2>&1 | grep -o "lavfi.scd.time: [0-9.]*"`
   - Por cada tramo, mira UN fotograma con cuadrícula: `mise exec -- python motor/ver.py <bruto> --t 12.5`
     (líneas cada 160 px con su coordenada real). Lee las coordenadas de la cuadrícula: no las estimes a ojo.
   - Elige `centro` = centro de lo importante (lo que señala o de lo que habla) y `ancho` (≤ 1040) para que quepa;
     el alto es ≈ 1,03 × ancho. Evita la cámara del bruto (x ≥ 1339, y ≥ 641), que ya sale arriba.
   - Si no hay nada claro, `{"centro": [640, 520], "ancho": 1000}`.
5. **Imágenes** (solo las que pida el usuario, donde diga): `{"t": "L5:3", "archivo": "imagenes/x.jpg"}` anclada a
   la palabra que indique. Duran automáticamente hasta el fin de frase que deje ≥ 2 s; suenan con cam shot.
   Tiempos del usuario tipo `0:41:18` = M:SS:fotogramas a 60 fps (41,30 s); "entre X e Y" → `"t"` + `"hasta"`.
   **Las imágenes que pasa el usuario son imágenes normales, no memes: van siempre abajo, debajo de su cara, como si
   las comentara** (modo `"abajo"`, el de por defecto). Solo se estira una imagen si el usuario dice que es un meme.
5b. **Memes estirados (regla del canal)**: los memes que ya vienen en el bruto a pantalla completa (detectados con los
   cambios de escena) van **estirados a toda la pantalla 1080x1920 aunque se deformen**, en plan shitpost, tapando
   cámara y pantalla (subtítulos encima): `"completa": [{"desde", "hasta", "modo": "estirar"}]`. Lo que el usuario
   diga que NO es meme (foto/clip real) no se estira: `"modo": "proporcion", "centro": [x, y]` (recorte 9:16 centrado
   en lo que pida). Una imagen del usuario que sí sea meme → `"modo": "estirar"`.
5c. **Zooms y subtítulos** son automáticos: el mini-zoom solo entra o sale al empezar una frase (tras coma/punto o
   palabra que abre frase), juntando frases hasta durar ≥ `frase_min` (2,5 s); nunca a mitad de frase. Los subtítulos
   llevan, además de la sombra dura negra, un halo negro difuminado semitransparente sin desplazamiento
   (`subtitulos.difusa` en `config.json`) para leerse sobre fondos amarillos o claros.
6. **Escribe `trabajo/<slug>/decisiones.json`** (esquema en el docstring de `motor/render.py`).
7. **Renderiza**: `mise exec -- python motor/render.py trabajo/<slug>` → `salida/short-N.mp4` (~15 s).
8. **Verifica**: `mise exec -- python motor/ver.py salida/short-N.mp4 --cada 3 --ancho 216` y mira la hoja una vez:
   lo importante centrado abajo, imágenes en su sitio, subtítulos legibles. Corrige y vuelve a renderizar si hace falta.

## Cambios que pida después
Edita `decisiones.json` / `subs.json` y vuelve a renderizar (sale como `short-N` nuevo; borra el anterior si el
usuario lo prefiere). "Abajo enfoca X" → cambia el tramo de `pantalla`. "Más/menos zooms" → `motor/config.json`
(`zoom`) o fuerza tramos con `"zooms": [[a, b], ...]`.
