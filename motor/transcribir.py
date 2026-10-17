"""Transcribe un vídeo en local (faster-whisper, CPU) con tiempos por palabra.

Uso: python motor/transcribir.py <video> [--modelo large-v3-turbo]

Crea en trabajo/<nombre>/:
  audio.wav        audio 16 kHz mono (también lo usa construir.py para afinar cortes)
  palabras.json    [{"s": inicio, "e": fin, "w": palabra}, ...] en segundos del bruto
  transcript.md    frases numeradas con tiempos: lo único que lee Claude
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from comun import carpeta_trabajo, empaquetar  # noqa: E402

# Prompt con titubeos para que Whisper NO limpie repeticiones ni arranques fallidos.
PROMPT = "Eh... bueno, o sea, el, el Madrid... no, espera. Vale, vale, vamos."


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--modelo", default="large-v3-turbo")
    args = ap.parse_args()

    video = Path(args.video)
    dst = carpeta_trabajo(video)
    wav = dst / "audio.wav"
    if not wav.exists():
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vn", "-ac", "1",
                        "-ar", "16000", str(wav)], check=True)

    from faster_whisper import WhisperModel
    t0 = time.time()
    modelo = WhisperModel(args.modelo, device="cpu", compute_type="int8", cpu_threads=12)
    segs, info = modelo.transcribe(
        str(wav), language="es", word_timestamps=True, initial_prompt=PROMPT,
        condition_on_previous_text=False,  # evita que "arregle" repeticiones y bucles de alucinación
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 400, "speech_pad_ms": 300},
    )
    palabras = []
    for s in segs:
        for w in s.words or []:
            palabras.append({"s": round(w.start, 3), "e": round(w.end, 3), "w": w.word.strip()})
        print(f"\r{s.end / info.duration * 100:5.1f}%", end="", flush=True)
    print(f"\ntranscrito en {time.time() - t0:.0f}s ({len(palabras)} palabras)")

    (dst / "palabras.json").write_text(json.dumps(palabras, ensure_ascii=False), encoding="utf-8")
    (dst / "transcript.md").write_text(empaquetar(palabras), encoding="utf-8")
    print(dst / "transcript.md")


if __name__ == "__main__":
    main()
