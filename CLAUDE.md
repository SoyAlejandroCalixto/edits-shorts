# edits-shorts

Convierte fragmentos de los vídeos largos en YouTube Shorts 1080x1920@30 con el estilo del canal. Para editar o
cambiar un short usa la skill `editar-short` (`.claude/skills/editar-short/SKILL.md`).

Estilo (automático en `motor/render.py`): cámara arriba lo más pequeña posible (recorte fijo del bruto a todo su
ancho, solo pared quitada por arriba para que sea más horizontal y la pantalla de abajo más alta, ver
`motor/config.json`) con mini-zoom de todo el short (la cámara crece y empuja la pantalla; nunca un zoom solo dentro
de su hueco, como ventana aislada):
el mini-zoom entra y sale solo al empezar frase (frases cortas juntas, ≥ 2,5 s) (salto suave ×1,18) y, mientras dura, zoom lento progresivo (0,02/s) de todo el fotograma, cámara y pantalla juntas, hacia el centro de la cámara, sin tocar los subtítulos (nunca solo dentro de la cámara como entorno aislado); un "¿eh?" siempre cierra la frase anterior, nunca abre una (no lleva cambio de plano delante); el primer plano es
siempre normal, nunca se empieza con zoom; si el bruto tiene
un corte (jump cut) al empezar la frase, el zoom entra o sale en el fotograma exacto del corte, nunca desfasado; pantalla abajo
recortada sobre lo importante (si es un reel al que reacciona, solo el vídeo del reel llenando todo el ancho, sin bandas negras a los lados: como `object-fit: cover`, recortando un poco sus lados), con los cambios de plano también al empezar frase; imágenes del usuario siempre abajo, debajo de la cara, con `recursos/cam shot.wav`; toda imagen o meme que pida
aparece y desaparece de golpe, sin animación, con un zoom lento constante y suave (subpíxel, sin vibrar) desde el centro (nunca desde una esquina) mientras está (`zoom_imagen_por_segundo`), y si un cambio de plano
queda cerca de su inicio o fin se mueve a ese mismo fotograma (nunca un fotograma suelto entre imagen y plano);
títulos que pida el usuario grandes en el centro (tamaño 130, blancos salvo que pida otro color, líneas juntas: interlineado 0,74),
con zoom-in de 0,2 s en ease-in (de menos a más rápido) sonando `recursos/swoosh.wav`, y zoom lento constante
hasta desaparecer sin transición;
memes del bruto estirados a toda la pantalla 1080x1920 aunque se deformen, salvo lo que el usuario diga que no es
meme; subtítulos amarillos en MAYÚSCULAS, Sofia Sans Black Italic con sombra dura y halo negro difuminado,
que aparecen con zoom-in de 0,1 s en ease con desenfoque de movimiento y desaparecen de golpe, sin animación.

## Carpetas
- `brutos/` fragmentos ya recortados (1920x1080). `imagenes/` imágenes que pasa el usuario.
- `salida/` `short-N.mp4`. `trabajo/<slug>/` transcripción, subs, decisiones (borrable al terminar).
- `recursos/cam shot.wav`, `recursos/swoosh.wav`, `fuentes/SofiaSans-BlackItalic.ttf`, `motor/` scripts y `config.json`.

## Entorno
- Python 3.12 + venv `.venv` con mise (en el PATH, activa el venv solo): `python ...` desde la raíz.
  Dependencias: `uv pip install faster-whisper "av<16" numpy soundfile`.
- ffmpeg en PATH (rutas relativas a la raíz en los filtros). GPU AMD: codifica con `h264_amf`.

Para borrar lo efímero tras cada vídeo (salida/, trabajo/) usa la skill `limpiar` (`motor/limpiar.py`).
