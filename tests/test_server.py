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
