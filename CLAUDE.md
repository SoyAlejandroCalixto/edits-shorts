# edits-shorts

Convierte fragmentos de los vídeos largos en YouTube Shorts 1080x1920@30 con el estilo del canal. Para editar o
cambiar un short usa la skill `editar-short` (`.claude/skills/editar-short/SKILL.md`).

Estilo (automático en `motor/render.py`): cámara arriba (recorte fijo del bruto, ver `motor/config.json`) con
mini-zoom periódico y zoom lento; pantalla abajo recortada sobre lo importante; imágenes del usuario abajo con
`recursos/cam shot.wav`; subtítulos amarillos en MAYÚSCULAS, Sofia Sans Black Italic con sombra.

## Carpetas
- `brutos/` fragmentos ya recortados (1920x1080). `imagenes/` imágenes que pasa el usuario.
- `salida/` `short-N.mp4`. `trabajo/<slug>/` transcripción, subs, decisiones (borrable al terminar).
- `recursos/cam shot.wav`, `fuentes/SofiaSans-BlackItalic.ttf`, `motor/` scripts y `config.json`.

## Entorno
- Python 3.12 + venv `.venv` con mise: `mise exec -- python ...` desde la raíz.
  Dependencias: `mise exec -- uv pip install faster-whisper "av<16" numpy soundfile`.
- ffmpeg en PATH (rutas relativas a la raíz en los filtros). GPU AMD: codifica con `h264_amf`.

Para borrar lo efímero tras cada vídeo (salida/, trabajo/) usa la skill `limpiar` (`motor/limpiar.py`).
