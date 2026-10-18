---
name: limpiar
description: Limpia los residuos del proyecto tras terminar un vídeo (salida/, trabajo/ y cachés). Úsala cuando el usuario diga "limpia", "limpia todo", "borra lo de este vídeo" o similar.
---

# Limpiar

1. Ejecuta `python motor/limpiar.py` desde la raíz: vacía `salida/` y `trabajo/` (las carpetas se
   quedan) y borra `motor/__pycache__`.
2. Solo si el usuario pide borrar también los brutos ("limpia todo", "borra también los brutos"), añade `--brutos`
   (vacía `brutos/` e `imagenes/`).
3. Dile en una línea qué se ha borrado y cuántos MB se han liberado.
