"""Tests del endpoint /v1/chat/completions con un motor falso.

No requiere OpenVINO. Verifica el contrato HTTP de tool_calls cuando el
motor emite un bloque <tool_call>, y que la respuesta plain-text no cambia
cuando no se pasan herramientas.
"""
import json

import pytest

from server import create_app


TOOL_CALL_BLOCK = (
    '<tool_call>\n'
    '{"name": "comparar", "arguments": {"refs": ["intel 125U", "amd 340"]}}\n'
    '</tool_call>'
)

TOOLS = [{
    "type": "function",
    "function": {
        "name": "comparar",
        "description": "Compara dos o mas procesadores.",
        "parameters": {
            "type": "object",
            "properties": {"refs": {"type": "array", "items": {"type": "string"}}},
            "required": ["refs"],
        },
    },
}]


class FakeEngine:
    """Motor simulado: si recibe tools, emite un bloque <tool_call>; si no, texto plano."""

    def generate(self, messages, max_new_tokens=512, temperature=0.0, tools=None) -> str:
        if tools:
            return TOOL_CALL_BLOCK
        return "El 125U tiene 8 nucleos."

    def stream(self, messages, max_new_tokens=512, temperature=0.0):
        yield "texto"


class FakeEngineWithThink:
    """Motor que devuelve un bloque <think> vacio seguido de texto."""

    def generate(self, messages, max_new_tokens=512, temperature=0.0, tools=None) -> str:
        return "<think>\n\n</think>Hola"

    def stream(self, messages, max_new_tokens=512, temperature=0.0):
        yield "texto"


@pytest.fixture
def client():
    app = create_app(FakeEngine(), model_name="test-model")
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_con_tools_devuelve_tool_calls(client):
    payload = {
        "messages": [{"role": "user", "content": "compara el 125U con el 340"}],
        "tools": TOOLS,
    }
    resp = client.post("/v1/chat/completions",
                       data=json.dumps(payload),
                       content_type="application/json")
    assert resp.status_code == 200
    data = resp.get_json()
    choice = data["choices"][0]
    assert choice["finish_reason"] == "tool_calls"
    tool_calls = choice["message"]["tool_calls"]
    assert len(tool_calls) == 1
    assert tool_calls[0]["function"]["name"] == "comparar"
    assert tool_calls[0]["type"] == "function"
    assert isinstance(tool_calls[0]["function"]["arguments"], str)
    assert '"refs"' in tool_calls[0]["function"]["arguments"]


def test_sin_tools_respuesta_igual_que_antes(client):
    payload = {
        "messages": [{"role": "user", "content": "cuantos nucleos tiene el 125U"}],
    }
    resp = client.post("/v1/chat/completions",
                       data=json.dumps(payload),
                       content_type="application/json")
    assert resp.status_code == 200
    data = resp.get_json()
    choice = data["choices"][0]
    assert choice["finish_reason"] == "stop"
    assert "8 nucleos" in choice["message"]["content"]
    assert "tool_calls" not in choice["message"]


# ── Tests de limpieza de <think> ─────────────────────────────────────

@pytest.fixture
def client_think():
    app = create_app(FakeEngineWithThink(), model_name="test-model")
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_think_tags_eliminados_plain(client_think):
    payload = {
        "messages": [{"role": "user", "content": "hola"}],
    }
    resp = client_think.post("/v1/chat/completions",
                             data=json.dumps(payload),
                             content_type="application/json")
    assert resp.status_code == 200
    data = resp.get_json()
    content = data["choices"][0]["message"]["content"]
    assert content == "Hola"
    assert "<think>" not in content


# ── Tests de transcripcion de audio ──────────────────────────────────────

import io
import wave
import struct
import numpy as np


class _FakeTranscriber:
    def __init__(self, text="hola mundo"):
        self.text = text
        self.calls = []

    def transcribe(self, samples, language="es"):
        self.calls.append((len(samples), language))
        return self.text


def _wav_bytes(hz=16000, seconds=0.1):
    n = int(hz * seconds)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(hz)
        w.writeframes(struct.pack("<" + "h" * n, *([0] * n)))
    return buf.getvalue()


def test_transcriptions_ok():
    tr = _FakeTranscriber("compara el 165H")
    app = create_app(engine=None, transcriber=tr)
    client = app.test_client()
    data = {"file": (io.BytesIO(_wav_bytes()), "a.wav"), "language": "es"}
    r = client.post("/v1/audio/transcriptions", data=data,
                    content_type="multipart/form-data")
    assert r.status_code == 200
    assert r.get_json()["text"] == "compara el 165H"
    assert tr.calls and tr.calls[0][1] == "es"


def test_transcriptions_unavailable_without_transcriber():
    app = create_app(engine=None, transcriber=None)
    r = app.test_client().post("/v1/audio/transcriptions",
                               data={"file": (io.BytesIO(_wav_bytes()), "a.wav")},
                               content_type="multipart/form-data")
    assert r.status_code == 503


def test_transcriptions_missing_file():
    app = create_app(engine=None, transcriber=_FakeTranscriber())
    r = app.test_client().post("/v1/audio/transcriptions", data={},
                               content_type="multipart/form-data")
    assert r.status_code == 400
