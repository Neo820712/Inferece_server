"""Motor de transcripcion Whisper sobre OpenVINO GenAI.

Import perezoso de openvino_genai (dentro de __init__) para poder importar el modulo
sin OpenVINO en el entorno de pruebas. Intenta NPU; si el pipeline NPU falla al
inicializar (el decoder autoregresivo es el punto flojo del soporte NPU), cae a CPU.
"""

# Sesgo de dominio: Whisper solo no acierta los codigos alfanumericos de modelo
# (oye "236V" como "236k"). El initial_prompt lo orienta al vocabulario de la app
# (procesadores, comparativa, Intel/AMD y el patron de codigos), sin forzar tokens.
_INITIAL_PROMPT = (
    "Comparativa tecnica de procesadores Intel Core Ultra y AMD Ryzen. "
    "Modelos como Core Ultra 7 236V, 265K, 165H, Ryzen 9 9950X, Ryzen AI, 230. "
    "Comandos: compara, similares, agrega, datos."
)


class WhisperEngine:
    def __init__(self, model_dir: str, device: str = "NPU", fallback: str = "CPU"):
        import openvino_genai as ov_genai
        self._ov_genai = ov_genai
        self.active_device = device
        try:
            self.pipe = ov_genai.WhisperPipeline(model_dir, device)
        except Exception as exc:
            print(f"[whisper] {device} no disponible ({str(exc)[:120]}); "
                  f"cayendo a {fallback}")
            self.active_device = fallback
            self.pipe = ov_genai.WhisperPipeline(model_dir, fallback)

    def transcribe(self, samples, language: str = "es") -> str:
        cfg = self.pipe.get_generation_config()
        cfg.language = f"<|{language}|>"
        cfg.task = "transcribe"
        cfg.return_timestamps = False
        cfg.initial_prompt = _INITIAL_PROMPT
        result = self.pipe.generate(samples, cfg)
        return str(result).strip()
