"""Tests del adaptador de API estilo Ollama (/api/chat, /api/tags) con motor falso.

No requiere OpenVINO. Verifica que el "sobre" JSON de Ollama es correcto y que el
motor por debajo es el mismo (tool_calls con arguments como objeto, no string).
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
    def generate(self, messages, max_new_tokens=512, temperature=0.0, tools=None) -> str:
        if tools:
            return TOOL_CALL_BLOCK
        return "El 125U tiene 8 nucleos."

    def stream(self, messages, max_new_tokens=512, temperature=0.0):
        yield "hola "
        yield "mundo"


@pytest.fixture
def client():
    app = create_app(FakeEngine(), model_name="test-model")
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_ollama_chat_sin_tools(client):
    payload = {"model": "test-model", "stream": False,
               "messages": [{"role": "user", "content": "cuantos nucleos"}]}
    r = client.post("/api/chat", data=json.dumps(payload), content_type="application/json")
    assert r.status_code == 200
    data = r.get_json()
    assert data["model"] == "test-model"
    assert data["done"] is True
    assert data["done_reason"] == "stop"
    assert data["message"]["role"] == "assistant"
    assert "8 nucleos" in data["message"]["content"]
    assert "tool_calls" not in data["message"]


def test_ollama_chat_con_tools_arguments_es_objeto(client):
    payload = {"model": "test-model", "stream": False,
               "messages": [{"role": "user", "content": "compara 125U y 340"}],
               "tools": TOOLS}
    r = client.post("/api/chat", data=json.dumps(payload), content_type="application/json")
    assert r.status_code == 200
    tc = r.get_json()["message"]["tool_calls"]
    assert len(tc) == 1
    assert tc[0]["function"]["name"] == "comparar"
    # A diferencia de OpenAI, en Ollama arguments es objeto, no string
    assert isinstance(tc[0]["function"]["arguments"], dict)
    assert tc[0]["function"]["arguments"]["refs"] == ["intel 125U", "amd 340"]


def test_ollama_chat_stream_ndjson(client):
    payload = {"model": "test-model", "stream": True,
               "messages": [{"role": "user", "content": "hola"}]}
    r = client.post("/api/chat", data=json.dumps(payload), content_type="application/json")
    assert r.status_code == 200
    assert r.mimetype == "application/x-ndjson"
    lines = [json.loads(l) for l in r.get_data(as_text=True).splitlines() if l.strip()]
    assert "".join(o["message"]["content"] for o in lines) == "hola mundo"
    assert lines[-1]["done"] is True


def test_ollama_chat_sin_messages_da_400(client):
    r = client.post("/api/chat", data=json.dumps({"model": "x"}),
                    content_type="application/json")
    assert r.status_code == 400


def test_ollama_tags(client):
    r = client.get("/api/tags")
    assert r.status_code == 200
    models = r.get_json()["models"]
    assert models and models[0]["name"] == "test-model"
