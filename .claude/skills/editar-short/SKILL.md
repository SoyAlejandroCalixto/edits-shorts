---
name: editar-short
description: Edita un fragmento de vídeo largo de brutos/ como YouTube Short 1080x1920@30 con el estilo del canal (cámara arriba con mini-zoom periódico, pantalla abajo centrada en lo importante, imágenes que pida el usuario con cam shot, subtítulos amarillos) y lo renderiza en salida/short-N.mp4. Úsala cuando pida editar un short o cambiar algo de uno.
---

# Editar short

Todo desde la raíz con `python ...`. El fragmento ya viene recortado: **no se corta nada**.
Composición, mini-zoom y estilo de subtítulos son automáticos; tú decides solo los recortes de pantalla, dónde van
las imágenes que pida el usuario y la corrección de los subtítulos.

## Flujo

1. **Bruto**: el más reciente de `brutos/` (o el que diga). Las imágenes que pase van en `imagenes/`.
1b. **Encuadre de la cámara (regla del canal)**: el usuario a veces mueve su cámara en OBS. Comprueba en cada bruto que
   `camara` de `config.json` sigue cuadrando: mide los bordes de la caja de la cámara (salto fuerte de gradiente en
   columnas y filas) y recórtala a **todo su ancho, sin comerse nada de los lados ni dejar ni un píxel de fuera**
   (1 px de margen dentro de cada borde), quitando solo pared por arriba para mantener la proporción w/h ≈ 1,61
   (elige w y h con 1080 × h / w a ≤ 0,02 de un número par: si no, queda una raya negra de 1-2 px bajo la cámara):
   cuanto más ancha, menos alta queda arriba y más sitio tiene la pantalla de abajo. Mira el recorte con
   `ffmpeg -ss 10 -i <bruto> -vf "crop=w:h:x:y" -frames:v 1 trabajo/cam.png` antes de renderizar.
2. **Transcribe**: `python motor/transcribir.py "brutos/<video>.mp4"` (~30 s por short).
3. **Subtítulos**: `python motor/subtitulos.py trabajo/<slug>` → `subs.json` (trozos de ≤4 palabras).
   Léelo y corrige solo el `texto` (MAYÚSCULAS): nombres propios (DE JONG, XAVI, MBAPPÉ, GÜLER…), palabras mal oídas
   (usa el contexto del `transcript.md`) y nombres partidos entre dos trozos (pasa la palabra al trozo vecino).
   No toques los tiempos.
4. **Recortes de pantalla** (lo que va abajo, en píxeles del bruto 1920x1080):
   - Cambios de pantalla: `ffmpeg -hide_banner -i <bruto> -vf "crop=1300:1080:0:0,scale=480:-1,scdet=threshold=6" -an -f null - 2>&1 | grep -o "lavfi.scd.time: [0-9.]*"`
   - Por cada tramo, mira UN fotograma con cuadrícula: `python motor/ver.py <bruto> --t 12.5`
     (líneas cada 160 px con su coordenada real). Lee las coordenadas de la cuadrícula: no las estimes a ojo.
   - Elige `centro` = centro de lo importante (lo que señala o de lo que habla) y `ancho` (≤ 930 con la cámara actual; el render lo limita a `ANCHO_MAX`) para que quepa;
     el alto es ≈ 1,16 × ancho. Evita la cámara del bruto (la caja de `camara` en `config.json`), que ya sale arriba.
   - **Enfocar lo que menciona (regla del canal, la pedirá a menudo)**: cuando habla de algo concreto de la pantalla
     (la posesión, el marcador, un jugador, "por aquí"…), abajo va justo eso, que suele estar donde tiene el ratón en
     ese momento: busca el cursor con `ver.py --t` en las palabras que lo nombran. **El enfoque dura todo el plano**
     (de cambio de plano a cambio de plano: bordes de mini-zoom y de imagen, que `render.py` imprime al final como
     `planos:`), nunca un cambio de recorte a mitad de plano; el render lleva cada `desde` al borde de plano más
     cercano. Si en un plano nombra dos cosas, enfoca la principal o encuadra las dos. Renderiza una vez, mira los
     `planos:` y asigna un tramo por plano. **Si la página hace scroll dentro del plano**, mide el desplazamiento con
     `python motor/scroll.py <bruto> <desde> <hasta>` y ponlo en `"seguir"` (y = y antes del scroll + desplazamiento,
     un punto por fotograma del scroll) para que lo enfocado no se mueva; con medidas a ojo el recorte vibra.
     Verifica que no queda ningún fotograma suelto en los cambios (cada cambio de plano y de recorte en el mismo
     fotograma).
   - Si no hay nada claro, `{"centro": [640, 520], "ancho": 1000}`.
   - **Reel al que reacciona (regla del canal)**: abajo va solo el vídeo del reel, sin bandas negras a los lados
     (como `object-fit: cover`). Mide la caja del vídeo dentro del reel (sin las franjas negras de Instagram, p. ej.
     `cropdetect`) y elige `ancho` = el menor entre (alto de esa caja − 6) / 1,16 y (ancho de la caja − 6) (la capa
     de abajo es 1080x1250 con la cámara actual: alto = 1,16 × ancho; si cambia la proporción de `camara` en
     `config.json`, cambia esta), con `centro` en el centro de la caja: llena todo sin bandas negras arriba, abajo ni
     a los lados. Ejemplo: caja 514x574 en (445, 276) → `{"centro": [702, 562], "ancho": 490}`.
     **Si el reel lleva fondo blureado a los lados** (una captura o collage dentro del reel con su propio fondo
     difuminado), la caja es solo el contenido nítido: nunca se ve la banda blureada.
     **Encuadra lo que dice**: si el reel es una lista (años, jugadores…), cambia el `centro` en vertical al tramo
     del que habla en cada frase (p. ej. baja al de 2026-2027 cuando lo nombra).
5. **Imágenes** (solo las que pida el usuario, donde diga): `{"t": "L5:3", "archivo": "imagenes/x.jpg"}` anclada a
   la palabra que indique. Duran automáticamente hasta el fin de frase que deje ≥ 2 s; suenan con cam shot.
   **Zoom en imágenes (regla del canal)**: toda imagen o meme que pida el usuario (abajo o estirado) aparece y
   desaparece de golpe, sin animación, y mientras está hace un zoom lento constante y suave (subpíxel, sin vibrar) desde el centro
   de la imagen, nunca desde una esquina (`zoom_imagen_por_segundo` 0,04, como el de los títulos). Es automático en el render.
   Tiempos del usuario tipo `0:41:18` = M:SS:fotogramas a 60 fps (41,30 s); "entre X e Y" → `"t"` + `"hasta"`.
   Con dos números (`01:34-04:02`) son SS:fotogramas a 60 fps (1,567–4,033 s) y suelen caer justo en cortes del bruto:
   pon los segundos 0,002 antes del fotograma (`1.565`, `4.031`) para no perder el primero al redondear.
   **Imagen y cambio de plano juntos (regla del canal)**: si un cambio de plano (zoom o recorte de abajo) queda a
   ≤ `ajuste_imagen` (0,3 s) del inicio o fin de una imagen, el render lo mueve justo a ese borde; nunca debe quedar
   un fotograma con la imagen ya quitada y el plano sin cambiar (o al revés). Verifica los fotogramas de cada borde.
   **Mismo plano durante toda la imagen (regla del canal)**: nunca hay cambio de plano (zoom o recorte) a mitad de
   una imagen; el render quita esas fronteras y lleva los bordes de zoom (también los de `"zooms"` forzados) al
   inicio o fin de la imagen. Si el usuario quiere la imagen sin zoom: `"plano": "normal"` en esa imagen.
   **Las imágenes que pasa el usuario son imágenes normales, no memes: van siempre abajo, debajo de su cara, como si
   las comentara** (modo `"abajo"`, el de por defecto). Solo se estira una imagen si el usuario dice que es un meme.
5a. **Barra animada** (si pide una barra que se rellena, p. ej. posesión 33 → 66): una imagen más con `"barra"` en
   vez de `"archivo"`: `{"t": "L3:8", "hasta": 18.931, "barra": {"de": 33, "a": 66, "anim": [16.0, 17.6]}}` (`anim` =
   inicio y fin del llenado en s del bruto, al ritmo de lo que dice). Va abajo con fondo #232323, barra blanca, relleno
   de rojo a verde según avanza y número dorado con la sombra de los subtítulos (`motor/barra.py`).
5b. **Memes estirados (regla del canal)**: los memes que ya vienen en el bruto a pantalla completa (detectados con los
   cambios de escena) van **estirados a toda la pantalla 1080x1920 aunque se deformen**, en plan shitpost, tapando
   cámara y pantalla (subtítulos encima): `"completa": [{"desde", "hasta", "modo": "estirar"}]`. Lo que el usuario
   diga que NO es meme (foto/clip real) no se estira: `"modo": "proporcion", "centro": [x, y]` (recorte 9:16 centrado
   en lo que pida). Una imagen del usuario que sí sea meme → `"modo": "estirar"`.
5c. **Zooms y subtítulos** son automáticos: el mini-zoom solo entra o sale al empezar una frase (tras coma/punto o
   palabra que abre frase; un "¿eh?" o un "¿no?" siempre cierra la frase anterior, nunca abre una: el cambio va luego, en la frase siguiente), juntando frases hasta durar ≥ `frase_min` (2,5 s); nunca a mitad de frase. **Primer plano
   normal (regla del canal)**: el short nunca empieza con zoom; el primer tramo es siempre el plano normal (también
   si fuerzas `"zooms"`: ninguno empieza en 0). **Sincronía con
   los cortes del bruto (regla del canal)**: el cambio de plano va justo cuando empieza a hablar; si el bruto tiene un
   corte (jump cut) ahí, el zoom cambia en el fotograma exacto del corte. El render detecta los cortes en la cámara
   (`cortes_camara`, `config.json` → `cortes`) y usa el corte en vez del inicio de palabra de Whisper (que llega hasta
   ~0,25 s tarde); un corte muy claro en una pausa abre frase aunque no haya puntuación. **Además, todo cambio de zoom a ≤ 0,3 s
   de un corte del bruto se pega al corte** (`alinear_a_cortes`, `cortes.alinear`; también cuenta como corte un salto
   que dobla la diferencia de los 2 fotogramas de cada lado, aunque esté gesticulando): no hace falta `zoom_retraso`
   para cuadrar con un corte, solo para lo que no es corte (p. ej. el arranque de la voz). Al verificar, saca los
   fotogramas de cada cambio de zoom (`select=eq(n\,N)`) y comprueba que el corte y el zoom coinciden. **Los cambios de
   recorte de abajo (`pantalla`) siguen la misma regla**: el render mueve cada `desde` al inicio de frase más cercano
   (≤ 3 s; `"exacto": true` para no moverlo) y luego al borde de plano (mini-zoom o imagen) más cercano, en el mismo
   fotograma que el zoom (esto último siempre, también con `"exacto"`). Pon pocos tramos: cambia de plano solo cuando cambie de verdad lo que
   se ve, no por cada detalle. Los tramos `completa` se ajustan solos al fotograma exacto del corte del bruto (sin
   fotogramas partidos al empezar o acabar un meme): usa los tiempos de `scdet` tal cual. Los subtítulos
   llevan, además de la sombra dura negra, un halo negro difuminado semitransparente sin desplazamiento
   (`subtitulos.difusa` en `config.json`) para leerse sobre fondos amarillos o claros. **Entrada de los subtítulos
   (regla del canal)**: cada trozo aparece con un zoom-in de 0,1 s con curva ease y desenfoque de movimiento (`subtitulos.entrada_ms`, `entrada_blur`) y
   desaparece de golpe, sin animación.
5d. **Títulos** (solo si el usuario los pide): texto grande en el centro de la pantalla, misma fuente, sombra y halo
   que los subtítulos (`config.json` → `titulo`): `"titulos": [{"desde": 0, "hasta": 1.565, "texto": "¿VENDER A\\NMBAPPÉ?"}]`
   en MAYÚSCULAS; `\\N` en el JSON = salto de línea (la línea que pida abajo). **Estilo fijo del canal**: blanco por
   defecto (`"color": "#RRGGBB"` si pide otro), tamaño 130 siempre, líneas juntas (`interlineado` 0,74: la parte alta de la línea de abajo queda a ~mitad del hueco entre ambas), entra con
   zoom-in rápido de 0,2 s con ease-in (de menos a más rápido, `aceleracion` 2) y sonido `recursos/swoosh.wav`, y
   luego zoom lento constante (hasta ×1,08) hasta desaparecer de golpe, sin transición.
6. **Escribe `trabajo/<slug>/decisiones.json`** (esquema en el docstring de `motor/render.py`).
7. **Renderiza**: `python motor/render.py trabajo/<slug>` → `salida/short-N.mp4` (~15 s).
8. **Verifica**: `python motor/ver.py salida/short-N.mp4 --cada 3 --ancho 216` y mira la hoja una vez:
   lo importante centrado abajo, imágenes en su sitio, subtítulos legibles. Corrige y vuelve a renderizar si hace falta.

## Cambios que pida después
Edita `decisiones.json` / `subs.json` y vuelve a renderizar (sale como `short-N` nuevo; borra el anterior si el
usuario lo prefiere). "Abajo enfoca X" → cambia el tramo de `pantalla`. "Más/menos zooms" → `motor/config.json`
(`zoom`) o fuerza tramos con `"zooms": [[a, b], ...]`. "Que los cambios de plano empiecen cuando vuelvo a hablar" → `"zooms_desde": "L3"` (antes, plano normal fijo).
