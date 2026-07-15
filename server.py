"""Servidor de inferencia local, OpenAI-compatible, compartido entre programas.

Expone /v1/chat/completions y /v1/models en 127.0.0.1:8200 (loopback, no se expone fuera).
Cualquier programa que hable el API estilo OpenAI puede usarlo como cliente.

La capa HTTP recibe el motor por inyeccion (create_app(engine)); no importa openvino, de
modo que se puede testear con un motor falso. El motor real se construye solo en __main__.
"""
import json
import struct
import time
import uuid
import wave

from flask import Flask, Response, jsonify, request, stream_with_context

from tool_parsing import parse_tool_calls, strip_think, strip_tool_calls


def _completion(text: str, model_name: str) -> dict:
    return {
        "id": "chatcmpl-" + uuid.uuid4().hex,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model_name,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": text},
            "finish_reason": "stop",
        }],
    }


def _completion_tool_calls(tool_calls, content, model_name):
    return {
        "id": "chatcmpl-" + uuid.uuid4().hex,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model_name,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": content or None, "tool_calls": tool_calls},
            "finish_reason": "tool_calls",
        }],
    }


def _chunk(delta: dict, model_name: str, finish=None) -> str:
    payload = {
        "id": "chatcmpl-" + uuid.uuid4().hex,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model_name,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
    }
    return "data: " + json.dumps(payload, ensure_ascii=False) + "\n\n"


def _sse(engine, messages, max_tokens, temperature, model_name):
    yield _chunk({"role": "assistant"}, model_name)
    for tok in engine.stream(messages, max_new_tokens=max_tokens, temperature=temperature):
        yield _chunk({"content": tok}, model_name)
    yield _chunk({}, model_name, finish="stop")
    yield "data: [DONE]\n\n"


def create_app(engine, model_name: str = "qwen3-4b-int4-ov", transcriber=None) -> Flask:
    app = Flask(__name__)

    def _read_wav_mono16k(stream):
        import numpy as np
        with wave.open(stream, "rb") as w:
            if w.getnchannels() != 1 or w.getframerate() != 16000 or w.getsampwidth() != 2:
                raise ValueError("se requiere WAV PCM16 mono 16kHz")
            frames = w.readframes(w.getnframes())
        ints = struct.unpack("<" + "h" * (len(frames) // 2), frames)
        return np.asarray(ints, dtype="float32") / 32768.0

    @app.get("/v1/models")
    def models():
        return jsonify({"object": "list", "data": [{"id": model_name, "object": "model"}]})

    @app.post("/v1/chat/completions")
    def chat_completions():
        body = request.get_json(force=True, silent=True) or {}
        messages = body.get("messages", [])
        if not messages:
            return jsonify({"error": "messages requerido"}), 400
        try:
            max_tokens = int(body.get("max_tokens", 512))
            temperature = float(body.get("temperature", 0.0))
        except (TypeError, ValueError):
            return jsonify({"error": "parametro invalido"}), 400
        if body.get("stream"):
            return Response(stream_with_context(
                _sse(engine, messages, max_tokens, temperature, model_name)),
                mimetype="text/event-stream")
        tools = body.get("tools")
        text = engine.generate(messages, max_new_tokens=max_tokens,
                               temperature=temperature, tools=tools)
        text = strip_think(text)
        if tools:
            calls = parse_tool_calls(text)
            if calls:
                return jsonify(_completion_tool_calls(calls, strip_tool_calls(text), model_name))
        return jsonify(_completion(text, model_name))

    @app.post("/v1/audio/transcriptions")
    def transcriptions():
        if transcriber is None:
            return jsonify({"error": "transcripcion de audio no disponible"}), 503
        f = request.files.get("file")
        if f is None:
            return jsonify({"error": "file requerido"}), 400
        language = (request.form.get("language") or "es").strip()[:8] or "es"
        try:
            samples = _read_wav_mono16k(f.stream)
        except Exception:
            return jsonify({"error": "audio invalido (se espera WAV PCM16 mono 16kHz)"}), 400
        try:
            text = transcriber.transcribe(samples, language=language)
        except Exception as exc:
            return jsonify({"error": "fallo la transcripcion", "detail": str(exc)[:200]}), 500
        return jsonify({"text": text or ""})

    return app


if __name__ == "__main__":
    import os

    from ov_engine import OVEngine  # mismo directorio; perezoso openvino dentro de OVEngine

    HERE = os.path.dirname(os.path.abspath(__file__))
    default_model = os.path.join(HERE, "models", "qwen3-4b-int4-ov")
    model_dir = os.environ.get("INFERENCE_MODEL_DIR", default_model)
    device = os.environ.get("INFERENCE_DEVICE", "GPU")
    port = int(os.environ.get("INFERENCE_PORT", "8200"))

    print(f"[inference] Cargando modelo en {device}: {model_dir}")
    print("[inference] (la primera carga puede tardar ~20 s)")
    app = create_app(OVEngine(model_dir, device))
    print(f"[inference] Listo. Escuchando en http://127.0.0.1:{port}/v1")
    app.run(host="127.0.0.1", port=port)
