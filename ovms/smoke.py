"""Comprobacion rapida de los servables de OVMS.

Uso: uv run --no-project --with httpx==0.28.1 --python 3.12 smoke.py
"""
import io
import math
import struct
import sys
import time
import wave

import httpx

MAIN = "http://127.0.0.1:8300"
STT = "http://127.0.0.1:8310"
TIMEOUT = httpx.Timeout(60, connect=3)


def estados(base: str) -> dict[str, str]:
    r = httpx.get(f"{base}/v1/config", timeout=TIMEOUT)
    r.raise_for_status()
    return {k: v["model_version_status"][0]["state"] for k, v in r.json().items()}


def wav_tono(segundos: float = 3.0) -> bytes:
    """Un segundo de tono seguido de silencio: basta para comprobar que el endpoint responde."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        n = int(16000 * segundos)
        w.writeframes(b"".join(
            struct.pack("<h", int(8000 * math.sin(2 * math.pi * 220 * i / 16000)) if i < 16000 else 0)
            for i in range(n)))
    return buf.getvalue()


def embedding(modelo: str, texto: str) -> list[float]:
    r = httpx.post(f"{MAIN}/v3/embeddings", json={"model": modelo, "input": [texto]}, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()["data"][0]["embedding"]


def main() -> int:
    fallos = []

    def paso(nombre, fn):
        t = time.perf_counter()
        try:
            detalle = fn()
            print(f"  ok     {nombre}: {detalle} ({(time.perf_counter() - t) * 1000:.0f} ms)")
        except Exception as e:  # el smoke informa todo fallo, del tipo que sea
            fallos.append(nombre)
            print(f"  FALLO  {nombre}: {e}")

    def servables():
        e = {**estados(MAIN), **estados(STT)}
        faltan = [n for n in ("llm", "embed", "embed-ingest", "whisper") if e.get(n) != "AVAILABLE"]
        if faltan:
            raise RuntimeError(f"no disponibles: {faltan}")
        return "llm, embed, embed-ingest, whisper"

    def transcripcion():
        r = httpx.post(f"{STT}/v3/audio/transcriptions", timeout=TIMEOUT,
                       files={"file": ("tono.wav", wav_tono(), "audio/wav")},
                       data={"model": "whisper", "language": "es", "temperature": "0"})
        r.raise_for_status()
        return "HTTP 200"

    def embeddings():
        texto = "Me cobraron dos veces la factura de este mes."
        a, b = embedding("embed", texto), embedding("embed-ingest", texto)
        coseno = sum(x * y for x, y in zip(a, b))
        if len(a) != 1024 or coseno < 0.99:
            raise RuntimeError(f"dimension {len(a)}, coseno CPU/GPU {coseno:.4f}")
        return f"dimension 1024, coseno CPU/GPU {coseno:.4f}"

    def rechazo_largo():
        r = httpx.post(f"{MAIN}/v3/embeddings", timeout=TIMEOUT,
                       json={"model": "embed", "input": ["factura " * 3000]})
        if r.status_code == 200 and len(r.json()["data"][0]["embedding"]) == 1024:
            return "entrada larga truncada"
        if r.status_code == 400:
            return "entrada larga rechazada con 400"
        raise RuntimeError(f"HTTP {r.status_code}")

    def chat():
        r = httpx.post(f"{MAIN}/v3/chat/completions", timeout=TIMEOUT, json={
            "model": "llm", "max_tokens": 8, "temperature": 0,
            "messages": [{"role": "user", "content": "Responde solo: hola"}]})
        r.raise_for_status()
        return repr(r.json()["choices"][0]["message"]["content"])

    for nombre, fn in (("servables", servables), ("transcripcion", transcripcion),
                       ("embeddings", embeddings), ("embedding largo", rechazo_largo), ("chat", chat)):
        paso(nombre, fn)
    print("RESULTADO:", "FALLO" if fallos else "OK")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
