"""Gate G3: el servidor/modelo emite un tool_call parseable. Requiere el modelo en la iGPU.

Uso (desde el venv del servidor):
  .venv\\Scripts\\python.exe smoke_tools.py
"""
import json
import os

from ov_engine import OVEngine
from tool_parsing import parse_tool_calls

MODEL = os.environ.get("INFERENCE_MODEL_DIR",
                       os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "models", "qwen3-4b-int4-ov"))
DEVICE = os.environ.get("INFERENCE_DEVICE", "GPU")

TOOLS = [{
    "type": "function",
    "function": {
        "name": "comparar",
        "description": "Compara dos o mas procesadores por nombre o numero de modelo.",
        "parameters": {
            "type": "object",
            "properties": {"refs": {"type": "array", "items": {"type": "string"}}},
            "required": ["refs"],
        },
    },
}]


def main():
    engine = OVEngine(MODEL, DEVICE)
    msg = [{"role": "user", "content": "comparame el intel 125U contar el amd 340"}]
    out = engine.generate(msg, max_new_tokens=256, temperature=0.0, tools=TOOLS)
    print("=== salida cruda ===")
    print(out)
    calls = parse_tool_calls(out)
    print("=== tool_calls parseados ===")
    print(json.dumps(calls, ensure_ascii=False, indent=2))
    print("GATE G3:", "OK" if calls and calls[0]["function"]["name"] == "comparar"
          else "REVISAR (ver CAMINO B en ov_engine o ajustar el prompt del sistema)")


if __name__ == "__main__":
    main()
