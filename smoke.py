"""Smoke local: carga el modelo, genera y mide latencia (sin levantar el servidor).

Uso (desde el venv del servicio):
  .venv\\Scripts\\python.exe smoke.py
"""
import os
import time

from ov_engine import OVEngine

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.environ.get("INFERENCE_MODEL_DIR", os.path.join(HERE, "models", "qwen3-4b-int4-ov"))
DEVICE = os.environ.get("INFERENCE_DEVICE", "GPU")


def main():
    print(f"Cargando modelo en {DEVICE}: {MODEL_DIR}")
    t0 = time.perf_counter()
    engine = OVEngine(MODEL_DIR, DEVICE)
    print(f"Carga del modelo: {time.perf_counter() - t0:.1f} s")

    messages = [{"role": "user", "content": "En una frase, que es un procesador?"}]
    engine.generate(messages, max_new_tokens=8)  # warm-up
    t0 = time.perf_counter()
    first = None
    n = 0
    for _tok in engine.stream(messages, max_new_tokens=64):
        if first is None:
            first = time.perf_counter() - t0
        n += 1
    total = time.perf_counter() - t0
    print(f"Primer token (caliente): {first*1000:.0f} ms")
    print(f"Tokens: {n} en {total:.2f} s -> {n/total:.1f} tok/s")


if __name__ == "__main__":
    main()
