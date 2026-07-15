"""Humo de Whisper: transcribe un WAV de prueba. Requiere el modelo OpenVINO y hardware.

Uso: .venv\\Scripts\\python smoke_whisper.py [ruta.wav]
Genera un tono silencioso si no se pasa WAV (solo verifica que el pipeline corre).
"""
import os
import sys
import wave

import numpy as np

from whisper_engine import WhisperEngine

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.environ.get("WHISPER_MODEL_DIR", os.path.join(HERE, "models", "whisper-medium-ov"))
DEVICE = os.environ.get("WHISPER_DEVICE", "NPU")


def _load_wav(path):
    with wave.open(path, "rb") as w:
        assert w.getframerate() == 16000 and w.getnchannels() == 1
        frames = w.readframes(w.getnframes())
    return np.frombuffer(frames, dtype="<i2").astype("float32") / 32768.0


if __name__ == "__main__":
    print(f"Cargando Whisper en {DEVICE}: {MODEL}")
    eng = WhisperEngine(MODEL, DEVICE)
    print(f"Dispositivo activo: {eng.active_device}")
    samples = _load_wav(sys.argv[1]) if len(sys.argv) > 1 else np.zeros(16000, "float32")
    print("Transcripcion:", repr(eng.transcribe(samples, language="es")))
