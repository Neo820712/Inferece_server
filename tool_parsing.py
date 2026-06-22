"""Parsea la salida de Qwen3 (formato Hermes) a tool_calls estilo OpenAI.

Qwen3 emite las llamadas a herramienta como bloques:
  <tool_call>
  {"name": "comparar", "arguments": {"refs": ["intel 125U", "amd 340"]}}
  </tool_call>
Pueden venir varios. Este parser es puro (sin dependencias de modelo) y testeable.
"""
import json
import re
import uuid

_TOOL_CALL_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)


def parse_tool_calls(text: str):
    matches = _TOOL_CALL_RE.findall(text or "")
    if not matches:
        return None
    calls = []
    for raw in matches:
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        name = obj.get("name")
        if not name:
            continue
        args = obj.get("arguments", {})
        calls.append({
            "id": "call_" + uuid.uuid4().hex[:8],
            "type": "function",
            "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)},
        })
    return calls or None


def strip_tool_calls(text: str) -> str:
    """Devuelve el texto sin los bloques <tool_call> (para el content residual)."""
    return _TOOL_CALL_RE.sub("", text or "").strip()
