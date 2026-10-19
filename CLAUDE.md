# edits-shorts

Convierte fragmentos de los vídeos largos en YouTube Shorts 1080x1920@30 con el estilo del canal. Para editar o
cambiar un short usa la skill `editar-short` (`.claude/skills/editar-short/SKILL.md`).

Estilo (automático en `motor/render.py`): cámara arriba (recorte fijo del bruto, ver `motor/config.json`) con
mini-zoom que entra y sale solo al empezar frase (frases cortas juntas, ≥ 2,5 s) y zoom lento; si el bruto tiene
un corte (jump cut) al empezar la frase, el zoom entra o sale en el fotograma exacto del corte, nunca desfasado; pantalla abajo
recortada sobre lo importante, con los cambios de plano también al empezar frase; imágenes del usuario siempre abajo, debajo de la cara, con `recursos/cam shot.wav`, y si un cambio de plano
queda cerca de su inicio o fin se mueve a ese mismo fotograma (nunca un fotograma suelto entre imagen y plano);
títulos que pida el usuario grandes en el centro (tamaño 130, blancos salvo que pida otro color, líneas juntas: interlineado 0,74),
con zoom-in de 0,2 s en ease-in (de menos a más rápido) sonando `recursos/swoosh.wav`, y zoom lento constante
hasta desaparecer sin transición;
memes del bruto estirados a toda la pantalla 1080x1920 aunque se deformen, salvo lo que el usuario diga que no es
meme; subtítulos amarillos en MAYÚSCULAS, Sofia Sans Black Italic con sombra dura y halo negro difuminado.

## Carpetas
- `brutos/` fragmentos ya recortados (1920x1080). `imagenes/` imágenes que pasa el usuario.
- `salida/` `short-N.mp4`. `trabajo/<slug>/` transcripción, subs, decisiones (borrable al terminar).
- `recursos/cam shot.wav`, `recursos/swoosh.wav`, `fuentes/SofiaSans-BlackItalic.ttf`, `motor/` scripts y `config.json`.

## Entorno
- Python 3.12 + venv `.venv` con mise (en el PATH, activa el venv solo): `python ...` desde la raíz.
  Dependencias: `uv pip install faster-whisper "av<16" numpy soundfile`.
- ffmpeg en PATH (rutas relativas a la raíz en los filtros). GPU AMD: codifica con `h264_amf`.

Para borrar lo efímero tras cada vídeo (salida/, trabajo/) usa la skill `limpiar` (`motor/limpiar.py`).
