"""Motor de inferencia OpenVINO GenAI.

El import de openvino_genai es perezoso (dentro de __init__) para que la capa HTTP
del servidor pueda importarse y testearse sin OpenVINO en el entorno de pruebas.
"""
from collections.abc import Iterator


class OVEngine:
    # CACHE_DIR guarda el modelo ya compilado para la GPU: la primera carga compila,
    # las siguientes reusan el blob (medido: 6.6 s -> 3.2 s).
    # KV_CACHE_PRECISION=u8 reduce a la mitad la memoria del KV cache, que es lo que
    # limita el contexto util en una iGPU con memoria compartida.
    # Ambas dejan el texto generado byte-identico (verificado con decodificacion
    # greedy). DYNAMIC_QUANTIZATION_GROUP_SIZE queda fuera a proposito: si altera la
    # salida en generaciones largas y no aporta velocidad medible.
    _PROPS = {"CACHE_DIR": "ov_cache", "KV_CACHE_PRECISION": "u8"}

    def __init__(self, model_dir: str, device: str = "GPU"):
        import openvino_genai as ov_genai  # perezoso: requiere el venv de inferencia
        self.device = device
        self.pipe = ov_genai.LLMPipeline(model_dir, device, **self._PROPS)
        self.tokenizer = self.pipe.get_tokenizer()
        self._ov_genai = ov_genai

    def _prompt(self, messages: list[dict], tools=None) -> str:
        # Sin sufijos de modo de razonamiento: cada modelo genera como venga
        # configurado. El " /no_think" que se anadia aqui era especifico de Qwen3 y
        # con cualquier otro modelo entraba al prompt como texto sin significado.
        msgs = list(messages)
        if not any(m.get("role") == "system" for m in msgs):
            msgs.insert(0, {"role": "system", "content": "Eres un asistente conciso en espanol."})
        if tools:
            try:
                return self.tokenizer.apply_chat_template(
                    msgs, add_generation_prompt=True, tools=tools)  # CAMINO A
            except TypeError:
                # CAMINO B: el binding no acepta tools -> inyectar en system
                import json as _json
                defs = _json.dumps(tools, ensure_ascii=False)
                hint = ("\n\nTienes estas herramientas (formato JSON):\n<tools>\n" + defs +
                        "\n</tools>\nResponde con uno o varios bloques "
                        "<tool_call>{\"name\":...,\"arguments\":{...}}</tool_call> cuando proceda.")
                msgs[0] = {**msgs[0], "content": msgs[0]["content"] + hint}
                return self.tokenizer.apply_chat_template(msgs, add_generation_prompt=True)
        return self.tokenizer.apply_chat_template(msgs, add_generation_prompt=True)

    def _config(self, max_new_tokens: int, temperature: float):
        cfg = self._ov_genai.GenerationConfig()
        cfg.max_new_tokens = max_new_tokens
        cfg.temperature = temperature
        cfg.do_sample = temperature > 0.0
        return cfg

    def generate(self, messages: list[dict], max_new_tokens: int = 2048,
                 temperature: float = 0.0, tools=None) -> str:
        result = self.pipe.generate(self._prompt(messages, tools),
                                    self._config(max_new_tokens, temperature))
        return str(result)

    def stream(self, messages: list[dict], max_new_tokens: int = 2048,
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
