"""Motor de inferencia OpenVINO GenAI.

El import de openvino_genai es perezoso (dentro de __init__) para que la capa HTTP
del servidor pueda importarse y testearse sin OpenVINO en el entorno de pruebas.
"""
from collections.abc import Iterator


class OVEngine:
    def __init__(self, model_dir: str, device: str = "GPU"):
        import openvino_genai as ov_genai  # perezoso: requiere el venv de inferencia
        self.device = device
        self.pipe = ov_genai.LLMPipeline(model_dir, device)
        self.tokenizer = self.pipe.get_tokenizer()
        self._ov_genai = ov_genai

    def _prompt(self, messages: list[dict]) -> str:
        # Qwen3 "thinking" desactivado: se fuerza con el sufijo /no_think.
        msgs = list(messages)
        if not any(m.get("role") == "system" for m in msgs):
            msgs.insert(0, {"role": "system", "content": "Eres un asistente conciso en espanol."})
        msgs[-1] = {**msgs[-1], "content": msgs[-1]["content"] + " /no_think"}
        return self.tokenizer.apply_chat_template(msgs, add_generation_prompt=True)

    def _config(self, max_new_tokens: int, temperature: float):
        cfg = self._ov_genai.GenerationConfig()
        cfg.max_new_tokens = max_new_tokens
        cfg.temperature = temperature
        cfg.do_sample = temperature > 0.0
        return cfg

    def generate(self, messages: list[dict], max_new_tokens: int = 512,
                 temperature: float = 0.0) -> str:
        result = self.pipe.generate(self._prompt(messages),
                                    self._config(max_new_tokens, temperature))
        return str(result)

    def stream(self, messages: list[dict], max_new_tokens: int = 512,
               temperature: float = 0.0) -> Iterator[str]:
        import queue
        import threading
        q: queue.Queue = queue.Queue()
        sentinel = object()

        def on_token(token: str) -> bool:
            q.put(token)
            return False  # no detener la generacion

        def run():
            try:
                self.pipe.generate(self._prompt(messages),
                                   self._config(max_new_tokens, temperature),
                                   streamer=on_token)
            finally:
                q.put(sentinel)

        threading.Thread(target=run, daemon=True).start()
        while True:
            tok = q.get()
            if tok is sentinel:
                break
            yield tok
